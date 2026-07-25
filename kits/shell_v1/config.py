"""Every tunable dimension of the Shell v1 kit, in one place.

SPDX-License-Identifier: 0BSD

Carried forward from ModKit's ``kit_config.py``, which got this right: no
geometry file may contain a hard-coded dimension. Improved in two ways --
:func:`validate` returns structured diagnostics instead of strings, and
:func:`derived` exposes the numbers an agent needs (stack heights, spans) so it
never has to add them up itself and get it wrong.

Units are metres throughout. See ``tessera.units`` for the coordinate space.
"""
from __future__ import annotations

KIT_ID = "shell_v1"
KIT_VERSION = "1.0.0"

# ------------------------------------------------------------------- grid
MODULE = 4.0              # length of one modular bay
WALL_HEIGHT = 3.0
WALL_THICKNESS = 0.20
FLOOR_THICKNESS = 0.20
FOUNDATION_THICKNESS = 0.30

# The translation lattice must divide BOTH the bay module and the wall
# thickness. A wall rotated 90 degrees is offset from its bay line by its own
# thickness, so a lattice that divides only the module reports every correctly
# placed side wall as off-grid. This caught a real bug in the first assembly.
GRID_XY = WALL_THICKNESS  # 0.20 m: divides MODULE (x20) and WALL_THICKNESS (x1)
GRID_Z = 0.05
YAW_STEP = 90.0           # modular pieces are 90-degree pieces, full stop

# --------------------------------------------------------------- openings
DOOR_WIDTH = 1.20
DOOR_HEIGHT = 2.20
DOOR_LEAF_GAP = 0.02      # clearance around the leaf inside the aperture
WINDOW_WIDTH = 1.80
WINDOW_HEIGHT = 1.20
WINDOW_SILL = 1.00
DOOR_SWING_CLEARANCE = 1.10   # depth of the volume that must stay free

# --------------------------------------------------------------- detailing
PANEL_INSET = 0.25        # border between the wall edge and the recessed bay
PANEL_DEPTH = 0.04
TILE_GROOVE = 0.05
TILE_GROOVE_DEPTH = 0.03
PLINTH_HEIGHT = 0.18
PLINTH_PROUD = 0.03       # how far the plinth stands proud of the wall face

# ------------------------------------------------------------------- roof
ROOF_RUN = 6.0            # horizontal distance from bearing to ridge
ROOF_PITCH = 0.42         # rise per unit run  (22.8 degrees)
ROOF_THICKNESS = 0.18
ROOF_OVERHANG = 0.30      # past the outer wall face
RIDGE_HALF_WIDTH = 0.28
RIDGE_HEIGHT = 0.16

# ------------------------------------------------------------------ props
CRATE_SIZE = 0.60
BENCH_LENGTH = 1.80
BENCH_DEPTH = 0.70
BENCH_HEIGHT = 0.90
BENCH_TOP_THICKNESS = 0.08
BENCH_LEG = 0.09

# ------------------------------------------------------ reference character
# Used to decide whether an aperture is actually walkable. A doorway that a
# validator calls "open" but the reference character cannot fit through is not
# open. Approximately an adult human.
CHARACTER_RADIUS = 0.35
CHARACTER_HEIGHT = 1.80

# -------------------------------------------------------------------- LODs
LOD_SCREEN_SIZES = (1.0, 0.45, 0.18)


def derived() -> dict:
    """Numbers an agent would otherwise have to compute, and get wrong."""
    floor_top = FOUNDATION_THICKNESS + FLOOR_THICKNESS
    return {
        "foundation_top_z": FOUNDATION_THICKNESS,
        "floor_top_z": floor_top,
        "wall_base_z": floor_top,
        "wall_top_z": floor_top + WALL_HEIGHT,
        "roof_bearing_z": floor_top + WALL_HEIGHT,
        "ridge_rise": ROOF_PITCH * ROOF_RUN,
        "ridge_z": floor_top + WALL_HEIGHT + ROOF_PITCH * ROOF_RUN,
        "building_span_for_one_gable": 2 * ROOF_RUN,
        "roof_pitch_degrees": round(__import__("math").degrees(
            __import__("math").atan(ROOF_PITCH)), 3),
        "door_head_z": DOOR_HEIGHT,
        "window_head_z": WINDOW_SILL + WINDOW_HEIGHT,
        "bay_module": MODULE,
    }


def validate() -> list:
    """Refuse parameter combinations that would generate broken geometry."""
    problems = []

    def bad(code, message, expected, actual):
        problems.append({"code": code, "message": message,
                         "expected": expected, "actual": actual})

    if DOOR_HEIGHT >= WALL_HEIGHT:
        bad("CFG_DOOR_TOO_TALL", "door head is at or above the wall top",
            "DOOR_HEIGHT < %.2f" % WALL_HEIGHT, DOOR_HEIGHT)
    if WINDOW_SILL + WINDOW_HEIGHT >= WALL_HEIGHT:
        bad("CFG_WINDOW_TOO_TALL", "window head is at or above the wall top",
            "WINDOW_SILL + WINDOW_HEIGHT < %.2f" % WALL_HEIGHT,
            WINDOW_SILL + WINDOW_HEIGHT)
    if DOOR_WIDTH + 2 * PANEL_INSET >= MODULE:
        bad("CFG_DOOR_TOO_WIDE", "door plus panel insets exceed the bay",
            "< %.2f" % MODULE, DOOR_WIDTH + 2 * PANEL_INSET)
    if DOOR_WIDTH < 2 * CHARACTER_RADIUS:
        bad("CFG_DOOR_IMPASSABLE",
            "door is narrower than the reference character",
            ">= %.2f" % (2 * CHARACTER_RADIUS), DOOR_WIDTH)
    if DOOR_HEIGHT < CHARACTER_HEIGHT:
        bad("CFG_DOOR_TOO_LOW",
            "door is shorter than the reference character",
            ">= %.2f" % CHARACTER_HEIGHT, DOOR_HEIGHT)
    if PANEL_DEPTH * 2 >= WALL_THICKNESS:
        bad("CFG_PANEL_TOO_DEEP", "recessed panels would meet inside the wall",
            "< %.3f" % (WALL_THICKNESS / 2), PANEL_DEPTH)
    if ROOF_THICKNESS <= TILE_GROOVE_DEPTH:
        bad("CFG_ROOF_TOO_THIN", "roof is thinner than its own detailing",
            "> %.3f" % TILE_GROOVE_DEPTH, ROOF_THICKNESS)
    if ROOF_OVERHANG <= WALL_THICKNESS:
        bad("CFG_NO_OVERHANG", "roof does not project past the wall it sits on",
            "> %.2f" % WALL_THICKNESS, ROOF_OVERHANG)
    if abs(MODULE / GRID_XY - round(MODULE / GRID_XY)) > 1e-9:
        bad("CFG_MODULE_OFF_GRID", "bay module is not a multiple of the snap grid",
            "MODULE / %.3f to be an integer" % GRID_XY, MODULE / GRID_XY)
    if abs(WALL_THICKNESS / GRID_XY - round(WALL_THICKNESS / GRID_XY)) > 1e-9:
        bad("CFG_THICKNESS_OFF_GRID",
            "wall thickness is not a multiple of the snap grid",
            "WALL_THICKNESS / %.3f to be an integer" % GRID_XY,
            WALL_THICKNESS / GRID_XY)
    if abs(WALL_HEIGHT / GRID_Z - round(WALL_HEIGHT / GRID_Z)) > 1e-9:
        bad("CFG_HEIGHT_OFF_GRID", "wall height is not a multiple of the Z grid",
            "WALL_HEIGHT / %.3f to be an integer" % GRID_Z, WALL_HEIGHT / GRID_Z)
    return problems
