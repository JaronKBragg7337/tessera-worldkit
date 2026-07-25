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
IT = cfg.INTERIOR_WALL_THICKNESS

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
    "M_Plaster": MaterialSlot(0, "M_Plaster", "interior",
                              [0.78, 0.76, 0.72, 1.0], 0.0, 0.90),
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


def partition_shell(length=M, height=H, thickness=IT):
    """Bare partition slab. The common body of every interior wall part.

    Deliberately *not* :func:`wall_shell`: an interior wall carries no plinth.
    The plinth stands ``PLINTH_PROUD`` of the wall face to throw water clear,
    which indoors buys nothing and stops a workbench standing flush against the
    wall -- the exact clearance complaint the workshop scene already raises.
    """
    return BoxSet.from_box((0, 0, 0), (length, thickness, height))


def skirting(solid, a0, a1, axis=0, thickness=IT):
    """Recessed shadow groove along both faces of a partition.

    ``axis`` is the axis the wall runs along: 0 for a wall lying along X (faces
    normal to Y), 1 for one lying along Y (faces normal to X). Passing the
    thickness rather than reading ``T`` is what lets the corner groove both of
    its legs from one function without either of them assuming a dimension.
    """
    g = cfg.INTERIOR_SKIRT_GROOVE
    z0 = cfg.INTERIOR_SKIRT_HEIGHT
    z1 = z0 + g
    if axis == 0:
        solid.subtract((a0, -0.001, z0), (a1, g, z1))
        solid.subtract((a0, thickness - g, z0), (a1, thickness + 0.001, z1))
    else:
        solid.subtract((-0.001, a0, z0), (g, a1, z1))
        solid.subtract((thickness - g, a0, z0), (thickness + 0.001, a1, z1))
    return solid


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



# ========================================================== 13 straight stair
def stair_straight():
    """A closed-stringer stair that lands exactly on the floor above.

    Every step is a box, so the box kernel represents this solid exactly -- no
    approximation, and the collision hulls are the treads themselves. That
    matters more here than anywhere else in the kit: a stair whose collision is
    a single convex hull is a ramp, and a stair whose collision is a hull per
    tread is a stair.

    The rise divides the storey height a whole number of times and the run is
    exactly one bay, both enforced by ``config.validate()``. A stair that lands
    19 cm below the floor is the kind of defect that survives every visual check
    and ruins the level.
    """
    rise, going, width = cfg.STAIR_RISE, cfg.STAIR_GOING, cfg.STAIR_WIDTH
    steps = round(cfg.STOREY_HEIGHT / rise)
    run = steps * going

    s = BoxSet()
    for i in range(steps):
        s.add((0, i * going, 0), (width, (i + 1) * going, (i + 1) * rise))
    # stringers stand slightly proud so the flight reads as built, not extruded
    for x0 in (-cfg.STAIR_STRINGER, width):
        s.add((x0, 0, 0), (x0 + cfg.STAIR_STRINGER, run, rise))

    return dict(
        asset_id="tsr:shell/stair.straight.4m",
        name="Stair Straight 4 m",
        category="traversal", semantic_role="stair",
        tags=["modular", "traversal", "vertical"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=[
            conn("base", "wall_base", (width / 2, run / 2, 0), (0, 0, -1), (0, 1, 0),
                 mode="surface", extent_half=(width / 2, run / 2), role="support",
                 required=True),
            conn("landing", "floor_edge", (width / 2, run, steps * rise),
                 (0, 1, 0), (1, 0, 0), role="seam", required=True,
                 notes="meets the edge of the floor it climbs to; the top tread "
                       "is flush with that floor's walking surface"),
            conn("foot", "floor_edge", (width / 2, 0, 0), (0, -1, 0), (1, 0, 0),
                 role="seam"),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        # Headroom is the whole point of a stairwell opening. Declaring it as
        # clearance means the validator complains when a floor is left solid
        # above the flight, instead of a player discovering it with their head.
        clearance_boxes=[
            [0.0, i * going, (i + 1) * rise,
             width, (i + 1) * going, (i + 1) * rise + cfg.STAIR_HEADROOM]
            for i in range(steps)
        ],
        notes=("%d steps of %.2f m rise and %.2f m going, climbing %.2f m over a "
               "%.2f m run at %.2f degrees. Collision is one hull per tread."
               % (steps, rise, going, steps * rise, run,
                  math.degrees(math.atan2(rise, going)))),
    )


# ==================================================== 14 floor with a stairwell
def floor_opening():
    """A floor slab with a stairwell cut through it.

    The hole is carved with ``carve_aperture`` on the vertical axis, so it is a
    first-class traversal opening rather than absent material: it has a clear
    size, it is checked against the reference character, and collision inherits
    it. Without this piece a second storey is a sealed lid.
    """
    s = BoxSet.from_box((0, 0, 0), (M, M, FT))
    g, d = cfg.TILE_GROOVE, cfg.TILE_GROOVE_DEPTH
    s.subtract((M / 2 - g / 2, 0, FT - d), (M / 2 + g / 2, M, FT + 0.001))
    s.subtract((0, M / 2 - g / 2, FT - d), (M, M / 2 + g / 2, FT + 0.001))

    ow, ol = cfg.OPENING_WIDTH, cfg.OPENING_LENGTH
    # Clear of a beam running under this edge of the slab. At 0.20 the opening
    # overlapped the beam by 4 cm and reported as an obstructed stairwell.
    x0 = cfg.BEAM_WIDTH + 0.06
    y0 = M - ol
    # The aperture reaches the slab edge exactly and does not overhang it.
    # An overhang of even a centimetre clips whatever the slab abuts and
    # reports as an obstructed opening.
    s.carve_aperture("stairwell", "passage",
                     (x0, y0, -0.01), (x0 + ow, M, FT + 0.01),
                     axis=2, traversable=True)

    return dict(
        asset_id="tsr:shell/floor.opening.4m",
        name="Floor Slab with Stairwell 4 m",
        category="structure", semantic_role="floor",
        tags=["modular", "walkable", "traversal"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=[
            conn("top", "floor_top", (M / 2, M / 4, FT), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, M / 4), role="support",
                 required=True,
                 notes="walkable area excludes the stairwell; the extent covers "
                       "the solid half only"),
            conn("stairwell", "floor_edge", (x0 + ow / 2, M, FT / 2),
                 (0, 1, 0), (1, 0, 0), role="seam",
                 notes="the stair's landing connector mates here"),
            conn("edge_neg_x", "floor_edge", (0, M / 2, FT / 2), (-1, 0, 0), (0, 1, 0)),
            conn("edge_pos_x", "floor_edge", (M, M / 2, FT / 2), (1, 0, 0), (0, 1, 0)),
            conn("edge_neg_y", "floor_edge", (M / 2, 0, FT / 2), (0, -1, 0), (1, 0, 0)),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True,
                     rests_on=["wall_top", "foundation_top", "floor_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes=("Stairwell opening is %.2f x %.2f m through the slab. Walking "
               "surface is the top at z = %.2f local."
               % (ow, ol, FT)),
    )


# ================================================================== 15 beam
def beam():
    """A spanning beam, so a floor can cross a bay instead of only ringing one.

    The benchmark exposed the need for this directly: with only perimeter walls
    to bear on, any second storey wider than a single bay is either cantilevered
    or floating, and both are now correctly refused.
    """
    d, w = cfg.BEAM_DEPTH, cfg.BEAM_WIDTH
    s = BoxSet.from_box((0, 0, 0), (M, w, d))
    # lighten the web so it reads as a beam rather than a bar
    for i in range(3):
        cx = M * (i + 1) / 4.0
        s.subtract((cx - 0.22, -0.001, 0.07), (cx + 0.22, 0.05, d - 0.07))
        s.subtract((cx - 0.22, w - 0.05, 0.07), (cx + 0.22, w + 0.001, d - 0.07))
    return dict(
        asset_id="tsr:shell/beam.4m",
        name="Beam 4 m",
        category="structure", semantic_role="beam",
        tags=["modular", "spanning"],
        solid=s, mesh=surface_from_boxset(s, "M_Steel"),
        materials=slots("M_Steel"),
        connectors=[
            conn("bearing", "roof_bearing", (M / 2, w / 2, 0), (0, 0, -1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, w / 2), role="support",
                 required=True, notes="rests on a wall_top like a roof panel does"),
            conn("top", "floor_top", (M / 2, w / 2, d), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, w / 2), role="support",
                 notes="carries a floor slab"),
            conn("edge_neg_x", "wall_edge", (0, w / 2, d / 2), (-1, 0, 0), (0, 0, 1)),
            conn("edge_pos_x", "wall_edge", (M, w / 2, d / 2), (1, 0, 0), (0, 0, 1)),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["wall_top", "column_top"],
                     support_axis="z", may_float=False,
                     # A beam is *defined* by bearing only at its ends, so the
                     # low-contact warning would fire on every correct one.
                     point_bearing=True),
        clearance_boxes=[],
        notes="Spans one bay between two supports, bearing only at its ends. "
              "Its top finishes level with the wall top so the floor above "
              "lands on one continuous plane.",
    )


# =============================================================== 16 railing
def railing():
    """Guards the open side of a stairwell or a landing."""
    h, post, rail = cfg.RAILING_HEIGHT, cfg.RAILING_POST, cfg.RAILING_RAIL
    s = BoxSet()
    n = cfg.RAILING_POSTS
    for i in range(n):
        x = (M - post) * i / (n - 1)
        s.add((x, 0, 0), (x + post, post, h))
    s.add((0, 0, h - rail), (M, rail, h))
    s.add((0, 0, h * 0.45), (M, rail * 0.8, h * 0.45 + rail * 0.8))
    return dict(
        asset_id="tsr:shell/railing.4m",
        name="Railing 4 m",
        category="traversal", semantic_role="railing",
        tags=["modular", "safety"],
        solid=s, mesh=surface_from_boxset(s, "M_Steel"),
        materials=slots("M_Steel"),
        connectors=[
            conn("base", "prop_base", (M / 2, post / 2, 0), (0, 0, -1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, post / 2), role="support",
                 required=True),
            conn("edge_neg_x", "wall_edge", (0, post / 2, h / 2), (-1, 0, 0), (0, 0, 1)),
            conn("edge_pos_x", "wall_edge", (M, post / 2, h / 2), (1, 0, 0), (0, 0, 1)),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes="%.2f m high. Blocks a fall without blocking a sight line." % h,
    )


# =============================================================== 17 column
def column():
    """Carries a beam where there is no wall.

    Exactly one beam shorter than a wall, so column plus beam finishes flush
    with the wall top and the floor above rests on a single plane. Without this
    piece, any storey wider than one walled bay is either cantilevered or
    floating -- both of which the support rules now correctly refuse, which is
    how the gap was found.
    """
    size, h = cfg.COLUMN_SIZE, cfg.COLUMN_HEIGHT
    s = BoxSet.from_box((0, 0, 0), (size, size, h))
    cap = 0.06
    s.add((-0.04, -0.04, 0), (size + 0.04, size + 0.04, cap))
    s.add((-0.04, -0.04, h - cap), (size + 0.04, size + 0.04, h))
    for f in (0.0, size - 0.05):
        s.subtract((f - 0.001, 0.09, cap + 0.08),
                   (f + 0.05, size - 0.09, h - cap - 0.08))
    return dict(
        asset_id="tsr:shell/column.3m",
        name="Column",
        category="structure", semantic_role="column",
        tags=["modular", "bearing"],
        solid=s, mesh=surface_from_boxset(s, "M_Steel"),
        materials=slots("M_Steel"),
        connectors=[
            conn("base", "wall_base", (size / 2, size / 2, 0), (0, 0, -1), (1, 0, 0),
                 mode="surface", extent_half=(size / 2, size / 2), role="support",
                 required=True),
            conn("top", "wall_top", (size / 2, size / 2, h), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(size / 2, size / 2), role="bearing",
                 required=True, notes="carries a beam's bearing connector"),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["floor_top", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[],
        notes=("%.2f m tall -- exactly WALL_HEIGHT minus BEAM_DEPTH, so column "
               "plus beam finishes level with the wall top." % h),
    )


# ============================================================ 18 entry stoop
def stair_stoop():
    """Two steps from the terrain up to the floor, outside a doorway.

    This asset exists because the reachability solver refused the finished
    workshop. The door was open, the aperture was wide enough, collision
    preserved it, and every other rule passed -- and no character could get in,
    because the floor sits 0.50 m above the ground outside and that is twice
    what anyone can step up.

    It is the clearest example so far of a defect that no amount of looking at
    the geometry reveals, because nothing about it looks wrong.
    """
    rise = cfg.STOOP_RISE / cfg.STOOP_STEPS
    going, width = cfg.STOOP_GOING, cfg.STOOP_WIDTH
    depth = going * cfg.STOOP_STEPS

    s = BoxSet()
    for i in range(cfg.STOOP_STEPS):
        s.add((0, i * going, 0), (width, (i + 1) * going, (i + 1) * rise))
    for x0 in (-0.05, width):
        s.add((x0, 0, 0), (x0 + 0.05, depth, rise * 0.5))

    return dict(
        asset_id="tsr:shell/stair.stoop.1m2",
        name="Entrance Stoop",
        category="traversal", semantic_role="stair",
        tags=["traversal", "entrance"],
        solid=s, mesh=surface_from_boxset(s, "M_Concrete"),
        materials=slots("M_Concrete"),
        connectors=[
            conn("base", "prop_base", (width / 2, depth / 2, 0), (0, 0, -1),
                 (0, 1, 0), mode="surface", extent_half=(width / 2, depth / 2),
                 role="support", required=True),
            conn("foot", "floor_edge", (width / 2, 0, 0), (0, -1, 0), (1, 0, 0),
                 role="seam",
                 notes="the approach side; the stair-usability check probes from here"),
            conn("landing", "floor_edge", (width / 2, depth, cfg.STOOP_RISE),
                 (0, 1, 0), (1, 0, 0), role="seam", required=True,
                 notes="the top step is level with the floor inside the doorway"),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=dict(requires_support=True, rests_on=["terrain", "foundation_top"],
                     support_axis="z", may_float=False),
        clearance_boxes=[[0.0, 0.0, cfg.STOOP_RISE, width, depth,
                          cfg.STOOP_RISE + cfg.CHARACTER_HEIGHT]],
        notes=("%d steps of %.2f m rising %.2f m to meet the floor inside. "
               "Sits on terrain in front of a doorway."
               % (cfg.STOOP_STEPS, rise, cfg.STOOP_RISE)),
    )


# ========================================================= 19 interior wall
#: Shared by all three interior pieces, so a partition cannot end up resting on
#: a foundation pad in one part and a floor slab in another.
#:
#: ``floor_top`` only, deliberately. An exterior wall may bear on a foundation
#: pad because it stands on the building line, where the pad is. A partition
#: stands *inside* the building, where there is a floor; one bearing directly on
#: a foundation is a partition outside the floor plate, which is either a
#: misplaced wall or a missing slab. Both are worth an error, and neither is
#: visible in a picture.
INTERIOR_SUPPORT = dict(requires_support=True, rests_on=["floor_top"],
                        support_axis="z", may_float=False)


def wall_interior():
    """A partition. Divides an interior; carries no roof and no weather.

    Same thickness as an exterior wall, which is a decision recorded in
    ``docs/decisions/0009-interior-pieces.md``: GRID_XY is the wall thickness,
    so a thinner partition would force the placement lattice finer and weaken
    the off-grid check for every piece in the kit.
    """
    s = partition_shell()
    skirting(s, 0, M, axis=0)
    return dict(
        asset_id="tsr:shell/wall.interior.4m",
        name="Interior Wall 4 m",
        # Role is "wall", not a new "partition" role, and that is deliberate.
        # semantic_role decides which rules apply, and every rule that applies
        # to a wall applies to a partition unchanged -- including
        # BASE_PIVOT_ROLES, the check that catches a floating pivot. A new role
        # would have quietly exempted these three pieces from it. What actually
        # differs about a partition is what it may rest on, and that belongs in
        # `support`, where it is stated below.
        category="structure", semantic_role="wall",
        tags=["modular", "interior", "partition"],
        solid=s, mesh=surface_from_boxset(s, "M_Plaster"),
        materials=slots("M_Plaster"),
        connectors=wall_connectors(thickness=IT),
        pivot_convention="bay_min_corner_on_base",
        support=INTERIOR_SUPPORT,
        clearance_boxes=[],
        notes=("Runs the full bay along +X, %0.2f m thick along +Y. Seams to "
               "other partitions on the bay grid. It cannot terminate flush "
               "against a *perimeter* wall: that wall's innermost surface is "
               "its plinth, at derived.perimeter_inner_face_inset from the bay "
               "line, which is not a whole number of grid units -- see "
               "derived.perimeter_inset_is_on_grid." % IT),
    )


# ====================================================== 20 interior doorway
def wall_interior_doorway():
    """A partition with a door in it. The piece an interior room is entered by.

    Without this, an interior room could be closed and not entered: the L corner
    seals a corner without overlapping anything, but carries no opening, so two
    of them box in a room with no way in. The benchmark repair hit exactly that
    and settled for an alcove open on one side.

    The aperture is the same ``DOOR_WIDTH x DOOR_HEIGHT`` as the exterior
    doorway, on purpose -- ``door.leaf.1m2`` hangs in either without a second
    leaf asset, and the reference-character checks that already govern the
    exterior door govern this one unchanged.
    """
    s = partition_shell()
    x0 = (M - cfg.DOOR_WIDTH) / 2
    x1 = x0 + cfg.DOOR_WIDTH
    skirting(s, 0, x0, axis=0)
    skirting(s, x1, M, axis=0)
    # carve_aperture, not subtract: the hole has to be *recorded* as a door, or
    # traversal, collision and blockage have nothing to test against.
    s.carve_aperture("door", "door",
                     (x0, -0.01, 0), (x1, IT + 0.01, cfg.DOOR_HEIGHT),
                     axis=1, traversable=True)
    return dict(
        asset_id="tsr:shell/wall.interior.doorway.4m",
        name="Interior Wall Doorway 4 m",
        category="structure", semantic_role="wall_opening",
        tags=["modular", "interior", "partition", "traversable"],
        solid=s, mesh=surface_from_boxset(s, "M_Plaster"),
        materials=slots("M_Plaster"),
        connectors=wall_connectors(thickness=IT, extra=[
            conn("jamb_neg_y", "opening_jamb", (M / 2, IT / 2, cfg.DOOR_HEIGHT / 2),
                 (0, -1, 0), (1, 0, 0), role="hinge_receiver",
                 notes="mid-reveal mount point; a leaf mated here sits centred "
                       "in the wall thickness rather than surface-hung"),
            conn("jamb_pos_y", "opening_jamb", (M / 2, IT / 2, cfg.DOOR_HEIGHT / 2),
                 (0, 1, 0), (1, 0, 0), role="hinge_receiver",
                 notes="same point, opposite facing, for a leaf approaching from +Y"),
        ]),
        pivot_convention="bay_min_corner_on_base",
        support=INTERIOR_SUPPORT,
        clearance_boxes=[
            [x0, -cfg.DOOR_SWING_CLEARANCE, 0, x1, 0, cfg.DOOR_HEIGHT],
            [x0, IT, 0, x1, IT + cfg.DOOR_SWING_CLEARANCE, cfg.DOOR_HEIGHT],
        ],
        notes=("Aperture is %.2f x %.2f m, identical to the exterior doorway so "
               "the same leaf fits. Both swing volumes must stay empty; indoors "
               "that is the constraint people actually break, because furniture "
               "goes against walls." % (cfg.DOOR_WIDTH, cfg.DOOR_HEIGHT)),
    )


# ======================================================== 21 interior corner
def wall_interior_corner():
    """L piece turning a partition through 90 degrees without overlap.

    The same argument as ``wall.corner.4m`` and for the same reason -- two
    partitions meeting at a corner overlap in a thickness-squared column, which
    is a real intersection and is correctly refused. See
    ``docs/decisions/0006-corner-piece-is-an-L.md``.

    Solid, with no opening, and that is a constraint rather than an omission: a
    room whose partition sides are one module each is closed by a single corner
    and cannot be entered. Give it two modules on one side and the second module
    is a ``wall.interior.doorway.4m``. Stated here so it is read rather than
    discovered.
    """
    s = BoxSet.from_box((0, 0, 0), (M, IT, H))
    s.add((0, 0, 0), (IT, M, H))
    # Groove only the legs, not the fused square where they meet: a groove
    # carried around the inside of the corner cuts the return face of the other
    # leg and leaves a notch at the junction.
    skirting(s, IT, M, axis=0, thickness=IT)
    skirting(s, IT, M, axis=1, thickness=IT)
    return dict(
        asset_id="tsr:shell/wall.interior.corner.4m",
        name="Interior Wall Corner 4 m",
        category="structure", semantic_role="corner",
        tags=["modular", "interior", "partition", "junction"],
        solid=s, mesh=surface_from_boxset(s, "M_Plaster"),
        materials=slots("M_Plaster"),
        connectors=[
            conn("base", "wall_base", (M / 2, IT / 2, 0), (0, 0, -1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, IT / 2), role="support",
                 required=True),
            conn("base_y", "wall_base", (IT / 2, M / 2, 0), (0, 0, -1), (0, 1, 0),
                 mode="surface", extent_half=(IT / 2, M / 2), role="support"),
            conn("top_x", "wall_top", (M / 2, IT / 2, H), (0, 0, 1), (1, 0, 0),
                 mode="surface", extent_half=(M / 2, IT / 2), role="bearing"),
            conn("top_y", "wall_top", (IT / 2, M / 2, H), (0, 0, 1), (0, 1, 0),
                 mode="surface", extent_half=(IT / 2, M / 2), role="bearing"),
            conn("edge_pos_x", "wall_edge", (M, IT / 2, H / 2), (1, 0, 0), (0, 0, 1),
                 role="seam"),
            conn("edge_pos_y", "wall_edge", (IT / 2, M, H / 2), (0, 1, 0), (0, 0, 1),
                 role="seam"),
        ],
        pivot_convention="bay_min_corner_on_base",
        support=INTERIOR_SUPPORT,
        clearance_boxes=[],
        notes=("Occupies the -X and -Y edges of its bay; seams out along +X and "
               "+Y. Solid: a one-module-per-side interior room closed by this "
               "piece alone has no way in, which is a property of the room, not "
               "a defect in the piece."),
    )


PARTS = [
    foundation_pad, floor_slab, wall_straight, wall_corner, wall_doorway,
    door_leaf, wall_window, window_leaf, roof_panel, roof_ridge,
    prop_crate, prop_workbench,
    stair_straight, floor_opening, beam, railing, column, stair_stoop,
    wall_interior, wall_interior_doorway, wall_interior_corner,
]
