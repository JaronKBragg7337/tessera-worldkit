"""Render preview images with headless Blender.

SPDX-License-Identifier: 0BSD

    pip install bpy==5.0.1        # Python 3.11
    python tools/render_previews.py

Uses Cycles on the CPU. Workbench would be far faster and is the natural choice
for an asset sheet, but it is an OpenGL engine and needs libEGL, which a
headless container does not have. Cycles is a pure software path tracer and
needs no graphics stack at all -- the only renderer here that runs anywhere the
rest of the pipeline runs.

Renders are documentation, not verification. Nothing here is asserted by a test;
`tools/verify_blender.py` does that.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "previews")


def load_adapter():
    path = os.path.join(ROOT, "adapters", "blender", "tessera_blender.py")
    spec = importlib.util.spec_from_file_location("tessera_blender", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup_render(bpy, width, height, samples=48, transparent=True):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    # Denoising is the biggest memory consumer in this pipeline and a small
    # container will have the process killed with no traceback at all. More
    # samples and no denoiser is cheaper in memory and only slightly slower.
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 4
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Base Contrast"


def setup_light(bpy, strength=3.0, sky=0.45):
    """A key sun plus a flat sky. Enough to read form, cheap enough to trace."""
    world = bpy.data.worlds.new("TesseraWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.62, 0.70, 0.80, 1.0)
    bg.inputs[1].default_value = sky
    bpy.context.scene.world = world

    sun_data = bpy.data.lights.new("TesseraSun", type="SUN")
    sun_data.energy = strength
    sun_data.angle = math.radians(3.0)
    sun = bpy.data.objects.new("TesseraSun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(52), 0.0, math.radians(-125))
    return sun


def frame_objects(bpy, objects, azimuth=48.0, elevation=28.0, pad=1.18,
                  ortho=True):
    """Aim a camera at everything, from a fixed three-quarter angle."""
    import mathutils
    # Flush pending transforms first. Blender evaluates object matrices lazily,
    # so straight after import_layout() every matrix_world is still identity and
    # bound_box measurements put the whole building at the origin -- which makes
    # the framing radius tiny and parks the camera inside a wall.
    bpy.context.view_layer.update()
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    for obj in objects:
        for corner in obj.bound_box:
            world = obj.matrix_world @ mathutils.Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], world[i])
                hi[i] = max(hi[i], world[i])
    centre = mathutils.Vector([(lo[i] + hi[i]) / 2 for i in range(3)])
    radius = max(max(hi[i] - lo[i] for i in range(3)), 0.5) * 0.5

    cam_data = bpy.data.cameras.new("TesseraCam")
    cam = bpy.data.objects.new("TesseraCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)

    a, e = math.radians(azimuth), math.radians(elevation)
    direction = mathutils.Vector((math.cos(e) * math.cos(a),
                                  math.cos(e) * math.sin(a),
                                  math.sin(e)))
    # Frame from the bounding sphere and the actual field of view rather than a
    # magic multiplier. A three-quarter view of a 12 m building projects to a
    # much larger silhouette than its longest axis, so a factor tuned on one
    # scene crops the next one.
    sphere = math.sqrt(sum((hi[i] - lo[i]) ** 2 for i in range(3))) / 2.0
    if ortho:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = sphere * 2 * pad
        cam.location = centre + direction * (sphere * 8 + 10)
    else:
        cam_data.type = "PERSP"
        cam_data.lens = 55
        sensor = cam_data.sensor_width
        res_x = bpy.context.scene.render.resolution_x
        res_y = bpy.context.scene.render.resolution_y
        half_h = math.atan((sensor / 2) / cam_data.lens)
        half_v = math.atan((sensor / 2) * (res_y / res_x) / cam_data.lens)
        half_fov = min(half_h, half_v)
        cam.location = centre + direction * (sphere / math.sin(half_fov) * pad)
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render_to(bpy, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def main():
    tb = load_adapter()
    if tb.bpy is None:
        print("bpy not available; pip install bpy under Python 3.11",
              file=sys.stderr)
        return 2
    bpy = tb.bpy
    with open(os.path.join(ROOT, "build", "catalog.json"), encoding="utf-8") as fh:
        catalog = json.load(fh)
    base = os.path.join(ROOT, "build")
    written = []

    # ------------------------------------------------ one image per asset
    for record in catalog["assets"]:
        short = record["id"].split("/")[-1]
        target = os.path.join(OUT, "assets", short + ".png")
        if os.path.exists(target):
            # Resume. Rendering is minutes of work that a container can
            # interrupt; losing all of it to restart is not acceptable.
            print("  skip %s (already rendered)" % short, flush=True)
            written.append(target)
            continue
        tb.wipe()
        setup_render(bpy, 512, 512, samples=16)
        setup_light(bpy)
        objects = tb.import_glb(os.path.join(base, record["files"]["glb"]))
        # No finishing pass here. It is cosmetic for a preview, and the
        # shade_auto_smooth operator it calls stalls indefinitely in this
        # headless build. verify_blender.py exercises it once, deliberately.
        frame_objects(bpy, objects, ortho=False, pad=1.10)
        written.append(render_to(bpy, target))
        print("  rendered %s" % short, flush=True)

    # ---------------------------------------------- the assembled building
    for name, layout_rel, azim, elev in (
        ("workshop_shell", "examples/workshop_shell/layout.json", 48.0, 26.0),
        ("safehouse_two_storey", "examples/safehouse_two_storey/layout.json", 232.0, 24.0),
    ):
        target = os.path.join(OUT, name + ".png")
        if os.path.exists(target):
            print("  skip %s (already rendered)" % name, flush=True)
            written.append(target)
            continue
        with open(os.path.join(ROOT, layout_rel), encoding="utf-8") as fh:
            layout = json.load(fh)
        tb.wipe()
        setup_render(bpy, 1120, 700, samples=24, transparent=False)
        setup_light(bpy)
        coll = tb.import_layout(catalog, layout, base, collision=False,
                                do_finish=False)
        placed = [o for o in coll.objects]
        frame_objects(bpy, placed, azimuth=azim, elevation=elev, ortho=False,
                      pad=1.06)
        written.append(render_to(bpy, target))
        print("  rendered %s (%d instances)" % (name, len(placed)), flush=True)

    # ------------------------------- the two-storey house with its roof off
    # The whole point of the mezzanine is inside, and a closed box shows none
    # of it. Dropping the roof and the near walls is how an architect draws it.
    with open(os.path.join(ROOT, "examples", "safehouse_two_storey",
                           "layout.json"), encoding="utf-8") as fh:
        layout = json.load(fh)
    hidden = ("roof.panel", "roof.ridge", "wall.window", "wall.corner.4m")
    cut = dict(layout)
    cut["instances"] = [i for i in layout["instances"]
                        if not any(h in i["asset"] for h in hidden)]
    tb.wipe()
    setup_render(bpy, 1120, 700, samples=24, transparent=False)
    setup_light(bpy)
    coll = tb.import_layout(catalog, cut, base, collision=False, do_finish=False)
    frame_objects(bpy, list(coll.objects), azimuth=214.0, elevation=30.0,
                  ortho=False, pad=1.04)
    written.append(render_to(bpy, os.path.join(OUT, "safehouse_cutaway.png")))
    print("  rendered safehouse_cutaway (%d instances)" % len(coll.objects))

    print("\n%d images -> %s" % (len(written), os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
