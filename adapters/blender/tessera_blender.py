"""Import a Tessera catalog or layout into Blender, and optionally finish it.

SPDX-License-Identifier: 0BSD

Blender is the canonical space, so there is no conversion to get wrong: metres,
Z-up, right-handed, identical.

Blender is *not* required to build Tessera. The whole generation and validation
pipeline is pure standard-library Python. Blender is here for three optional
jobs the pure pipeline deliberately does not do:

1. import a layout for hand-editing or rendering
2. add bevels and weighted normals -- the shading treatment that makes a
   geometric kit read as one coherent set
3. export FBX, which has no reasonable pure-Python writer

Usage
-----
    blender -b --python adapters/blender/tessera_blender.py -- \\
        --catalog build/catalog.json \\
        --layout examples/workshop_shell/layout.json \\
        --collision --finish --out build/workshop.blend

    blender -b --python adapters/blender/tessera_blender.py -- \\
        --catalog build/catalog.json --fbx build/fbx
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

try:
    import bpy
except ImportError:  # pragma: no cover - only meaningful inside Blender
    bpy = None

BEVEL_WIDTH = 0.012
BEVEL_SEGMENTS = 2
BEVEL_ANGLE = 30.0
WEIGHTED_NORMAL = 60


def argv_after_dashes():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="tessera_blender")
    p.add_argument("--catalog", default="build/catalog.json")
    p.add_argument("--layout")
    p.add_argument("--out", help="write a .blend here")
    p.add_argument("--fbx", help="export every catalog asset as FBX into this folder")
    p.add_argument("--collision", action="store_true",
                   help="create UCX_ collision objects from the contract")
    p.add_argument("--finish", action="store_true",
                   help="apply bevel + weighted normals to every imported mesh")
    p.add_argument("--clear", action="store_true", default=True)
    return p.parse_args(argv if argv is not None else argv_after_dashes())


# ------------------------------------------------------------------ helpers
def wipe():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.objects,
                  bpy.data.collections, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def collection(name):
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def import_glb(path):
    """Import a shipped GLB and undo the glTF Y-up conversion.

    The GLB files are written in glTF space so browsers get them right by
    default. Blender's importer applies +Y-up-to-+Z-up automatically, which
    lands the object back in canonical Tessera space -- identical to how the
    asset was authored. This function asserts that rather than assuming it.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    for obj in new:
        obj.rotation_euler = (0.0, 0.0, 0.0)
        obj.location = (0.0, 0.0, 0.0)
    return new


def check_bounds(obj, record, tolerance=1e-3):
    """Fail loudly if the imported mesh is not the size the contract promised."""
    corners = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = [min(c[i] for c in corners) for i in range(3)]
    hi = [max(c[i] for c in corners) for i in range(3)]
    want_lo = record["dimensions"]["bounds"]["min"]
    want_hi = record["dimensions"]["bounds"]["max"]
    for i in range(3):
        if abs(lo[i] - want_lo[i]) > tolerance or abs(hi[i] - want_hi[i]) > tolerance:
            raise AssertionError(
                "%s imported with bounds %s..%s but the contract says %s..%s -- "
                "the importer's axis conversion does not match the exporter's"
                % (record["id"], lo, hi, want_lo, want_hi))


def make_collision(record, parent, coll):
    """UCX_ boxes straight from the contract's occupancy decomposition.

    This is why Tessera assets keep their doorways: the hulls are the carved
    solid, so an aperture is a hole in the collision too. Letting Blender or the
    engine auto-generate a convex hull would seal it.
    """
    created = []
    for i, hull in enumerate(record["collision"]["hulls"]):
        size = [hull[3] - hull[0], hull[4] - hull[1], hull[5] - hull[2]]
        centre = [(hull[0] + hull[3]) / 2, (hull[1] + hull[4]) / 2,
                  (hull[2] + hull[5]) / 2]
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=centre)
        box = bpy.context.active_object
        box.scale = size
        box.name = "UCX_%s_%02d" % (parent.name, i)
        box.display_type = "WIRE"
        box.parent = parent
        for c in list(box.users_collection):
            c.objects.unlink(box)
        coll.objects.link(box)
        created.append(box)
    return created


def finish(obj):
    """The shading treatment. Optional, and never changes silhouettes."""
    bpy.context.view_layer.objects.active = obj
    bevel = obj.modifiers.new("TesseraBevel", "BEVEL")
    bevel.width = BEVEL_WIDTH
    bevel.segments = BEVEL_SEGMENTS
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(BEVEL_ANGLE)
    bevel.harden_normals = True
    wn = obj.modifiers.new("TesseraWeightedNormal", "WEIGHTED_NORMAL")
    wn.weight = WEIGHTED_NORMAL
    wn.keep_sharp = True
    obj.data.use_auto_smooth = True if hasattr(obj.data, "use_auto_smooth") else None


# ------------------------------------------------------------------- import
def import_catalog(catalog, base_dir, coll_name="Tessera", collision=False,
                   do_finish=False):
    coll = collection(coll_name)
    made = {}
    for record in catalog["assets"]:
        path = os.path.join(base_dir, record["files"]["glb"])
        objects = import_glb(path)
        if not objects:
            raise RuntimeError("nothing imported from %s" % path)
        obj = objects[0]
        obj.name = record["id"].split("/")[-1]
        check_bounds(obj, record)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
        obj["tessera_asset_id"] = record["id"]
        obj["tessera_role"] = record["semantic_role"]
        obj["tessera_pivot"] = record["pivot"]["convention"]
        if collision:
            make_collision(record, obj, coll)
        if do_finish:
            finish(obj)
        made[record["id"]] = obj
    return made


def import_layout(catalog, layout, base_dir, collision=False, do_finish=False):
    protos = import_catalog(catalog, base_dir, "TesseraSource",
                            collision=False, do_finish=do_finish)
    for obj in protos.values():
        obj.hide_set(True)
        obj.hide_render = True
    coll = collection("TesseraLayout")
    index = {a["id"]: a for a in catalog["assets"]}
    for inst in layout["instances"]:
        proto = protos[inst["asset"]]
        copy = proto.copy()
        copy.data = proto.data
        copy.name = inst["id"]
        copy.hide_render = False
        copy.location = inst["position"]
        yaw, pitch, roll = inst.get("rotation_degrees", (0, 0, 0))
        copy.rotation_mode = "ZYX"
        copy.rotation_euler = (math.radians(roll), math.radians(pitch),
                               math.radians(yaw))
        copy.scale = (inst.get("scale", 1.0),) * 3
        coll.objects.link(copy)
        if collision:
            make_collision(index[inst["asset"]], copy, coll)
    return coll


def export_fbx(catalog, base_dir, out_dir):
    """FBX exists here and nowhere else: there is no sane pure-Python writer."""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for record in catalog["assets"]:
        wipe()
        objects = import_glb(os.path.join(base_dir, record["files"]["glb"]))
        obj = objects[0]
        obj.name = record["id"].split("/")[-1]
        check_bounds(obj, record)
        make_collision(record, obj, collection("Tessera"))
        path = os.path.join(out_dir, obj.name + ".fbx")
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=True, apply_unit_scale=True,
            global_scale=1.0, axis_forward="-Z", axis_up="Y",
            mesh_smooth_type="FACE", use_custom_props=True,
            bake_space_transform=False,
        )
        written.append(path)
    return written


def main():
    if bpy is None:
        print("this script only runs inside Blender:\n"
              "  blender -b --python adapters/blender/tessera_blender.py -- --help",
              file=sys.stderr)
        return 2
    args = parse_args()
    base_dir = os.path.dirname(os.path.abspath(args.catalog))
    with open(args.catalog, encoding="utf-8") as fh:
        catalog = json.load(fh)
    if catalog["schema"] != "tessera.catalog/1":
        raise SystemExit("unsupported catalog schema %r" % catalog["schema"])

    if args.clear:
        wipe()

    if args.fbx:
        paths = export_fbx(catalog, base_dir, args.fbx)
        print("[tessera] exported %d FBX files to %s" % (len(paths), args.fbx))
        return 0

    if args.layout:
        with open(args.layout, encoding="utf-8") as fh:
            layout = json.load(fh)
        import_layout(catalog, layout, base_dir, args.collision, args.finish)
        print("[tessera] imported %d instances" % layout["instance_count"])
    else:
        made = import_catalog(catalog, base_dir, collision=args.collision,
                              do_finish=args.finish)
        print("[tessera] imported %d assets" % len(made))

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.out))
        print("[tessera] saved %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
