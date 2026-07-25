"""Import a Tessera catalog and layout into Unreal Engine 5.

SPDX-License-Identifier: 0BSD

Verified against Unreal Engine 5.6.1 by ``tools/verify_unreal.py``. Run it
headless::

    UnrealEditor-Cmd.exe <Project>.uproject ^
        -ExecutePythonScript="tools/verify_unreal.py" ^
        -unattended -nopause -nosplash -NullRHI

Coordinate handling
-------------------
Unreal is Z-up like Tessera, but LEFT-handed, and works in centimetres. The
conversion is::

    canonical (x, y, z) metres  ->  Unreal (x, -y, z) centimetres

That is the mapping Unreal's own glTF importer applies to the shipped meshes, so
layout transforms have to match it exactly or the geometry and the instances
disagree. This was measured, not assumed: a 4.00 x 0.26 x 3.00 m wall imports to
X 0..400, Y -23..3, Z 0..300, which is (x, -y, z) and not a swap.

Negating Y flips handedness on its own, so no extra mirror is applied, and a
canonical yaw about +Z becomes a negated yaw about Unreal's +Z.

Collision
---------
Unreal generates convex collision for an imported mesh **whether or not you ask
it to**. Setting the mesh pipeline's ``collision`` flag to False still produced
one 18-DOP convex hull over a doorway wall in 5.6 -- which seals the doorway,
silently, and is the single worst trap in modular kits.

So this adapter does not try to prevent it. It imports, then *removes* whatever
collision arrived and rebuilds it from the contract's hulls, which are the
carved solid and therefore keep the aperture open.
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
    return (p[0] * CM_PER_METRE, -p[1] * CM_PER_METRE, p[2] * CM_PER_METRE)


def to_unreal_yaw(yaw_degrees):
    """Canonical yaw about +Z -> Unreal yaw, negated for the handedness flip."""
    return -yaw_degrees


def box_to_unreal(hull):
    """A contract hull -> (centre, full extents) in Unreal units.

    ``FKBoxElem`` X/Y/Z are full extents, not half -- confirmed by asking Unreal
    to fit a box to a known mesh and reading back what it stored.
    """
    centre = to_unreal_location([(hull[i] + hull[i + 3]) / 2 for i in range(3)])
    extent = tuple(abs(hull[i + 3] - hull[i]) * CM_PER_METRE for i in range(3))
    return centre, extent


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="tessera_unreal")
    p.add_argument("--catalog", default="build/catalog.json")
    p.add_argument("--layout")
    p.add_argument("--content-root", default="/Game/Tessera")
    p.add_argument("--report", default="build/unreal-import-report.json")
    known, _ = p.parse_known_args(argv or sys.argv[1:])
    return known


# ------------------------------------------------------------------- import
def import_asset(record, base_dir, destination):
    """Import one GLB and return the StaticMesh object Unreal actually made.

    The path cannot be constructed from destination_path + destination_name:
    Interchange nests the result at ``<dest>/<file stem>/StaticMeshes/<name>``,
    so a constructed path resolves to nothing and every later step fails. Ask
    the task what it produced instead.
    """
    source = os.path.join(base_dir, record["files"]["glb"].replace("/", os.sep))
    options = unreal.InterchangeGenericAssetsPipeline()
    try:
        mesh_pipeline = options.get_editor_property("mesh_pipeline")
        mesh_pipeline.set_editor_property("combine_static_meshes", False)
        mesh_pipeline.set_editor_property("import_collision_according_to_mesh_name", False)
        mesh_pipeline.set_editor_property("force_collision_primitive_generation", False)
        # NOTE: setting this False does not stop Unreal generating a convex
        # hull. apply_collision() removes whatever arrives regardless.
        mesh_pipeline.set_editor_property("collision", False)
    except Exception as exc:
        unreal.log_warning("[tessera] mesh pipeline options: %s" % exc)

    task = unreal.AssetImportTask()
    task.filename = source
    task.destination_path = destination
    task.destination_name = record["id"].split("/")[-1].replace(".", "_")
    task.automated = True
    task.replace_existing = True
    task.save = True
    task.options = options

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    meshes = [o for o in (task.get_objects() or [])
              if isinstance(o, unreal.StaticMesh)]
    if not meshes:
        raise RuntimeError("no static mesh produced by importing %s" % source)
    return meshes[0]


def apply_collision(mesh, record):
    """Replace whatever collision arrived with the contract's hulls.

    Built as one list and assigned in a single write. Appending a fitted box and
    editing it in place does not reliably persist, because the array returns
    copies of the struct.
    """
    body = mesh.get_editor_property("body_setup")
    if body is None:
        unreal.EditorStaticMeshLibrary.add_simple_collisions(
            mesh, unreal.ScriptingCollisionShapeType.BOX)
        body = mesh.get_editor_property("body_setup")
    unreal.EditorStaticMeshLibrary.remove_collisions(mesh)

    elems = []
    for hull in record["collision"]["hulls"]:
        centre, extent = box_to_unreal(hull)
        elem = unreal.KBoxElem()
        elem.set_editor_property("center", unreal.Vector(*centre))
        elem.set_editor_property("x", extent[0])
        elem.set_editor_property("y", extent[1])
        elem.set_editor_property("z", extent[2])
        elems.append(elem)

    agg = body.get_editor_property("agg_geom")
    agg.set_editor_property("box_elems", elems)
    agg.set_editor_property("convex_elems", [])
    body.set_editor_property("agg_geom", agg)
    body.set_editor_property("collision_trace_flag",
                             unreal.CollisionTraceFlag.CTF_USE_SIMPLE_AND_COMPLEX)
    mesh.set_editor_property("body_setup", body)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False)
    return len(elems)


def spawn_layout(layout, meshes):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    for inst in layout["instances"]:
        mesh = meshes.get(inst["asset"])
        if mesh is None:
            unreal.log_warning("[tessera] no imported mesh for %s" % inst["asset"])
            continue
        loc = unreal.Vector(*to_unreal_location(inst["position"]))
        yaw = to_unreal_yaw(inst.get("rotation_degrees", (0, 0, 0))[0])
        actor = subsystem.spawn_actor_from_object(mesh, loc, unreal.Rotator(0.0, yaw, 0.0))
        if actor:
            actor.set_actor_label(inst["id"])
            scale = inst.get("scale", 1.0)
            actor.set_actor_scale3d(unreal.Vector(scale, scale, scale))
            spawned.append(actor)
    return spawned


def import_catalog(catalog, base_dir, content_root):
    meshes = {}
    for record in catalog["assets"]:
        mesh = import_asset(record, base_dir, content_root)
        apply_collision(mesh, record)
        meshes[record["id"]] = mesh
    return meshes


def main():
    if unreal is None:
        print("this script only runs inside Unreal Engine's Python environment",
              file=sys.stderr)
        return 2
    args = parse_args()
    base_dir = os.path.dirname(os.path.abspath(args.catalog))
    with open(args.catalog, encoding="utf-8") as fh:
        catalog = json.load(fh)

    meshes = import_catalog(catalog, base_dir, args.content_root)
    report = {
        "catalog": catalog["kit"],
        "fingerprint": catalog.get("fingerprint"),
        "imported": sorted(m.get_path_name() for m in meshes.values()),
        "spawned": [],
    }
    if args.layout:
        with open(args.layout, encoding="utf-8") as fh:
            layout = json.load(fh)
        report["spawned"] = [a.get_actor_label() for a in spawn_layout(layout, meshes)]

    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    unreal.log("[tessera] imported %d, spawned %d"
               % (len(report["imported"]), len(report["spawned"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
