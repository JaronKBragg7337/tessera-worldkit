"""Verify the Blender adapter against a real Blender.

SPDX-License-Identifier: 0BSD

Run with a Python that has the ``bpy`` module installed::

    pip install bpy==5.0.1        # needs Python 3.11
    python tools/verify_blender.py

or inside a Blender install::

    blender -b --python tools/verify_blender.py

This is what promotes the Blender adapter out of "script-provided-unverified".
It does not check that the script runs; it checks that what comes out the other
side is what the contract promised:

* every asset imports, and its bounds match the catalog to within a millimetre
* triangle counts survive the round trip
* collision objects are built, one per declared hull
* a doorway's collision is genuinely void where the aperture is -- the single
  claim this whole project is built around
* a full layout instantiates at the transforms the layout specifies
* FBX export produces a file

Exit code 0 means the adapter is verified; 1 means it is not; 2 means Blender
was not available to ask.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOLERANCE = 1e-3

failures = []
checks = []


def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    if not ok:
        failures.append("%s: %s" % (name, detail))
    print("  %-4s %-46s %s" % ("ok" if ok else "FAIL", name, detail))
    return ok


def load_adapter():
    path = os.path.join(ROOT, "adapters", "blender", "tessera_blender.py")
    spec = importlib.util.spec_from_file_location("tessera_blender", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def world_bounds(obj):
    corners = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return ([min(c[i] for c in corners) for i in range(3)],
            [max(c[i] for c in corners) for i in range(3)])


def main():
    tb = load_adapter()
    if tb.bpy is None:
        print("bpy is not available; cannot verify. "
              "pip install bpy (Python 3.11), or run under Blender.",
              file=sys.stderr)
        return 2
    bpy = tb.bpy
    print("Blender %s\n" % bpy.app.version_string)

    with open(os.path.join(ROOT, "build", "catalog.json"), encoding="utf-8") as fh:
        catalog = json.load(fh)
    base = os.path.join(ROOT, "build")

    # ------------------------------------------------- 1 every asset imports
    print("assets")
    for record in catalog["assets"]:
        short = record["id"].split("/")[-1]
        tb.wipe()
        objects = tb.import_glb(os.path.join(base, record["files"]["glb"]))
        if not check("%s imports" % short, bool(objects), ""):
            continue
        obj = objects[0]

        lo, hi = world_bounds(obj)
        want_lo = record["dimensions"]["bounds"]["min"]
        want_hi = record["dimensions"]["bounds"]["max"]
        worst = max(max(abs(lo[i] - want_lo[i]), abs(hi[i] - want_hi[i]))
                    for i in range(3))
        check("%s bounds match the contract" % short, worst <= TOLERANCE,
              "worst axis error %.2e m" % worst)

        tris = len(obj.data.loop_triangles) or sum(
            len(p.vertices) - 2 for p in obj.data.polygons)
        check("%s triangle count survives" % short,
              tris == record["geometry"]["triangles"],
              "%d vs %d declared" % (tris, record["geometry"]["triangles"]))

        hulls = tb.make_collision(record, obj, tb.collection("Verify"))
        check("%s collision hulls built" % short,
              len(hulls) == record["collision"]["hull_count"],
              "%d of %d" % (len(hulls), record["collision"]["hull_count"]))

    # -------------------------------------- 2 the doorway is genuinely void
    print("\napertures")
    doorway = next(a for a in catalog["assets"] if a["id"].endswith("wall.doorway.4m"))
    tb.wipe()
    obj = tb.import_glb(os.path.join(base, doorway["files"]["glb"]))[0]
    obj.name = "doorway"
    hulls = tb.make_collision(doorway, obj, tb.collection("Verify"))
    ap = doorway["apertures"][0]
    lo, hi = ap["bounds"]["min"], ap["bounds"]["max"]
    # shrink slightly so a hull merely touching the rim does not count
    pad = 0.01
    intruders = []
    for h in hulls:
        hb_lo = [h.location[i] - abs(h.scale[i]) / 2 for i in range(3)]
        hb_hi = [h.location[i] + abs(h.scale[i]) / 2 for i in range(3)]
        if all(hb_lo[i] < hi[i] - pad and hb_hi[i] > lo[i] + pad for i in range(3)):
            intruders.append(h.name)
    check("doorway collision leaves the aperture void", not intruders,
          "%d hull(s) inside the opening: %s" % (len(intruders), intruders[:3]))
    check("doorway aperture admits the reference character",
          ap["fits_capsule"]["admits_reference_character"],
          "clear %.2f x %.2f m" % (ap["clear_width"], ap["clear_height"]))

    # --------------------------------------------- 3 a whole layout imports
    print("\nlayout")
    layout_path = os.path.join(ROOT, "examples", "safehouse_two_storey", "layout.json")
    with open(layout_path, encoding="utf-8") as fh:
        layout = json.load(fh)
    tb.wipe()
    coll = tb.import_layout(catalog, layout, base, collision=False, do_finish=False)
    placed = [o for o in coll.objects]
    check("layout instantiates every instance",
          len(placed) == layout["instance_count"],
          "%d of %d" % (len(placed), layout["instance_count"]))

    by_id = {i["id"]: i for i in layout["instances"]}
    worst_pos, worst_name = 0.0, ""
    for obj in placed:
        spec = by_id.get(obj.name)
        if not spec:
            continue
        err = max(abs(obj.location[i] - spec["position"][i]) for i in range(3))
        if err > worst_pos:
            worst_pos, worst_name = err, obj.name
    check("instances land at the layout's transforms", worst_pos <= TOLERANCE,
          "worst %.2e m (%s)" % (worst_pos, worst_name))

    # ------------------------------------------------- 4 finishing and FBX
    print("\nexport")
    tb.wipe()
    obj = tb.import_glb(os.path.join(base, doorway["files"]["glb"]))[0]
    before = len(obj.modifiers)
    tb.finish(obj)
    check("finishing pass applies without error", len(obj.modifiers) > before,
          "%d modifier(s) added" % (len(obj.modifiers) - before))

    out_dir = os.path.join(ROOT, "build", "fbx")
    written = tb.export_fbx(catalog, base, out_dir)
    check("FBX export writes one file per asset",
          len(written) == len(catalog["assets"]),
          "%d files" % len(written))
    check("every FBX file has content",
          all(os.path.getsize(p) > 1024 for p in written), "")

    # Blender appends .001 when a name is taken, which silently breaks the
    # UCX_<mesh>_## convention Unreal uses to bind collision. The meshes then
    # import with no collision and nothing says why.
    suffixed = [os.path.basename(p) for p in written
                if any(".%03d" % n in os.path.basename(p) for n in range(1, 10))]
    check("no FBX filename picked up a name-collision suffix", not suffixed,
          "%s" % suffixed[:3])

    names = sorted(o.name for o in bpy.data.objects)
    mesh_names = [n for n in names if not n.startswith("UCX_")]
    ucx = [n for n in names if n.startswith("UCX_")]
    bound = all(any(u.startswith("UCX_%s_" % m) for m in mesh_names) for u in ucx)
    check("UCX collision names match their mesh, as Unreal requires",
          bool(ucx) and bound, "%d hull(s) for %s" % (len(ucx), mesh_names))

    print("\n%d checks, %d failed" % (len(checks), len(failures)))
    if failures:
        for f in failures:
            print("  FAIL %s" % f, file=sys.stderr)
        return 1
    print("Blender adapter VERIFIED against Blender %s" % bpy.app.version_string)
    return 0


if __name__ == "__main__":
    sys.exit(main())
