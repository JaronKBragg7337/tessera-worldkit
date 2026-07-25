# 0010 — A wall junction bridges from the perimeter face to the bay line

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

Decision [`0009`](0009-interior-pieces.md) found that a regular partition cannot
terminate against a perimeter wall. The wall body ends 0.20 m from its bay line,
but its plinth projects another 0.03 m into the room for its lower 0.18 m. A
partition started at the body face therefore overlaps the plinth by:

```
0.03 × 0.20 × 0.18 = 0.00108 m³
```

That is small enough to dismiss as numerical noise and large enough to be real
geometry. Moving the partition to the next 0.20 m grid step avoids the overlap
and leaves a 0.17 m slot. Rebating every partition end creates holes at ordinary
partition seams, while changing the plinth changes existing perimeter assets to
solve an interior problem.

## Decision

Add one dedicated asset: `wall.junction.trim.3m8`.

### It is 3.80 m long on purpose

The trim begins at the perimeter wall face, 0.20 m from the bay line, and ends
at the next 4.00 m bay line:

```
WALL_JUNCTION_TRIM_LENGTH = MODULE - GRID_XY = 3.80 m
```

This is not a shortened “4 m wall.” Its name, measured bounds and purpose all
say 3.8 m. A normal 4 m interior wall or doorway continues from its far end.
Two opposing trims also leave a whole-module span between perimeter walls.

### Only the lower perimeter end is rebated

For `z < PLINTH_HEIGHT`, the first `PLINTH_PROUD` of the trim is absent. That
lower face touches the plinth at 0.23 m. Above it, the trim begins at the 0.20 m
wall-body face. The ordinary partition end is unchanged.

### Dedicated connectors solve the orientation

Perimeter straight, doorway and window walls expose `wall_face` receivers on
both faces, near both ends of the bay. The receiver is half a partition
thickness from the bay end, inside the flat panel border rather than the
recessed panel. `wall.junction` on the rebated trim end mates only to
`wall_face`.

That separate connector pair is deliberate. A regular `wall_edge` must not mate
to the receiver because it lacks the rebate and would recreate the original
intersection. `Builder.mate()` chooses the yaw and translation, so an agent
does not decide which end faces the plinth.

The config validator asserts that mating places the trim pivot on `GRID_XY` and
that its far end lands on a `MODULE` line. `tessera.asset/1` is unchanged; this
adds connector vocabulary, not a schema revision.

## Consequences

- The kit has 22 assets.
- `examples/interior_rooms/` now reuses the south and west perimeter walls
  instead of keeping a corridor around a free-standing room.
- Two trims, one interior doorway and one interior corner close that room with
  0 errors and 0 warnings; three routes are proven.
- A falsification test restores the removed lower box mathematically and
  measures the original 0.00108 m³ plinth overlap. The shipped trim measures
  zero at the same mates.
- The trim remains a `wall` resting on `floor_top`, so the existing floating,
  support, grid and intersection rules apply unchanged.
