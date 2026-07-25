# 0007 — Support is a surface relation, not a point coincidence

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

The predecessor connector model had one mating mode: two points coincide. That
works for seams — wall edge to wall edge, roof ridge to roof ridge — and cannot
express the most common relation in a building: *a wall stands somewhere on a
floor*. The wall's base and the floor's top do not meet at a point; they meet on
a plane, at a position the floor does not constrain.

## Decision

Connectors declare `mating_mode`:

- **`point`** — the two world points must coincide within
  `tolerance.position_metres`. Seams, ridges, hinges.
- **`surface`** — the two planes must be coplanar and the smaller `extent_half`
  contained in the larger. Wall base on floor top, prop base on any surface,
  roof bearing on wall top.

## Consequences

- "Rests on" becomes checkable. `placement.support.rests_on` names connector
  kinds, and the validator finds real support by plane and footprint overlap
  rather than by hoping two points line up.
- Footprint is not silhouette. A workbench's footprint is its four legs, so
  support coverage is measured against what actually touches.
- **A support candidate must start below the datum.** Without that test every
  instance in the building reported as buried under the roof, because the roof
  overlaps it in plan and its top is higher. Overlapping in plan is not the same
  as being underneath — a bug the validator found on its own first run, on 15
  instances at once.
- Assets whose lowest vertex is not their bearing plane declare
  `support.datum_connector`. A roof panel's eave overhang legitimately hangs
  below the wall top it bears on; measuring grounding at the lowest vertex would
  report every correctly placed roof as buried.
- Assets carried by a connection rather than by ground contact — a hung door
  leaf, a ridge cap — set `may_float: true` and are validated by their
  connection instead. They warn if they declare none, because for those assets
  the connection is the only evidence they are attached to anything.
