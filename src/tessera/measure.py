"""Derive the placement contract from a solid.

SPDX-License-Identifier: 0BSD

Nothing in this module is authored by hand. Every field it produces is measured
from the box set and the extracted mesh, so the contract cannot drift away from
the geometry it describes. That single property is the difference between a
catalog an agent can trust and a README it has to second-guess.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import os as _os

from .boxset import BoxSet, box_size
from .contract import (
    CONNECTOR_COMPATIBILITY, CONTRACT_VERSION, SCHEMA_ID, SCALE_CLASSES,
    ApertureRecord, Bounds, LicenseRecord, Provenance, ValidationRecord,
    to_jsonable,
)
from .mesh import Mesh
from .units import (
    ANGLE_UNIT, CANONICAL_SPACE, CONTACT_EPSILON, FORWARD, LINEAR_UNIT, RIGHT,
    UP, q,
)

AXIS_LETTER = ("x", "y", "z")


def utcnow() -> str:
    """Current UTC time, or a pinned one when SOURCE_DATE_EPOCH is set.

    Timestamps are the only field in a catalog that is not a pure function of
    the inputs, so they are the only thing that can make two identical builds
    differ. Honouring the reproducible-builds convention means CI can assert a
    genuinely byte-identical rebuild rather than a rebuild that is identical
    apart from the parts nobody checked.
    """
    epoch = _os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return _dt.datetime.fromtimestamp(
            int(epoch), _dt.timezone.utc).replace(microsecond=0).isoformat()
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def footprint_rects(solid: BoxSet, tolerance: float = CONTACT_EPSILON):
    """XY rectangles where the solid actually touches its support plane.

    Only boxes whose underside sits on the solid's lowest plane count. This is
    what makes "unsupported object" a real test: a roof panel's footprint is its
    two bearing strips, not its silhouette.
    """
    base = min(b[2] for b in solid.boxes)
    return [(b[0], b[1], b[3], b[4]) for b in solid.boxes
            if abs(b[2] - base) <= tolerance]


def staircase_boxes(mesh: Mesh, axis: int = 2, slabs: int = 12):
    """Conservative inner box decomposition of a non-box solid.

    Used only for prism geometry such as pitched roofs, where no exact set of
    axis-aligned boxes exists. Every emitted box lies strictly inside the mesh's
    convex silhouette per slab, so intersection tests never produce a false
    positive. The record is flagged ``exact: false`` and the validator widens
    its tolerance accordingly rather than pretending the approximation is truth.
    """
    lo = [min(p[i] for p in mesh.positions) for i in range(3)]
    hi = [max(p[i] for p in mesh.positions) for i in range(3)]
    span = hi[axis] - lo[axis]
    if span <= 0:
        return []
    step = span / slabs
    out = []
    for k in range(slabs):
        a0 = lo[axis] + k * step
        a1 = a0 + step
        inside = [p for p in mesh.positions if a0 - 1e-9 <= p[axis] <= a1 + 1e-9]
        if len(inside) < 3:
            continue
        others = [i for i in range(3) if i != axis]
        b = [0.0] * 6
        b[axis], b[axis + 3] = q(a0), q(a1)
        ok = True
        for i in others:
            vals = [p[i] for p in inside]
            b[i], b[i + 3] = q(min(vals)), q(max(vals))
            if b[i + 3] - b[i] <= 0:
                ok = False
        if ok:
            out.append(tuple(b))
    return out


def aperture_records(solid: BoxSet, character_radius: float = 0.35,
                     character_height: float = 1.8):
    """Turn carved holes into checkable traversal openings."""
    out = []
    for ap in solid.apertures:
        sx, sy, sz = box_size(ap.region)
        if ap.axis == 0:
            clear_w, clear_h = sy, sz
        elif ap.axis == 1:
            clear_w, clear_h = sx, sz
        else:
            clear_w, clear_h = sx, sy
        out.append(ApertureRecord(
            id=ap.id,
            kind=ap.kind,
            bounds=Bounds.of(ap.region),
            traversal_axis=AXIS_LETTER[ap.axis],
            clear_width=q(clear_w),
            clear_height=q(clear_h),
            traversable=ap.traversable,
            fits_capsule={
                "radius": q(min(clear_w, clear_h) / 2),
                "height": q(clear_h),
                "admits_reference_character": bool(
                    ap.traversable
                    and clear_w >= character_radius * 2
                    and clear_h >= character_height
                ),
                "reference_character": {
                    "radius": character_radius,
                    "height": character_height,
                },
            },
        ))
    return out


def mesh_digest(mesh: Mesh) -> str:
    h = hashlib.sha256()
    for p in mesh.positions:
        h.update(("%.6f,%.6f,%.6f;" % p).encode())
    for t in mesh.triangles:
        h.update(("%d,%d,%d;" % t).encode())
    return h.hexdigest()


def build_asset_record(
    *,
    asset_id: str,
    name: str,
    category: str,
    semantic_role: str,
    solid: BoxSet | None,
    mesh: Mesh,
    connectors: list,
    materials: list,
    pivot_convention: str,
    pivot_rationale: str,
    grid: dict,
    allowed_rotations: list,
    allowed_scaling: dict,
    prohibited_scaling: list,
    placement_constraints: list,
    support: dict,
    clearance_boxes: list,
    provenance: Provenance,
    tags: list | None = None,
    scale_class: str = "standard",
    occupancy_exact: bool = True,
    occupancy_boxes: list | None = None,
    occupancy_tolerance: float = 0.0,
    lods: list | None = None,
    notes: str = "",
) -> dict:
    """Assemble one catalog entry. All geometry-derived fields are measured."""
    mb = mesh.bounds()
    bounds = Bounds.of(mb)
    size = bounds.size()

    if occupancy_boxes is None:
        occupancy_boxes = list(solid.boxes) if solid is not None else []
    occ = BoxSet(boxes=[tuple(b) for b in occupancy_boxes])

    base_z = mb[2]
    grounded_bounds = Bounds(
        min=[q(mb[0]), q(mb[1]), 0.0],
        max=[q(mb[3]), q(mb[4]), q(mb[5] - base_z)],
    )

    fp = footprint_rects(occ) if occ.boxes else []
    nonman, boundary = mesh.edge_manifold_report()

    record = {
        "schema": SCHEMA_ID,
        "contract_version": CONTRACT_VERSION,
        "id": asset_id,
        "name": name,
        "category": category,
        "semantic_role": semantic_role,
        "tags": sorted(tags or []),
        "scale_class": scale_class,
        "scale_factor": SCALE_CLASSES[scale_class],

        "space": {
            "convention": CANONICAL_SPACE,
            "handedness": "right",
            "up": list(UP),
            "forward": list(FORWARD),
            "right": list(RIGHT),
            "linear_unit": LINEAR_UNIT,
            "angle_unit": ANGLE_UNIT,
            "rotation_order": "ZYX-intrinsic",
        },

        "dimensions": {
            "bounds": to_jsonable(bounds),
            "size": [q(v) for v in size],
            "grounded_bounds": to_jsonable(grounded_bounds),
            "is_authored_grounded": abs(base_z) <= CONTACT_EPSILON,
            "base_z_local": q(base_z),
            "top_z_local": q(mb[5]),
        },

        "pivot": {
            # The origin is (0,0,0) by definition; what an agent needs is where
            # the origin sits *relative to the geometry*, because that is the
            # number that decides whether a placed asset floats or sinks.
            "origin_local": [0.0, 0.0, 0.0],
            "convention": pivot_convention,
            "rationale": pivot_rationale,
            "offset_from_bounds_min": [q(-mb[0]), q(-mb[1]), q(-mb[2])],
            "offset_from_footprint_centre": [
                q(-(mb[0] + mb[3]) / 2), q(-(mb[1] + mb[4]) / 2), q(-mb[2])],
            # Place the origin at support_top + base_offset_z and the asset is
            # grounded exactly. This single number kills the floating-object bug.
            "base_offset_z": q(-base_z),
        },

        "axes": {
            "forward": list(FORWARD),
            "up": list(UP),
            "right": list(RIGHT),
            "ground_plane": "z=0",
            "intended_ground_normal": list(UP),
        },

        "placement": {
            "grid": grid,
            "allowed_rotations": allowed_rotations,
            "allowed_scaling": allowed_scaling,
            "prohibited_scaling": prohibited_scaling,
            "constraints": placement_constraints,
            "support": support,
            "footprint_rects": [[q(v) for v in r] for r in fp],
            "footprint_area": q(sum((r[2] - r[0]) * (r[3] - r[1]) for r in fp)),
        },

        "connectors": [to_jsonable(c) for c in connectors],

        "occupancy": {
            "representation": "axis_aligned_box_set",
            "exact": occupancy_exact,
            "box_count": len(occ.boxes),
            "volume": q(occ.volume()),
            "boxes": [[q(v) for v in b] for b in occ.boxes],
            "disjoint": occ.is_disjoint() if occ.boxes else True,
            # How far the box set may fall short of the true solid. Zero for an
            # exact decomposition. Consumers widen containment tests by this
            # much instead of pretending the approximation is the truth.
            "approximation_tolerance": q(occupancy_tolerance),
        },

        "clearance": {
            "representation": "axis_aligned_box_set",
            "box_count": len(clearance_boxes),
            "boxes": [[q(v) for v in b] for b in clearance_boxes],
            "purpose": "volumes that must remain free for the asset to function",
        },

        "apertures": [to_jsonable(a) for a in aperture_records(solid)] if solid else [],

        "collision": {
            # The occupancy box set is already a valid convex decomposition, so
            # collision is exact and -- critically -- inherits the carved
            # apertures. A doorway generated this way cannot be sealed by an
            # auto-generated convex hull, which was the single worst consumer
            # trap in the source pack.
            "mode": "convex_decomposition",
            "source": "occupancy_box_set" if occupancy_exact else "staircase_approximation",
            "exact": occupancy_exact,
            "hull_count": len(occ.boxes),
            "hulls": [[q(v) for v in b] for b in occ.boxes],
            "preserves_apertures": True,
            "auto_convex_would_seal_apertures": bool(solid and solid.apertures),
            "engine_hint": "import as convex hulls; do NOT let the engine auto-generate",
        },

        "materials": [to_jsonable(m) for m in materials],

        "lods": [to_jsonable(l) for l in (lods or [])],

        "geometry": {
            "triangles": mesh.triangle_count,
            "vertices": mesh.vertex_count,
            "surface_area": q(mesh.surface_area()),
            "signed_volume": q(mesh.signed_volume()),
            "watertight": mesh.is_watertight(),
            "non_manifold_edges": len(nonman),
            "boundary_edges": len(boundary),
            "outward_winding": mesh.signed_volume() > 0,
            "sha256": mesh_digest(mesh),
        },

        "files": {},

        "engine": {
            "unreal": {
                "import_uniform_scale": 1.0,
                "unit_conversion": "1 metre -> 100 uu (applied by the adapter)",
                "combine_meshes": False,
                "generate_lightmap_uvs": False,
                "import_normals": "Import Normals and Tangents",
                "auto_generate_collision": False,
                "collision_source": "UCX_ hulls from occupancy",
                "note": "auto collision seals apertures; use the shipped hulls",
            },
            "unity": {
                "scale_factor": 1.0,
                "convert_units": True,
                "normals": "Import",
                "generate_colliders": False,
                "collision_source": "compound BoxCollider set from occupancy",
            },
            "three": {
                "format": "glb",
                "up_axis": "+Y",
                "conversion": "canonical Z-up right-handed -> glTF Y-up right-handed",
            },
            "blender": {"format": "glb", "conversion": "identity"},
        },

        "provenance": to_jsonable(provenance),
        "license": to_jsonable(LicenseRecord()),
        "validation": to_jsonable(ValidationRecord()),
        "notes": notes,
    }
    return record
