# 0006 — The corner piece is an L, not a post

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

A rectangular building perimeter has to close without geometry overlapping. Two
walls running the full bay module meet at a corner and overlap in a
`thickness × thickness` column. That is a real intersection: it z-fights, it
breaks physics, and the validator correctly refuses it.

The usual fixes are all bad in a different way:

- **Shorten walls to `module − thickness`.** A "4 m wall" that is 3.8 m long is
  a lie that every consumer has to learn.
- **A corner post plus shortened walls.** Same lie, plus an extra piece.
- **Offset the second wall along its own length.** The building becomes
  asymmetric by one wall thickness.
- **Let them overlap and ignore it.** Turns the intersection rule into noise,
  which is how validators get switched off.

## Decision

`wall.corner.4m` is an **L** occupying both edges of a bay corner — a full
module in each direction, fused into one solid, with seam connectors at the far
end of each leg.

## Consequences

- A rectangular perimeter closes with four L corners plus straight pieces for
  the middle segments, with **zero overlapping geometry**. The 12 × 12 m
  workshop uses four corners and four middle walls and passes the intersection
  rule with no tuning.
- Walls stay honestly 4 m. The module means what it says.
- A building must be at least 3 bays per side to have a middle segment for a
  door or window. That is a real constraint and it is stated here rather than
  discovered.
- The corner carries two `wall_base` and two `wall_top` surface connectors, one
  per leg, so a roof can bear on either.

The first assembled scene used two corners on opposite diagonals and left the
other two corners to overlapping walls. The validator caught it —
`0.1223 m³ shared volume`, twice — which is the intended way for this class of
mistake to be found.
