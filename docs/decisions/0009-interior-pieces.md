# 0009 — Interior pieces are walls, at wall thickness

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

[`0006`](0006-corner-piece-is-an-L.md) made a rectangular *perimeter* close
without overlapping geometry, using an L corner. It gave the kit no way to close
an interior room, because the L carries no opening: two of them box in a room
with no door. `examples/safehouse` says so in a comment and settles for an
alcove open on one side, and the constrained-agent benchmark could not do better.

M3 adds three pieces — `wall.interior.4m`, `wall.interior.doorway.4m`,
`wall.interior.corner.4m` — so a room inside a building can be both closed and
entered. Four things had to be decided to do that, and three of them looked like
free choices until they were costed.

## Decision

### 1. A partition is the same thickness as an exterior wall

`INTERIOR_WALL_THICKNESS == WALL_THICKNESS == 0.20`.

A thinner partition is more realistic and it is the obvious first instinct. It
costs more than it looks.

`GRID_XY` **is** the wall thickness, and that is not a coincidence — a wall
rotated 90 degrees is offset from its bay line by its own thickness, so a
lattice that divides only the module reports every correctly placed side wall as
off-grid. That was a real bug in the first assembly and the comment recording it
is still in `config.py`.

A 0.10 m partition therefore forces `GRID_XY` down to 0.10. Nothing existing
breaks — a finer lattice is strictly more permissive — and that is exactly the
problem. `TSR_LAYOUT_OFF_GRID` exists to catch a wall that is not on its bay
line. Halve the lattice and a wall 0.10 m out of position starts passing. We
would be trading a working check for a visual nicety, which is the same trade as
deleting the check.

The constant exists anyway, with `CFG_INTERIOR_THICKNESS_OFF_GRID` behind it, so
that anyone who does diverge it gets a config error rather than a kit that
silently stops seaming.

### 2. Their `semantic_role` is `wall`, `wall_opening` and `corner`

Not new `partition*` roles. `semantic_role` decides which rules apply, and
`BASE_PIVOT_ROLES` — the check that catches a pivot off its own base, the single
most common cause of a floating object — is keyed on it. A new role would have
quietly exempted all three new pieces from that check on the day they were
added, and nothing would have reported it.

What genuinely differs about a partition is what it may rest on. That belongs in
`placement.support.rests_on`, and it is `["floor_top"]` only: an exterior wall
may bear on a foundation pad because it stands on the building line, where the
pad is; a partition standing on a foundation is a partition outside the floor
plate, which is a misplaced wall or a missing slab. Both are worth an error.

This also keeps `tessera.asset/1` unchanged, which M3 asks for.

### 3. The interior corner is solid

Consistent with 0006 and for the same reason: two partitions meeting at a corner
overlap in a `thickness × thickness` column, which is a real intersection.

It carries no opening, so a room whose partition sides are one module each is
closed by corners alone and **cannot be entered**. That is a property of the
room, not a defect in the piece: a corner consumes one module of each side it
turns, so a door needs a side of at least three modules. Same shape of
constraint as 0006's "at least 3 bays per side", restated for interiors, and
asserted by `test_the_interior_corner_carries_no_opening`.

### 4. A partition run may not terminate against a perimeter wall — yet

This one was not decided. It was discovered, by building the obvious version of
the example first: a room partitioned off the corner of a 12 × 12 m shell,
reusing two perimeter walls. It produced four `TSR_LAYOUT_INTERSECTION` errors
of **0.0011 m³** each — small enough to read as floating-point noise and real
enough to z-fight.

The cause: a perimeter wall's innermost surface is not its face. `wall_shell`
stands the plinth `PLINTH_PROUD` past the slab on *both* faces, so the first
solid a partition meets is `WALL_THICKNESS + PLINTH_PROUD` = **0.23 m** in from
the bay line — and 0.23 is not a whole number of `GRID_XY` units.

So a module-length partition placed on the grid cannot finish flush against a
perimeter wall. It ends at 0.20 and drives its bottom `PLINTH_HEIGHT` through
the plinth, or it stops a grid step short and leaves a 0.17 m slot. Every
workaround considered made something else worse:

- **Rebate the partition ends by `PLINTH_PROUD`.** Clears the plinth, and puts a
  60 mm × 180 mm see-through slot at every partition-to-partition seam.
- **Hand the ends — tongue one side, rebate the other.** Works when a run starts
  at a corner and ends at a perimeter; fails for a run crossing between two
  perimeter walls, and makes "which way round does this piece go" a thing an
  agent has to get right. That is the correction loop this kit exists to delete.
- **Shorten the partition to `MODULE − PLINTH_PROUD`.** A 3.97 m "4 m wall",
  which is the lie 0006 rejected.
- **Drop the plinth, or make it flush.** Fixes it, and silently changes the
  geometry of five assets nobody asked to touch.
- **Exclude the plinth from the intersection test.** Weakening a rule to make a
  scene pass.

None of those is right, and the piece that *is* right — a wall-to-wall junction
trim — is already on the M3 list and is not a partition. So the number is
published as `derived.perimeter_inner_face_inset`, alongside
`derived.perimeter_inset_is_on_grid` (`false`), and
`examples/interior_rooms/` builds a **free-standing** room with a corridor all
the way around it, where no such junction exists anywhere.

## Consequences

- Three new assets, 21 in the kit, all passing the same 19 asset rules unchanged.
- `door.leaf.1m2` hangs in an interior doorway without a second leaf asset,
  because the aperture is the identical `DOOR_WIDTH × DOOR_HEIGHT`. Asserted.
- `examples/interior_rooms/` assembles 58 instances with 0 manual corrections
  and validates with 0 errors and 0 warnings, proving three routes by flood fill.
- Swapping the one interior doorway for a solid interior wall makes the room
  unreachable and raises `TSR_LAYOUT_UNREACHABLE`. Without that control, "the
  room can be entered" would only be evidence that a flood fill can find *some*
  route, which it can — around the outside of the room.
- An interior room in the corner of a building, reusing its perimeter walls,
  still cannot be built. That is the remaining gap and it is a junction piece,
  not a partition.
- The plinth's proud return on the *inside* face of an exterior wall is now
  known to be load-bearing on layout. Worth revisiting when the junction trim is
  designed, rather than changing now to suit one example.

## Resolution

The final gap above was closed by
[`0010`](0010-wall-junction-bridges-to-the-bay-line.md). The free-standing
example was replaced by a room that reuses two perimeter walls; the historical
finding and rejected workarounds remain here because they are the reason the
junction has its dedicated geometry and connector pair.
