"""Import a Tessera catalog and layout into Unreal Engine 5.

SPDX-License-Identifier: 0BSD

Run inside the editor's Python console, or headless:

    UnrealEditor-Cmd.exe Project.uproject -run=pythonscript \\
        -script="adapters/unreal/tessera_unreal.py --catalog build/catalog.json"

Coordinate handling
-------------------
Unreal is Z-up like Tessera, but LEFT-handed with +X forward and +Y right, and
it works in centimetres. Two things follow, and both are applied here rather
than left to an import setting somebody will forget:

* one canonical metre is 100 Unreal units
* canonical +Y forward becomes Unreal +X forward, which is the X/Y swap that
  also flips handedness, so no extra mirror is needed

Collision
---------
Auto-generated convex collision seals doorways. That is the single worst trap
in modular kits and it is why every Tessera asset ships its own hulls: the
occupancy box set is already a valid convex decomposition, and because
apertures were carved out of it, the doorway survives. This script turns
``auto_generate_collision`` OFF and builds ``UBodySetup`` boxes from the
contract instead.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import unreal
except ImportError:  # pragma: no cover - only meaningful inside Unreal
    unreal = None

CM_PER_METRE = 100.0


def to_unreal_location(p):
    """canonical (x, y, z) metres -> Unreal (X, Y, Z) centimetres."""
    return (p[1] * CM_PER_METRE, p[0] * CM_PER_METRE, p[2] * CM_PER_METRE)


def to_unreal_yaw(yaw_degrees):
    """Canonical yaw about +Z becomes Unreal yaw about +Z, negated.

    Canonical is right-handed and Unreal is left-handed, so a positive rotation
    in one is a negative rotation in the other once the axes are swapped.
    """
    return -yaw_degrees


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="tessera_unreal")
    p.add_argument("--catalog", default="build/catalog.json")
    p.add_argument("--layout")
    p.add_argument("--content-root", default="/Game/Tessera")
    p.add_argument("--skip-import", action="store_true",
                   help="assets are already imported; only build the level")
    p.add_argument("--report", default="build/unreal-import-report.json")
    known, _ = p.parse_known_args(argv or sys.argv[1:])
    return known


# ------------------------------------------------------------------- import
def import_asset(record, base_dir, destination):
    task = unreal.AssetImportTask()
    task.filename = os.path.join(base_dir, record["files"]["glb"])
    task.destination_path = destination
    task.destination_name = record["id"].split("/")[-1].replace(".", "_")
    task.automated = True
    task.replace_existing = True
    task.save = True

    options = unreal.InterchangeGenericAssetsPipeline()
    try:
        mesh_pipeline = options.get_editor_property("mesh_pipeline")
        # Do NOT let the engine invent collision. See the module docstring.
        mesh_pipeline.set_editor_property("build_nanite", True)
        mesh_pipeline.set_editor_property("import_collision", False)
        mesh_pipeline.set_editor_property("import_collision_according_to_mesh_name",
                                          False)
        mesh_pipeline.set_editor_property("combine_static_meshes", False)
    except Exception as exc:  # editor version differences are expected
        unreal.log_warning("[tessera] could not set mesh pipeline options: %s" % exc)
    task.options = options

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    return "%s/%s" % (destination, task.destination_name)


def apply_collision(asset_path, record):
    """Replace whatever collision exists with the contract's hulls."""
    mesh = unreal.EditorAssetLibrary.load_asset(asset_path)
    if mesh is None:
        raise RuntimeError("could not load %s after import" % asset_path)
    unreal.EditorStaticMeshLibrary.remove_collisions(mesh)
    for hull in record["collision"]["hulls"]:
        centre = [(hull[i] + hull[i + 3]) / 2 for i in range(3)]
        size = [hull[i + 3] - hull[i] for i in range(3)]
        loc = to_unreal_location(centre)
        # Unreal's box helper takes half-extents implicitly via the box size
        unreal.EditorStaticMeshLibrary.add_simple_collisions(
            mesh, unreal.ScriptingCollisionShapeType.BOX)
        # position the newly added primitive
        body = mesh.get_editor_property("body_setup")
        boxes = body.get_editor_property("agg_geom").get_editor_property("box_elems")
        if boxes:
            box = boxes[-1]
            box.set_editor_property("center", unreal.Vector(*loc))
            box.set_editor_property("x", size[1] * CM_PER_METRE)
            box.set_editor_property("y", size[0] * CM_PER_METRE)
            box.set_editor_property("z", size[2] * CM_PER_METRE)
    unreal.EditorAssetLibrary.save_asset(asset_path)
    return len(record["collision"]["hulls"])


def spawn_layout(layout, asset_paths):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    for inst in layout["instances"]:
        path = asset_paths.get(inst["asset"])
        if path is None:
            unreal.log_warning("[tessera] no imported asset for %s" % inst["asset"])
            continue
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        loc = unreal.Vector(*to_unreal_location(inst["position"]))
        yaw = to_unreal_yaw(inst.get("rotation_degrees", (0, 0, 0))[0])
        rot = unreal.Rotator(0.0, 0.0, yaw)
        actor = subsystem.spawn_actor_from_object(mesh, loc, rot)
        if actor:
            actor.set_actor_label(inst["id"])
            actor.set_actor_scale3d(unreal.Vector(*([inst.get("scale", 1.0)] * 3)))
            spawned.append(inst["id"])
    return spawned


def main():
    if unreal is None:
        print("this script only runs inside Unreal Engine's Python environment",
              file=sys.stderr)
        return 2
    args = parse_args()
    base_dir = os.path.dirname(os.path.abspath(args.catalog))
    with open(args.catalog, encoding="utf-8") as fh:
        catalog = json.load(fh)

    report = {"catalog": catalog["kit"], "imported": [], "collision": {},
              "spawned": [], "warnings": []}
    asset_paths = {}
    for record in catalog["assets"]:
        path = "%s/%s" % (args.content_root,
                          record["id"].split("/")[-1].replace(".", "_"))
        if not args.skip_import:
            path = import_asset(record, base_dir, args.content_root)
            report["imported"].append(path)
        asset_paths[record["id"]] = path
        try:
            report["collision"][path] = apply_collision(path, record)
        except Exception as exc:
            report["warnings"].append("collision on %s: %s" % (path, exc))

    if args.layout:
        with open(args.layout, encoding="utf-8") as fh:
            layout = json.load(fh)
        report["spawned"] = spawn_layout(layout, asset_paths)

    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    unreal.log("[tessera] imported %d, spawned %d, %d warning(s)"
               % (len(report["imported"]), len(report["spawned"]),
                  len(report["warnings"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
