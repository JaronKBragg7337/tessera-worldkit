"""Catalog assembly: parts in, contract out.

SPDX-License-Identifier: 0BSD
"""
from __future__ import annotations

import hashlib
import json
import os

from .contract import CATALOG_SCHEMA_ID, CONTRACT_VERSION, Provenance
from .export.glb import write_glb
from .export.obj import write_obj
from .measure import build_asset_record, utcnow
from .units import ANGLE_UNIT, CANONICAL_SPACE, LINEAR_UNIT

GENERATOR = "tessera.catalog"

#: Placement policy by category. Kept here, not in the part definitions, so a
#: whole class of assets cannot drift apart. Modular pieces are 90-degree, fixed
#: scale pieces -- that restriction is what keeps occupancy and collision exact
#: under rotation, and it is stated with its reason so an agent knows it is a
#: contract rather than an oversight.
#: ``grid`` selects which snap policy applies. ``module`` pieces must land on
#: the bay grid or they leave visible seams. ``mated`` pieces are positioned by
#: solving a connector, so imposing a grid on top would fight the solver and
#: report a false error on a perfectly placed door. ``free`` pieces are
#: decorative: grounding is still enforced, position is not.
GRID_POLICY = {
    "module": lambda cfg: {"module": cfg.MODULE, "snap_xy": cfg.GRID_XY,
                           "snap_z": cfg.GRID_Z,
                           "yaw_step_degrees": cfg.YAW_STEP,
                           "policy": "module",
                           "rationale": ("Modular pieces seam only on the bay "
                                         "grid they were authored on.")},
    "module_xy": lambda cfg: {"module": cfg.MODULE, "snap_xy": cfg.GRID_XY,
                              "snap_z": None,
                              "yaw_step_degrees": cfg.YAW_STEP,
                              "policy": "module_xy",
                              "rationale": ("Plan position is on the bay grid; "
                                            "height is solved from the roof "
                                            "pitch and is not a round number.")},
    "mated": lambda cfg: {"module": cfg.MODULE, "snap_xy": None, "snap_z": None,
                          "yaw_step_degrees": cfg.YAW_STEP,
                          "policy": "mated",
                          "rationale": ("Positioned by solving a connector "
                                        "against its host, so a grid check "
                                        "would contradict the solver.")},
    "free": lambda cfg: {"module": cfg.MODULE, "snap_xy": None, "snap_z": None,
                         "yaw_step_degrees": None,
                         "policy": "free",
                         "rationale": ("Decorative. Grounding and support are "
                                       "still enforced; position is not.")},
}

PLACEMENT_POLICY = {
    "structure": {
        "grid": "module",
        "allowed_rotations": [0.0, 90.0, 180.0, 270.0],
        "allow_pitch_roll": False,
        "allowed_scaling": {
            "uniform_only": True, "min": 1.0, "max": 1.0,
            "rationale": ("Modular pieces are a dimensional standard. Scaling one "
                          "moves its connectors off the grid and stops it seaming "
                          "with every other piece in the kit."),
        },
        "prohibited_scaling": ["non-uniform", "any scale other than 1.0"],
    },
    "opening": {
        "grid": "mated",
        "allowed_rotations": [0.0, 90.0, 180.0, 270.0],
        "allow_pitch_roll": False,
        "allowed_scaling": {
            "uniform_only": True, "min": 1.0, "max": 1.0,
            "rationale": ("The aperture is sized to the reference character and to "
                          "its matching leaf. Scaling breaks both relationships."),
        },
        "prohibited_scaling": ["non-uniform", "any scale other than 1.0"],
    },
    "roof": {
        "grid": "module_xy",
        "allowed_rotations": [0.0, 90.0, 180.0, 270.0],
        "allow_pitch_roll": False,
        "allowed_scaling": {
            "uniform_only": True, "min": 1.0, "max": 1.0,
            "rationale": "Roof pitch must match across every panel or junctions gap.",
        },
        "prohibited_scaling": ["non-uniform", "any scale other than 1.0"],
    },
    "ground": {
        "grid": "module",
        "allowed_rotations": [0.0, 90.0, 180.0, 270.0],
        "allow_pitch_roll": False,
        "allowed_scaling": {
            "uniform_only": True, "min": 1.0, "max": 1.0,
            "rationale": "Ground tiles define the grid; scaling one desynchronises it.",
        },
        "prohibited_scaling": ["non-uniform", "any scale other than 1.0"],
    },
    "prop": {
        "grid": "free",
        # null means any yaw. Props carry no seams, so forcing them to 90-degree
        # steps makes a scene look machine-placed for no engineering benefit.
        "allowed_rotations": None,
        "allow_pitch_roll": False,
        "allowed_scaling": {
            "uniform_only": True, "min": 0.75, "max": 1.5,
            "rationale": ("Props carry no seams, so modest uniform scaling is safe. "
                          "Non-uniform scaling still breaks the collision hulls."),
        },
        "prohibited_scaling": ["non-uniform"],
    },
    "traversal": {
        "grid": "module",
        "allowed_rotations": [0.0, 90.0, 180.0, 270.0],
        "allow_pitch_roll": False,
        "allowed_scaling": {
            "uniform_only": True, "min": 1.0, "max": 1.0,
            "rationale": "Step heights are tuned to the reference character.",
        },
        "prohibited_scaling": ["non-uniform", "any scale other than 1.0"],
    },
}

PIVOT_RATIONALE = {
    "bay_min_corner_on_base": (
        "Origin at the minimum corner of the bay, on the asset's own base. One "
        "rule for every modular piece means an agent never has to branch: put "
        "the origin on the supporting surface at a grid corner and the piece is "
        "correctly placed. base_offset_z is 0 by construction."
    ),
    "footprint_centre_on_base": (
        "Origin at the centre of the footprint, on the base. Props are placed by "
        "pointing at where they should stand, so a centred origin means the "
        "placement point is the visible resting point."
    ),
    "leaf_min_corner_on_base": (
        "Origin at the minimum corner of the leaf, on its base, matching the "
        "aperture's own minimum corner so a leaf drops into an opening with a "
        "pure translation."
    ),
    "bay_min_x_at_bearing_plane": (
        "Origin at minimum X, on the plane where the panel bears on the wall "
        "top. The panel's lowest vertex is the eave overhang, which hangs below "
        "the bearing plane; using it as the datum would make every correctly "
        "placed roof report as buried."
    ),
    "bay_min_x_at_ridge_line": (
        "Origin at minimum X on the ridge line, so the cap straddles the seam "
        "between two mated panels with a pure translation."
    ),
}


def build_catalog(parts, out_dir, kit_id, kit_version, config_module,
                  author="Jaron K Bragg", write_meshes=True):
    """Generate every asset, export it, and assemble the catalog document."""
    mesh_dir = os.path.join(out_dir, "meshes")
    os.makedirs(mesh_dir, exist_ok=True)

    records = []
    for factory in parts:
        part = factory()
        category = part["category"]
        policy = PLACEMENT_POLICY[category]
        short = part["asset_id"].split("/")[-1]

        files = {}
        if write_meshes:
            glb = os.path.join(mesh_dir, short + ".glb")
            write_glb(glb, part["mesh"], part["materials"], short)
            write_obj(os.path.join(mesh_dir, short + ".obj"),
                      part["mesh"], part["materials"], short)
            files = {
                "glb": os.path.relpath(glb, out_dir).replace(os.sep, "/"),
                "obj": ("meshes/%s.obj" % short),
                "mtl": ("meshes/%s.mtl" % short),
            }

        prov = Provenance(
            generator="%s/%s" % (GENERATOR, factory.__name__),
            generator_version="%s+%s" % (CONTRACT_VERSION, kit_version),
            created_utc=utcnow(),
            authored_by=author,
            origin="original-generated",
            source_inputs=[],
            generated_files=sorted(files.values()),
            derived_from=[],
            third_party_review="none-required",
            notes=("Generated from scratch by the named function using only the "
                   "Tessera geometry kernel. No third-party mesh, texture or "
                   "model file is read at any point in this pipeline."),
        )

        record = build_asset_record(
            asset_id=part["asset_id"],
            name=part["name"],
            category=category,
            semantic_role=part["semantic_role"],
            solid=part.get("solid"),
            mesh=part["mesh"],
            connectors=part["connectors"],
            materials=part["materials"],
            pivot_convention=part["pivot_convention"],
            pivot_rationale=PIVOT_RATIONALE[part["pivot_convention"]],
            grid=GRID_POLICY[policy["grid"]](config_module),
            allowed_rotations=policy["allowed_rotations"],
            allowed_scaling=policy["allowed_scaling"],
            prohibited_scaling=policy["prohibited_scaling"],
            placement_constraints=part.get("placement_constraints", []),
            support=part["support"],
            clearance_boxes=part.get("clearance_boxes", []),
            provenance=prov,
            tags=part.get("tags"),
            occupancy_exact=part.get("occupancy_exact", True),
            occupancy_boxes=part.get("occupancy_boxes"),
            occupancy_tolerance=part.get("occupancy_tolerance", 0.0),
            lods=part.get("lods"),
            notes=part.get("notes", ""),
        )
        record["placement"]["allow_pitch_roll"] = policy["allow_pitch_roll"]
        record["files"] = files
        record["kit"] = {"id": kit_id, "version": kit_version}
        records.append(record)

    catalog = {
        "schema": CATALOG_SCHEMA_ID,
        "contract_version": CONTRACT_VERSION,
        "kit": {"id": kit_id, "version": kit_version},
        "generated_utc": utcnow(),
        "space": {
            "convention": CANONICAL_SPACE,
            "linear_unit": LINEAR_UNIT,
            "angle_unit": ANGLE_UNIT,
            "handedness": "right",
            "up": [0, 0, 1],
            "forward": [0, 1, 0],
        },
        "config": {k: getattr(config_module, k) for k in dir(config_module)
                   if k.isupper() and isinstance(getattr(config_module, k),
                                                 (int, float, str, tuple))},
        "derived": config_module.derived(),
        "asset_count": len(records),
        "totals": {
            "triangles": sum(r["geometry"]["triangles"] for r in records),
            "vertices": sum(r["geometry"]["vertices"] for r in records),
        },
        "assets": records,
    }
    return catalog


def write_catalog(catalog, path):
    text = json.dumps(catalog, indent=2, sort_keys=False) + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return hashlib.sha256(text.encode()).hexdigest()


def load_catalog(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
