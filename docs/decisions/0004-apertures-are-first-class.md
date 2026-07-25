# 0004 — Holes are recorded at the moment they are cut

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

"Auto-generated convex collision seals doorways" is the best-known trap in
modular kits, and the predecessor pack could only document it:

> *Collision is not authored. Convex hulls close doorways, arches and stairs. Do
> not assume a placed doorway is walkable.*

A warning tells an agent to be careful. It does not let it check.

## Decision

`BoxSet.carve_aperture()` removes material **and records what the hole is for** —
its id, kind, region and traversal axis. `subtract()` merely removes material,
and is used for detailing that is not an opening.

## Consequences

Three warnings become three executable rules:

| Question | Rule |
|---|---|
| Is the opening big enough for a character? | `asset.aperture.admits_character` |
| Does collision seal it? | `asset.collision.preserves_apertures` |
| Has something been placed in the route? | `layout.aperture_clear` |

And two properties fall out for free:

- **Collision inherits the hole.** Hulls are derived from the carved box set, so
  a doorway is a hole in the collision by construction rather than by care.
- **A closed door is distinguishable from a blocked one.** A leaf connected to
  the wall it fills produces an `info`, not an error, with the reasoning stated:
  the opening is closed but not obstructed. A crate left in the doorway produces
  an error. Neither source repository could tell those apart.

`fits_capsule.admits_reference_character` uses a real adult-sized capsule, so an
opening marked traversable that nobody can walk through fails the build. An
opening nobody can walk through is a wall with a decoration.
