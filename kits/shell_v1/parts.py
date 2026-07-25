"""Shell v1 -- the vertical-slice kit.

SPDX-License-Identifier: 0BSD

Twelve original parts, enough to assemble a sealed workshop shell with a
walkable doorway, a glazed window and a pitched gable roof, entirely from
metadata.

Every part is defined by the box kernel or an extruded profile, so every
dimension in the catalog is measured rather than declared, and the collision
hulls are the solid itself -- which is what makes the doorway survive import.
"""
from __future__ import annotations

import math

from tessera.boxset import BoxSet
from tessera.contract import (
    CONNECTOR_COMPATIBILITY, Connector, MaterialSlot, MatingTolerance,
)
from tessera.mesh import extrude_profile, surface_from_boxset
from tessera.units import q

import config as cfg

M = cfg.MODULE
H = cfg.WALL_HEIGHT
T = cfg.WALL_THICKNESS
FT = cfg.FLOOR_THICKNESS
FDT = cfg.FOUNDATION_THICKNESS

MATERIALS = {
    "M_Concrete": MaterialSlot(0, "M_Concrete", "structure",
                               [0.62, 0.61, 0.58, 1.0], 0.0, 0.85),
    "M_Steel": MaterialSlot(0, "M_Steel", "structure",
                            [0.55, 0.57, 0.60, 1.0], 1.0, 0.42),
    "M_Wood": MaterialSlot(0, "M_Wood", "prop",
                           [0.47, 0.33, 0.19, 1.0], 0.0, 0.72),
    "M_PaintedMetal": MaterialSlot(0, "M_PaintedMetal", "trim",
                                   [0.28, 0.36, 0.40, 1.0], 0.6, 0.45),
    "M_RoofSheet": MaterialSlot(0, "M_RoofSheet", "roof",
                                [0.34, 0.32, 0.33, 1.0], 0.7, 0.55),
    "M_Glass": MaterialSlot(0, "M_Glass", "glazing",
                            [0.72, 0.82, 0.85, 0.28], 0.0, 0.08),
}


def slots(*names):
    out = []
    for i, n in enumerate(names):
        base = MATERIALS[n]
        out.append(MaterialSlot(i, base.name, base.role, base.base_color,
                                base.metallic, base.roughness))
    return out


# ------------------------------------------------------------------ helpers
def conn(ident, kind, position, normal, tangent, *, mode="point",
         extent_half=None, role="generic", required=False,
         position_tol=0.001, angle_tol=1.0, roll_tol=1.0, notes=""):
    return Connector(
        id=ident, kind=kind,
        position=[q(v) for v in position],
        normal=[float(v) for v in normal],
        tangent=[float(v) for v in tangent],
        mating_mode=mode,
        extent_half=[q(v) for v in extent_half] if extent_half else None,
        role=role,
        compatible_kinds=list(CONNECTOR_COMPATIBILITY.get(kind, ())),
        incompatible_kinds=sorted(
            set(CONNECTOR_COMPATIBILITY) - set(CONNECTOR_COMPATIBILITY.get(kind, ()))
        ),
        tolerance=MatingTolerance(position_tol, angle_tol, roll_tol),
        required=required,
        notes=notes,
    )


def recess(solid, x0, x1, z0, z1, depth=None):
    """Recess a panel into both faces of a Y-thin wall between x0..x1."""
    d = cfg.PANEL_DEPTH if depth is None else depth
    solid.subtract((x0, -0.001, z0), (x1, d, z1))
    solid.subtract((x0, T - d, z0), (x1, T + 0.001, z1))
    return solid


def wall_shell(length=M, height=H, thickness=T):
    """Bare wall slab with a plinth. The common body of every wall part."""
    s = BoxSet.from_box((0, 0, 0), (length, thickness, height))
    # plinth stands proud on both faces, so assembled walls read as built
    s.add((0, -cfg.PLINTH_PROUD, 0), (length, thickness + cfg.PLINTH_PROUD,
                                      cfg.PLINTH_HEIGHT))
    return s


def wall_connectors(length=M, height=H, thickness=T, extra=()):
    c = [
        conn("base", "wall_base", (length / 2, thickness / 2, 0), (0, 0, -1),
             (1, 0, 0), mode="surface", extent_half=(length / 2, thickness / 2),
             role="support", required=True,
             notes="rests on any floor_top or foundation_top surface"),
        conn("top", "wall_top", (length / 2, thickness / 2, height), (0, 0, 1),
             (1, 0, 0), mode="surface", extent_half=(length / 2, thickness / 2),
             role="bearing", notes="carries a roof panel's roof_bearing"),
        conn("edge_neg_x", "wall_edge", (0, thickness / 2, height / 2),
             (-1, 0, 0), (0, 0, 1), role="seam"),
        conn("edge_pos_x", "wall_edge", (length, thickness / 2, height / 2),
             (1, 0, 0), (0, 0, 1), role="seam"),
    ]
    c.extend(extra)
    return c


# =========================================================== 01 foundation
def foundation_pad():
    s = BoxSet.from_box((0, 0, 0), (M, M, FDT))
    # toe-kick chamfer on the four sides. Deliberately NOT a recess in the top
    # face: anything that rebates the bearing surface makes every slab placed on
    # it float by the rebate depth, which is exactly the bug this kit exists to
    # eliminate. Bearing surfaces stay flat.
    k, kh = 0.05, 0.06
    s.subtract((-0.001, -0.001, -0.001), (k, M + 0.001, kh))
    s.subtract((M - k, -0.001, -0.001), (M + 0.001, M + 0.001, kh))
    s.subtract((-0.001, -0.001, -0.001), (M + 0.001, k, kh))
    s.subtract((-0.001, M - k, -0.001), (M + 0.001, M + 0.001, kh))
    return dict(
        asset_id="tsr:shell/foundation.pad.4m",
        name="Foundation Pad 4 m",
        category="ground", semantic_role="foundation",
        tags=["modular", "ground", "bearing"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=[
            conn("top", "foundation_top", (M / 2, M / 2, FDT), (0, 0, 1),
                 (1, 0, 0), mode="surface", extent_half=(M / 2, M / 2),
                 role="support", required=True,
                 notes="flat bearing surface across the whole pad"),
            conn("edge_neg_x", "floor_edge", (0, M / 2, FDT / 2), (-1, 0, 0), (0, 1, 0)),
            conn("edge_pos_x", "floor_edge", (M, M / 2, FDT / 2), (1, 0, 0), (0, 1, 0)),
            conn("edge_neg_y", "floor_edge", (M / 2, 0, FDT / 2), (0, -1, 0), (1, 0, 0)),
            conn("edge_pos_y", "floor_edge", (M / 2, M, FDT / 2), (0, 1, 0), (1, 0, 0)),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=False, rests_on=["terrain"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes="Sits directly on terrain. Everything else in the kit stacks on it.",
    )


# ================================================================ 02 floor
def floor_slab():
    s = BoxSet.from_box((0, 0, 0), (M, M, FT))
    g, d = cfg.TILE_GROOVE, cfg.TILE_GROOVE_DEPTH
    for t in (M / 2,):
        s.subtract((t - g / 2, 0, FT - d), (t + g / 2, M, FT + 0.001))
        s.subtract((0, t - g / 2, FT - d), (M, t + g / 2, FT + 0.001))
    return dict(
        asset_id="tsr:shell/floor.slab.4m",
        name="Floor Slab 4 m",
        category="structure", semantic_role="floor",
        tags=["modular", "walkable"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=[
            conn("top", "floor_top", (M / 2, M / 2, FT), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, M / 2), role="support",
                 required=True, notes="walkable surface; carries wall_base and prop_base"),
            conn("edge_neg_x", "floor_edge", (0, M / 2, FT / 2), (-1, 0, 0), (0, 1, 0)),
            conn("edge_pos_x", "floor_edge", (M, M / 2, FT / 2), (1, 0, 0), (0, 1, 0)),
            conn("edge_neg_y", "floor_edge", (M / 2, 0, FT / 2), (0, -1, 0), (1, 0, 0)),
            conn("edge_pos_y", "floor_edge", (M / 2, M, FT / 2), (0, 1, 0), (1, 0, 0)),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["foundation_top", "floor_top"],
                     support_axis="z", may_float=False),
        # Deliberately no clearance volume. Headroom above a floor is not a
        # "must stay empty" constraint -- walls and props are supposed to stand
        # on it. Clearance is reserved for volumes an asset needs to *function*,
        # like a door swing. Overstating it turns the report into noise.
        clearance_boxes=[],
        notes="Walking surface is the TOP of this slab at z = %.2f local." % FT,
    )


# ======================================================== 03 straight wall
def wall_straight():
    s = wall_shell()
    recess(s, cfg.PANEL_INSET, M - cfg.PANEL_INSET,
           cfg.PLINTH_HEIGHT + 0.12, H - 0.25)
    return dict(
        asset_id="tsr:shell/wall.straight.4m",
        name="Wall Straight 4 m",
        category="structure", semantic_role="wall",
        tags=["modular", "perimeter"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=wall_connectors(),
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes="Runs the full bay along +X, %0.2f m thick along +Y." % T,
    )


# ========================================================== 04 corner wall
def wall_corner():
    """L piece occupying both edges of a bay corner.

    Deliberately a full L rather than a post: it means a rectangular building
    perimeter can be closed with corners and straights that never overlap, so
    the assembled shell passes the intersection validator with zero tuning.
    """
    s = BoxSet.from_box((0, 0, 0), (M, T, H))
    s.add((0, 0, 0), (T, M, H))
    s.add((0, -cfg.PLINTH_PROUD, 0), (M, T + cfg.PLINTH_PROUD, cfg.PLINTH_HEIGHT))
    s.add((-cfg.PLINTH_PROUD, 0, 0), (T + cfg.PLINTH_PROUD, M, cfg.PLINTH_HEIGHT))
    recess(s, T + cfg.PANEL_INSET, M - cfg.PANEL_INSET,
           cfg.PLINTH_HEIGHT + 0.12, H - 0.25)
    return dict(
        asset_id="tsr:shell/wall.corner.4m",
        name="Wall Corner 4 m",
        category="structure", semantic_role="corner",
        tags=["modular", "perimeter", "junction"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=[
            conn("base", "wall_base", (M / 2, T / 2, 0), (0, 0, -1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, T / 2), role="support",
                 required=True),
            conn("base_y", "wall_base", (T / 2, M / 2, 0), (0, 0, -1), (0, 1, 0),
                 mode="surface", extent_half=(T / 2, M / 2), role="support"),
            conn("top_x", "wall_top", (M / 2, T / 2, H), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, T / 2), role="bearing"),
            conn("top_y", "wall_top", (T / 2, M / 2, H), (0, 0, 1), (0, 1, 0),
                 mode="surface", extent_half=(T / 2, M / 2), role="bearing"),
            conn("edge_pos_x", "wall_edge", (M, T / 2, H / 2), (1, 0, 0), (0, 0, 1),
                 role="seam"),
            conn("edge_pos_y", "wall_edge", (T / 2, M, H / 2), (0, 1, 0), (0, 0, 1),
                 role="seam"),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes="Occupies the -X and -Y edges of its bay; seams out along +X and +Y.",
    )


# ========================================================= 05 doorway wall
def wall_doorway():
    s = wall_shell()
    x0 = (M - cfg.DOOR_WIDTH) / 2
    x1 = x0 + cfg.DOOR_WIDTH
    recess(s, cfg.PANEL_INSET, x0 - 0.12, cfg.PLINTH_HEIGHT + 0.12, H - 0.25)
    recess(s, x1 + 0.12, M - cfg.PANEL_INSET, cfg.PLINTH_HEIGHT + 0.12, H - 0.25)
    s.carve_aperture("door", "door",
                     (x0, -cfg.PLINTH_PROUD - 0.01, 0),
                     (x1, T + cfg.PLINTH_PROUD + 0.01, cfg.DOOR_HEIGHT),
                     axis=1, traversable=True)
    return dict(
        asset_id="tsr:shell/wall.doorway.4m",
        name="Wall Doorway 4 m",
        category="structure", semantic_role="wall_opening",
        tags=["modular", "perimeter", "traversable"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=wall_connectors(extra=[
            conn("jamb_neg_y", "opening_jamb", (M / 2, T / 2, cfg.DOOR_HEIGHT / 2),
                 (0, -1, 0), (1, 0, 0), role="hinge_receiver",
                 notes="mid-reveal mount point; a leaf mated here sits centred "
                       "in the wall thickness rather than surface-hung"),
            conn("jamb_pos_y", "opening_jamb", (M / 2, T / 2, cfg.DOOR_HEIGHT / 2),
                 (0, 1, 0), (1, 0, 0), role="hinge_receiver",
                 notes="same point, opposite facing, for a leaf approaching from +Y"),
        ]),
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[
            [x0, -cfg.DOOR_SWING_CLEARANCE, 0, x1, 0, cfg.DOOR_HEIGHT],
            [x0, T, 0, x1, T + cfg.DOOR_SWING_CLEARANCE, cfg.DOOR_HEIGHT],
        ],
        notes=("Aperture is %.2f x %.2f m. The clearance volumes on both faces "
               "must stay empty or the door is unusable."
               % (cfg.DOOR_WIDTH, cfg.DOOR_HEIGHT)),
    )


# ============================================================== 06 door leaf
def door_leaf():
    g = cfg.DOOR_LEAF_GAP
    w = cfg.DOOR_WIDTH - 2 * g
    h = cfg.DOOR_HEIGHT - g
    th = 0.06
    s = BoxSet.from_box((0, 0, 0), (w, th, h))
    for (z0, z1) in ((0.12, h / 2 - 0.06), (h / 2 + 0.06, h - 0.12)):
        s.subtract((0.10, -0.001, z0), (w - 0.10, 0.018, z1))
        s.subtract((0.10, th - 0.018, z0), (w - 0.10, th + 0.001, z1))
    return dict(
        asset_id="tsr:shell/door.leaf.1m2",
        name="Door Leaf 1.2 m",
        category="opening", semantic_role="door",
        tags=["opening", "leaf"],
        solid=s, mesh=surface_from_boxset(s, "M_PaintedMetal"),
        materials=slots("M_PaintedMetal"),
        connectors=[
            conn("hinge", "leaf_hinge", (w / 2, th / 2, h / 2), (0, -1, 0), (1, 0, 0),
                 role="hinge", required=True,
                 notes="mid-thickness so mating an opening_jamb centres the leaf "
                       "in the reveal; hinge axis is local +Z at x = 0"),
            conn("hinge_back", "leaf_hinge", (w / 2, th / 2, h / 2), (0, 1, 0), (1, 0, 0),
                 role="hinge"),
        ],
        pivot_convention="leaf_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["opening_jamb"],
                     support_axis="none", may_float=True,
                     note="a hung leaf is supported by its jamb, not by the ground"),
        clearance_boxes=[[0, -cfg.DOOR_SWING_CLEARANCE, 0, w, 0, h]],
        notes="Sized to the doorway aperture with a %.0f mm gap all round." % (g * 1000),
    )


# =========================================================== 07 window wall
def wall_window():
    s = wall_shell()
    x0 = (M - cfg.WINDOW_WIDTH) / 2
    x1 = x0 + cfg.WINDOW_WIDTH
    z0 = cfg.WINDOW_SILL
    z1 = z0 + cfg.WINDOW_HEIGHT
    recess(s, cfg.PANEL_INSET, x0 - 0.12, cfg.PLINTH_HEIGHT + 0.12, H - 0.25)
    recess(s, x1 + 0.12, M - cfg.PANEL_INSET, cfg.PLINTH_HEIGHT + 0.12, H - 0.25)
    s.carve_aperture("window", "window",
                     (x0, -cfg.PLINTH_PROUD - 0.01, z0),
                     (x1, T + cfg.PLINTH_PROUD + 0.01, z1),
                     axis=1, traversable=False)
    return dict(
        asset_id="tsr:shell/wall.window.4m",
        name="Wall Window 4 m",
        category="structure", semantic_role="wall_opening",
        tags=["modular", "perimeter", "glazed"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=wall_connectors(extra=[
            conn("jamb_neg_y", "opening_jamb", (M / 2, T / 2, (z0 + z1) / 2),
                 (0, -1, 0), (1, 0, 0), role="glazing_receiver"),
            conn("jamb_pos_y", "opening_jamb", (M / 2, T / 2, (z0 + z1) / 2),
                 (0, 1, 0), (1, 0, 0), role="glazing_receiver"),
        ]),
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes=("Aperture is %.2f x %.2f m at sill height %.2f m. Marked "
               "non-traversable: it is a sight line, not a route."
               % (cfg.WINDOW_WIDTH, cfg.WINDOW_HEIGHT, cfg.WINDOW_SILL)),
    )


# =========================================================== 08 window leaf
def window_leaf():
    g = cfg.DOOR_LEAF_GAP
    w = cfg.WINDOW_WIDTH - 2 * g
    h = cfg.WINDOW_HEIGHT - 2 * g
    fr = 0.07
    th = 0.06
    frame = BoxSet.from_box((0, 0, 0), (w, th, h))
    frame.subtract((fr, -0.001, fr), (w - fr, th + 0.001, h - fr))
    frame.add((w / 2 - 0.025, 0.015, 0), (w / 2 + 0.025, th - 0.015, h))
    mesh = surface_from_boxset(frame, "M_PaintedMetal")
    glass = BoxSet.from_box((fr - 0.01, th / 2 - 0.006, fr - 0.01),
                            (w - fr + 0.01, th / 2 + 0.006, h - fr + 0.01))
    gmesh = surface_from_boxset(glass, "M_Glass")
    offset = len(mesh.positions)
    for p in gmesh.positions:
        mesh.vertex(p)
    for tri, mat, nrm in zip(gmesh.triangles, gmesh.tri_material, gmesh.tri_normal):
        pts = [gmesh.positions[i] for i in tri]
        mesh.add_polygon(pts, mat, nrm)
    combined = frame.copy()
    for b in glass.boxes:
        combined.add(b[:3], b[3:])
    return dict(
        asset_id="tsr:shell/window.leaf.1m8",
        name="Window Leaf 1.8 m",
        category="opening", semantic_role="window",
        tags=["opening", "glazed", "leaf"],
        solid=combined, mesh=mesh,
        materials=slots("M_PaintedMetal", "M_Glass"),
        connectors=[
            conn("mount", "leaf_hinge", (w / 2, th / 2, h / 2), (0, -1, 0), (1, 0, 0),
                 role="fixed_glazing", required=True),
            conn("mount_back", "leaf_hinge", (w / 2, th / 2, h / 2), (0, 1, 0), (1, 0, 0),
                 role="fixed_glazing"),
        ],
        pivot_convention="leaf_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["opening_jamb"],
                     support_axis="none", may_float=True),
        clearance_boxes=[],
        notes="Two material slots: painted frame and glazing. Glazing is not collidable.",
    )


# ============================================================ 09 roof panel
def roof_panel():
    """Pitched panel.

    The bearing datum is the *outer* wall face (local y = 0, local z = 0), not
    the wall centreline. That choice matters: if the roof plane passed through
    the centreline, the panel underside would dip below the wall top on the
    outboard half and every correctly placed roof would report an intersection
    with the wall carrying it. Starting the plane at the outer face means the
    panel touches the wall exactly along its outer top edge and rises away from
    it inboard, which is also how a real rafter meets a wall plate.
    """
    p = cfg.ROOF_PITCH
    y0 = -cfg.ROOF_OVERHANG
    y1 = cfg.ROOF_RUN
    t = cfg.ROOF_THICKNESS

    def v(y):
        return p * y

    profile = [(y0, v(y0)), (y1, v(y1)), (y1, v(y1) + t), (y0, v(y0) + t)]
    mesh = extrude_profile(profile, 0, 0, M, "M_RoofSheet")
    occ, occ_tol = _prism_occupancy(profile, 0, 0, M)
    return dict(
        asset_id="tsr:shell/roof.panel.4m",
        name="Roof Panel 4 m",
        category="roof", semantic_role="roof",
        tags=["modular", "pitched"],
        solid=None, mesh=mesh,
        occupancy_boxes=occ, occupancy_exact=False,
        occupancy_tolerance=occ_tol,
        materials=slots("M_RoofSheet"),
        connectors=[
            conn("bearing", "roof_bearing", (M / 2, 0, 0), (0, 0, -1),
                 (1, 0, 0), mode="surface", extent_half=(M / 2, 0.06),
                 role="support", required=True, position_tol=0.002,
                 notes="place this point on the wall top plane and the panel "
                       "is grounded; the eave overhang legitimately hangs below it"),
            conn("ridge", "roof_ridge", (M / 2, y1, v(y1) + t / 2), (0, 1, 0),
                 (1, 0, 0), role="seam", required=True, angle_tol=2.0,
                 notes="mates the opposing slope's ridge connector"),
            conn("ridge_cap", "roof_ridge", (M / 2, y1, v(y1) + t), (0, 0, 1),
                 (1, 0, 0), role="cap_seat", angle_tol=2.0,
                 notes="upward seat for the ridge cap"),
            conn("edge_neg_x", "roof_edge",
                 (0, (y0 + y1) / 2, (v(y0) + v(y1)) / 2 + t / 2),
                 (-1, 0, 0), (0, 1, 0), role="seam", position_tol=0.002),
            conn("edge_pos_x", "roof_edge",
                 (M, (y0 + y1) / 2, (v(y0) + v(y1)) / 2 + t / 2),
                 (1, 0, 0), (0, 1, 0), role="seam", position_tol=0.002),
        ],
        pivot_convention="bay_min_x_at_bearing_plane",
        support=dict(requires_support=True, rests_on=["wall_top"],
                     support_axis="z", may_float=False,
                     datum_connector="bearing",
                     note="grounded means the bearing connector plane, not the "
                          "panel's lowest vertex, which hangs below on the overhang"),
        clearance_boxes=[],
        notes=("Pitch %.3f degrees, run %.2f m, overhang %.2f m past the wall "
               "face. Occupancy is a %d-slab inner approximation because a "
               "pitched solid has no exact axis-aligned box decomposition; the "
               "validator widens its tolerance to match."
               % (math.degrees(math.atan(p)), y1, cfg.ROOF_OVERHANG, len(occ)))
    )


def _prism_occupancy(profile, axis, a0, a1, slabs=None, max_slabs=256,
                     min_fill=0.5):
    """Exact inner staircase boxes for a convex extruded profile.

    For each slab of the profile's sweep axis, the inner box runs from the
    highest lower-boundary value at either end of the slab to the lowest
    upper-boundary value. For a convex profile that box is guaranteed to lie
    inside the solid, so intersection tests built on it can produce false
    negatives but never false positives -- the safe direction for a clash check.

    Slab count is solved rather than guessed. On a steep thin section the rise
    across one slab can exceed the section thickness, at which point the inner
    box is empty and the approximation silently produces *no* occupancy at all.
    That is exactly the kind of quiet hole this repository exists to prevent, so
    the resolution doubles until every slab yields a box.
    """
    us = [pt[0] for pt in profile]
    u0, u1 = min(us), max(us)

    def column(u):
        vals = []
        n = len(profile)
        for i in range(n):
            x0, y0 = profile[i]
            x1, y1 = profile[(i + 1) % n]
            if abs(x1 - x0) < 1e-12:
                if abs(u - x0) < 1e-9:
                    vals.extend((y0, y1))
                continue
            if min(x0, x1) - 1e-9 <= u <= max(x0, x1) + 1e-9:
                t = (u - x0) / (x1 - x0)
                vals.append(y0 + t * (y1 - y0))
        return (min(vals), max(vals)) if vals else None

    def attempt(n):
        # Boundaries are computed once and shared, so slab k's upper bound is
        # bitwise the same value as slab k+1's lower bound. Recomputing them
        # independently lets rounding put two slabs 1e-6 apart in the wrong
        # direction, and the resulting overlap breaks the disjointness invariant
        # the whole exact-clash story depends on.
        edges = [q(u0 + (u1 - u0) * i / n) for i in range(n + 1)]
        out = []
        shrink = 0.0
        for k in range(n):
            pu0, pu1 = edges[k], edges[k + 1]
            if pu1 - pu0 <= 1e-9:
                return None
            c0, c1 = column(pu0), column(pu1)
            if not c0 or not c1:
                return None
            lo = max(c0[0], c1[0])
            hi = min(c0[1], c1[1])
            if hi - lo <= 1e-6:
                return None
            full = max(c0[1], c1[1]) - min(c0[0], c1[0])
            if full > 0 and (hi - lo) / full < min_fill:
                return None
            shrink = max(shrink, lo - min(c0[0], c1[0]), max(c0[1], c1[1]) - hi)
            b = [0.0] * 6
            b[axis], b[axis + 3] = q(a0), q(a1)
            b[1], b[4] = pu0, pu1
            b[2], b[5] = q(lo), q(hi)
            out.append(tuple(b))
        return out, q(shrink)

    n = slabs or 8
    while n <= max_slabs:
        result = attempt(n)
        if result:
            return result
        n *= 2
    raise ValueError(
        "could not build an inner occupancy staircase filling at least %.0f%% of "
        "this profile at up to %d slabs; the section is too thin relative to its "
        "slope" % (min_fill * 100, max_slabs)
    )


# ============================================================ 10 roof ridge
def roof_ridge():
    """Ridge cap whose underside is a V matching the roof pitch.

    A flat-bottomed cap sitting on the apex of a 33-degree roof leaves an 18 cm
    wedge of daylight on each side. Cutting the underside to the pitch means the
    cap beds onto both slopes, and means its occupancy does not intersect the
    panels it caps.
    """
    hw = cfg.RIDGE_HALF_WIDTH
    hh = cfg.RIDGE_HEIGHT
    p = cfg.ROOF_PITCH
    drop = p * hw
    profile = [
        (-hw, -drop), (0.0, 0.0), (hw, -drop),
        (hw, -drop + hh), (0.0, hh), (-hw, -drop + hh),
    ]
    mesh = extrude_profile(profile, 0, 0, M, "M_RoofSheet")
    occ, occ_tol = _prism_occupancy(profile, 0, 0, M)
    return dict(
        asset_id="tsr:shell/roof.ridge.4m",
        name="Roof Ridge Cap 4 m",
        category="roof", semantic_role="roof_trim",
        tags=["modular", "trim"],
        solid=None, mesh=mesh,
        occupancy_boxes=occ, occupancy_exact=False,
        occupancy_tolerance=occ_tol,
        materials=slots("M_RoofSheet"),
        connectors=[
            conn("seat", "roof_ridge", (M / 2, 0, 0), (0, 0, -1), (1, 0, 0),
                 role="cap", required=True,
                 notes="mates a roof panel's upward ridge_cap seat"),
            conn("edge_neg_x", "roof_edge", (0, 0, hh / 2), (-1, 0, 0), (0, 1, 0)),
            conn("edge_pos_x", "roof_edge", (M, 0, hh / 2), (1, 0, 0), (0, 1, 0)),
        ],
        pivot_convention="bay_min_x_at_ridge_line",
        support=dict(requires_support=True, rests_on=["roof_ridge"],
                     support_axis="none", may_float=True,
                     note="carried by the ridge seam of two mated panels, so it "
                          "is validated by connection rather than by ground contact"),
        clearance_boxes=[],
        notes="Trim only. Carries no load and seals no aperture.",
    )


# ============================================================== 11 crate
def prop_crate():
    sz = cfg.CRATE_SIZE
    s = BoxSet.from_box((-sz / 2, -sz / 2, 0), (sz / 2, sz / 2, sz))
    r = 0.07
    d = 0.022
    for (ax, lo, hi) in ((0, -sz / 2, sz / 2), (1, -sz / 2, sz / 2)):
        for face in (lo, hi):
            p0 = [-sz / 2 + r, -sz / 2 + r, r]
            p1 = [sz / 2 - r, sz / 2 - r, sz - r]
            p0[ax] = face - d if face > 0 else face - 0.001
            p1[ax] = face + 0.001 if face < 0 else face + d
            s.subtract(tuple(p0), tuple(p1))
    s.subtract((-sz / 2 + r, -sz / 2 + r, sz - d), (sz / 2 - r, sz / 2 - r, sz + 0.001))
    return dict(
        asset_id="tsr:shell/prop.crate.small",
        name="Crate Small",
        category="prop", semantic_role="prop",
        tags=["prop", "stackable"],
        solid=s, mesh=surface_from_boxset(s, "M_Wood"),
        materials=slots("M_Wood"),
        connectors=[
            conn("base", "prop_base", (0, 0, 0), (0, 0, -1), (1, 0, 0),
                 mode="surface", extent_half=(sz / 2, sz / 2), role="support",
                 required=True),
            conn("top", "floor_top", (0, 0, sz), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(sz / 2 - r, sz / 2 - r),
                 role="stack", notes="crates stack; the recessed lid is the seat"),
        ],
        pivot_convention="footprint_centre_on_base",
        support=dict(requires_support=True,
                     rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes="Origin at footprint centre so it drops onto a surface without sinking.",
    )


# ============================================================ 12 workbench
def prop_workbench():
    L, D, Hh = cfg.BENCH_LENGTH, cfg.BENCH_DEPTH, cfg.BENCH_HEIGHT
    tt, leg = cfg.BENCH_TOP_THICKNESS, cfg.BENCH_LEG
    s = BoxSet.from_box((-L / 2, -D / 2, Hh - tt), (L / 2, D / 2, Hh))
    inset = 0.10
    for sx in (-1, 1):
        for sy in (-1, 1):
            x = sx * (L / 2 - inset)
            y = sy * (D / 2 - inset)
            s.add((x - leg / 2, y - leg / 2, 0), (x + leg / 2, y + leg / 2, Hh - tt))
    rail_z0, rail_z1 = 0.22, 0.22 + 0.06
    s.add((-L / 2 + inset - leg / 2, -D / 2 + inset - leg / 2, rail_z0),
          (L / 2 - inset + leg / 2, -D / 2 + inset + leg / 2, rail_z1))
    s.add((-L / 2 + inset - leg / 2, D / 2 - inset - leg / 2, rail_z0),
          (L / 2 - inset + leg / 2, D / 2 - inset + leg / 2, rail_z1))
    return dict(
        asset_id="tsr:shell/prop.workbench",
        name="Workbench",
        category="prop", semantic_role="prop",
        tags=["prop", "furniture"],
        solid=s, mesh=surface_from_boxset(s, "M_Wood"),
        materials=slots("M_Wood"),
        connectors=[
            conn("base", "prop_base", (0, 0, 0), (0, 0, -1), (1, 0, 0),
                 mode="surface", extent_half=(L / 2 - inset + leg / 2,
                                              D / 2 - inset + leg / 2),
                 role="support", required=True,
                 notes="footprint is the four legs, not the overhanging top"),
            conn("worktop", "floor_top", (0, 0, Hh), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(L / 2, D / 2), role="stack"),
        ],
        pivot_convention="footprint_centre_on_base",
        support=dict(requires_support=True,
                     rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[[-L / 2, -D / 2 - 0.7, 0, L / 2, -D / 2, Hh]],
        notes="The top overhangs the legs, so footprint area is much smaller "
              "than the silhouette. Support checks use the legs.",
    )


PARTS = [
    foundation_pad, floor_slab, wall_straight, wall_corner, wall_doorway,
    door_leaf, wall_window, window_leaf, roof_panel, roof_ridge,
    prop_crate, prop_workbench,
]
