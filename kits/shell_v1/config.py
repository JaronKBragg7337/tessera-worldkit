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

# ---------------------------------------------------------- interior walls
# A partition is the same thickness as an exterior wall, and that is a decision
# rather than an oversight. GRID_XY *is* the wall thickness, because a wall
# rotated 90 degrees is offset from its bay line by its own thickness. A thinner
# partition would force the lattice down to divide it as well, and a finer
# lattice catches fewer off-grid placements -- a wall half a thickness out of
# position would start passing. Trading a working check for a visual nicety is
# the wrong trade. See docs/decisions/0009-interior-pieces.md.
#
# It is a named constant anyway, so that anyone who does diverge it gets
# CFG_INTERIOR_THICKNESS_OFF_GRID instead of a kit that silently stops seaming.
INTERIOR_WALL_THICKNESS = WALL_THICKNESS

# A partition is finished with a recessed skirting groove, not the exterior
# plinth. The plinth stands PLINTH_PROUD of the wall face to throw water clear,
# which indoors only stops furniture standing flush against the wall. A groove
# does the same visual job and leaves the interior face flat.
INTERIOR_SKIRT_HEIGHT = 0.10
INTERIOR_SKIRT_GROOVE = 0.02

# A partition cannot meet a perimeter wall directly because the perimeter
# plinth stands PLINTH_PROUD past the wall face. The junction trim starts at the
# inner wall face and ends on the next MODULE line, so its length is one bay
# less the wall-face offset. It rebates only its bottom PLINTH_HEIGHT by
# PLINTH_PROUD: above the plinth it touches the wall body; below it touches the
# plinth face. The receiver sits half a partition thickness from the end of a
# perimeter module, inside the flat panel border, and mating it puts the trim's
# bay-min pivot exactly one wall thickness from the perimeter bay line.
WALL_JUNCTION_TRIM_LENGTH = MODULE - GRID_XY
WALL_JUNCTION_RECEIVER_OFFSET = INTERIOR_WALL_THICKNESS / 2

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

# ------------------------------------------------------------- traversal
# A storey is floor-top to floor-top: the slab above sits on the wall top, so
# the rise is the wall height plus one slab.
STOREY_HEIGHT = FLOOR_THICKNESS + WALL_HEIGHT      # 3.20 m

STAIR_RISE = 0.20          # per step
STAIR_GOING = 0.25         # tread depth
STAIR_WIDTH = 1.20         # matches DOOR_WIDTH so a stair fits a doorway
STAIR_HEADROOM = 2.00      # clear height measured vertically above each nosing
STAIR_STRINGER = 0.06

# A stairwell opening in the floor above. Wider than the stair so a character
# does not clip the edge, and long enough that headroom is clear where it
# matters.
OPENING_WIDTH = STAIR_WIDTH + 0.30
OPENING_LENGTH = 2.60

BEAM_DEPTH = 0.30        # keeps COLUMN_HEIGHT on the Z grid
BEAM_WIDTH = 0.24

# A column carries a beam whose top finishes flush with the wall top, so the
# floor above lands on one continuous plane. That makes the column exactly one
# beam shorter than a wall -- an invariant, not a coincidence, and validate()
# enforces it.
COLUMN_HEIGHT = WALL_HEIGHT - BEAM_DEPTH
#: Wide enough that a beam ending on the grid line still lands on it, and a
#: whole number of grid units so the column itself is placeable.
COLUMN_SIZE = 0.40

RAILING_HEIGHT = 1.10
RAILING_POST = 0.07
RAILING_RAIL = 0.05
RAILING_POSTS = 5

# An entrance stoop. The floor sits FOUNDATION_THICKNESS + FLOOR_THICKNESS above
# the terrain, which is more than a character can step up in one go, so without
# this a doorway is reachable only in theory. The reachability solver found that
# in the finished workshop -- the door was open and nobody could get in.
STOOP_RISE = FOUNDATION_THICKNESS + FLOOR_THICKNESS   # 0.50 m
STOOP_STEPS = 2
STOOP_GOING = 0.30        # 2 steps -> 0.60 m deep, a whole number of Z-grid units
STOOP_WIDTH = DOOR_WIDTH

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
#: The tallest single rise a character can walk up without a jump, and the limit
#: the navigation solver uses, so the kit and the solver cannot disagree. 45 cm
#: matches Unreal's default MaxStepHeight and Unity's usual Step Offset for a
#: controller this size.
CHARACTER_STEP_UP = 0.45
#: What a *stoop* is allowed to ask, which is much less. The runtime limit is
#: what a character can survive; this is what a person would call a step.
COMFORTABLE_STEP_UP = 0.25

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
        # How far the *innermost surface* of a perimeter wall stands in from its
        # bay line. Note that this is the plinth, not the wall face: the plinth
        # stands PLINTH_PROUD past the slab on both faces, so the first solid a
        # partition meets is 0.23 in, not 0.20.
        #
        # Read the next number before running a partition up to a perimeter
        # wall. This inset is deliberately published because it is NOT a whole
        # number of GRID_XY units, and that has a consequence: a module-length
        # partition placed on the grid cannot terminate flush against a
        # perimeter wall. It either ends at 0.20 and drives its bottom
        # PLINTH_HEIGHT through the plinth (TSR_LAYOUT_INTERSECTION, about
        # 0.001 m3 -- small enough to look like noise and real enough to
        # z-fight), or it stops a grid step short and leaves a slot.
        #
        # A regular partition still may not start here directly. Use
        # wall.junction.trim.3m8, whose lower end is rebated to this inset and
        # whose far end lands on the next module line. See decision 0010.
        "perimeter_inner_face_inset": WALL_THICKNESS + PLINTH_PROUD,
        "perimeter_inset_is_on_grid": abs(
            (WALL_THICKNESS + PLINTH_PROUD) / GRID_XY
            - round((WALL_THICKNESS + PLINTH_PROUD) / GRID_XY)) < 1e-9,
        "partition_thickness": INTERIOR_WALL_THICKNESS,
        "wall_junction_trim_length": WALL_JUNCTION_TRIM_LENGTH,
        "wall_junction_rebate": PLINTH_PROUD,
        "wall_junction_origin_inset": (
            WALL_JUNCTION_RECEIVER_OFFSET + INTERIOR_WALL_THICKNESS / 2
        ),
        "storey_height": STOREY_HEIGHT,
        "second_floor_top_z": floor_top + STOREY_HEIGHT,
        "stair_steps": round(STOREY_HEIGHT / STAIR_RISE),
        "stair_run": round(STOREY_HEIGHT / STAIR_RISE) * STAIR_GOING,
        "stair_angle_degrees": round(__import__("math").degrees(
            __import__("math").atan2(STAIR_RISE, STAIR_GOING)), 3),
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

    # ---- interior walls -----------------------------------------------
    # The grid lattice has to divide *every* wall thickness in the kit, not just
    # the exterior one. A partition rotated 90 degrees is offset from its bay
    # line by its own thickness, exactly as an exterior wall is; if the lattice
    # does not divide it, every correctly placed partition reports off-grid and
    # the only way to silence that is to make the lattice finer, which weakens
    # the check for everything else.
    if abs(INTERIOR_WALL_THICKNESS / GRID_XY
           - round(INTERIOR_WALL_THICKNESS / GRID_XY)) > 1e-9:
        bad("CFG_INTERIOR_THICKNESS_OFF_GRID",
            "interior wall thickness is not a multiple of the snap grid",
            "INTERIOR_WALL_THICKNESS / %.3f to be an integer" % GRID_XY,
            INTERIOR_WALL_THICKNESS / GRID_XY)
    if INTERIOR_SKIRT_GROOVE * 2 >= INTERIOR_WALL_THICKNESS:
        bad("CFG_INTERIOR_GROOVE_TOO_DEEP",
            "skirting grooves cut from both faces would meet inside the partition",
            "< %.3f" % (INTERIOR_WALL_THICKNESS / 2), INTERIOR_SKIRT_GROOVE)
    if INTERIOR_SKIRT_HEIGHT + INTERIOR_SKIRT_GROOVE >= WALL_HEIGHT:
        bad("CFG_INTERIOR_SKIRT_TOO_TALL",
            "the skirting groove runs off the top of the partition",
            "INTERIOR_SKIRT_HEIGHT + INTERIOR_SKIRT_GROOVE < %.2f" % WALL_HEIGHT,
            INTERIOR_SKIRT_HEIGHT + INTERIOR_SKIRT_GROOVE)
    if (abs(WALL_JUNCTION_TRIM_LENGTH / GRID_XY
            - round(WALL_JUNCTION_TRIM_LENGTH / GRID_XY)) > 1e-9):
        bad("CFG_WALL_JUNCTION_LENGTH_OFF_GRID",
            "wall junction trim length is not a whole number of grid steps",
            "WALL_JUNCTION_TRIM_LENGTH / %.3f to be an integer" % GRID_XY,
            WALL_JUNCTION_TRIM_LENGTH / GRID_XY)
    if WALL_JUNCTION_TRIM_LENGTH <= PLINTH_PROUD:
        bad("CFG_WALL_JUNCTION_CONSUMED_BY_REBATE",
            "the plinth rebate consumes the whole junction trim",
            "> %.3f" % PLINTH_PROUD, WALL_JUNCTION_TRIM_LENGTH)
    junction_origin = (
        WALL_JUNCTION_RECEIVER_OFFSET + INTERIOR_WALL_THICKNESS / 2
    )
    if abs(junction_origin / GRID_XY - round(junction_origin / GRID_XY)) > 1e-9:
        bad("CFG_WALL_JUNCTION_ORIGIN_OFF_GRID",
            "mating a junction trim would put its pivot off the XY grid",
            "(WALL_JUNCTION_RECEIVER_OFFSET + "
            "INTERIOR_WALL_THICKNESS / 2) / %.3f to be an integer" % GRID_XY,
            junction_origin / GRID_XY)
    junction_far = junction_origin + WALL_JUNCTION_TRIM_LENGTH
    if abs(junction_far / MODULE - round(junction_far / MODULE)) > 1e-9:
        bad("CFG_WALL_JUNCTION_END_OFF_MODULE",
            "the far end of a mated junction trim misses the next bay line",
            "(junction origin + WALL_JUNCTION_TRIM_LENGTH) / MODULE "
            "to be an integer",
            junction_far / MODULE)
    if WALL_JUNCTION_RECEIVER_OFFSET >= MODULE / 2:
        bad("CFG_WALL_JUNCTION_RECEIVER_OUTSIDE_BAY",
            "the pair of junction receivers do not fit inside one wall bay",
            "< %.3f" % (MODULE / 2), WALL_JUNCTION_RECEIVER_OFFSET)
    # An interior doorway carves the same aperture as an exterior one out of a
    # module-long partition, leaving a pier each side. A pier thinner than the
    # wall it is part of is a modelling error, not a slim design: it reads as a
    # sliver, and at 90-degree yaw it is the piece that has to carry the head.
    interior_pier = (MODULE - DOOR_WIDTH) / 2
    if interior_pier < INTERIOR_WALL_THICKNESS:
        bad("CFG_INTERIOR_DOOR_PIER_TOO_NARROW",
            "the piers beside an interior doorway are thinner than the wall itself",
            ">= %.2f" % INTERIOR_WALL_THICKNESS, interior_pier)

    # ---- traversal ----------------------------------------------------
    if STOOP_RISE / STOOP_STEPS > COMFORTABLE_STEP_UP + 1e-9:
        bad("CFG_STOOP_STEP_TOO_TALL",
            "the entrance stoop asks the character to step higher than it can",
            "<= %.2f per step" % COMFORTABLE_STEP_UP, STOOP_RISE / STOOP_STEPS)
    if abs(STOOP_RISE - (FOUNDATION_THICKNESS + FLOOR_THICKNESS)) > 1e-9:
        bad("CFG_STOOP_WRONG_HEIGHT",
            "the stoop does not land level with the floor inside",
            FOUNDATION_THICKNESS + FLOOR_THICKNESS, STOOP_RISE)
    if STOOP_RISE <= CHARACTER_STEP_UP:
        bad("CFG_STOOP_POINTLESS",
            "the floor is within one step of the ground, so the stoop is not "
            "needed and its presence hides that fact",
            "> %.2f" % CHARACTER_STEP_UP, STOOP_RISE)
    if STAIR_RISE > COMFORTABLE_STEP_UP + 1e-9:
        bad("CFG_STAIR_STEP_TOO_TALL",
            "stair steps are taller than the character can climb",
            "<= %.2f" % COMFORTABLE_STEP_UP, STAIR_RISE)
    steps = STOREY_HEIGHT / STAIR_RISE
    if abs(steps - round(steps)) > 1e-9:
        bad("CFG_STAIR_DOES_NOT_REACH",
            "the stair does not land exactly on the floor above",
            "STOREY_HEIGHT / STAIR_RISE to be a whole number of steps", steps)
    run = round(steps) * STAIR_GOING
    if abs(run / MODULE - round(run / MODULE)) > 1e-9:
        bad("CFG_STAIR_RUN_OFF_MODULE",
            "the stair run is not a whole number of bays, so it cannot be placed "
            "on the grid it has to seam with",
            "%.3f m run to be a multiple of MODULE" % run, run / MODULE)
    if STAIR_WIDTH < 2 * CHARACTER_RADIUS:
        bad("CFG_STAIR_TOO_NARROW", "the stair is narrower than the character",
            ">= %.2f" % (2 * CHARACTER_RADIUS), STAIR_WIDTH)
    if STAIR_HEADROOM < CHARACTER_HEIGHT:
        bad("CFG_STAIR_HEADROOM", "a character cannot stand up on the stair",
            ">= %.2f" % CHARACTER_HEIGHT, STAIR_HEADROOM)
    # Where the floor above still covers the flight, a character must be able to
    # stand up. The stair is only low enough for that over its first
    # (headroom-limited) stretch, so the opening has to be at least as long as
    # the rest of the run. Getting this wrong produces a stairwell you crack
    # your head in, which no visual check ever reveals.
    covered_run = ((STOREY_HEIGHT - FLOOR_THICKNESS - CHARACTER_HEIGHT)
                   / STAIR_RISE) * STAIR_GOING
    needed = round(STOREY_HEIGHT / STAIR_RISE) * STAIR_GOING - covered_run
    if OPENING_LENGTH < needed - 1e-9:
        bad("CFG_OPENING_TOO_SHORT",
            "the stairwell opening is too short for a character to stand up on "
            "the upper part of the flight",
            ">= %.2f m" % needed, OPENING_LENGTH)
    if abs(COLUMN_HEIGHT + BEAM_DEPTH - WALL_HEIGHT) > 1e-9:
        bad("CFG_COLUMN_BEAM_MISMATCH",
            "a column plus its beam does not finish level with the wall top, so "
            "the floor above would rest on two different planes",
            WALL_HEIGHT, COLUMN_HEIGHT + BEAM_DEPTH)
    if abs(COLUMN_SIZE / GRID_XY - round(COLUMN_SIZE / GRID_XY)) > 1e-9:
        bad("CFG_COLUMN_OFF_GRID", "column size is not a whole number of grid units",
            "COLUMN_SIZE / %.2f to be an integer" % GRID_XY, COLUMN_SIZE / GRID_XY)
    if OPENING_WIDTH <= STAIR_WIDTH:
        bad("CFG_OPENING_TOO_TIGHT",
            "the stairwell opening is no wider than the stair, so a character "
            "would clip its edge",
            "> %.2f" % STAIR_WIDTH, OPENING_WIDTH)
    # The classic rule of thumb: 2*rise + going should land near 0.63 m.
    comfort = 2 * STAIR_RISE + STAIR_GOING
    if not 0.55 <= comfort <= 0.70:
        bad("CFG_STAIR_UNCOMFORTABLE",
            "step proportions are outside the usual comfortable range",
            "0.55 <= 2*rise + going <= 0.70", comfort)
    return problems
