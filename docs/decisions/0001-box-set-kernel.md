# 0001 — Solids are sets of disjoint axis-aligned boxes

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

Architectural geometry — walls, floors, openings, plinths, recessed panels — is
built from unions and differences of axis-aligned boxes. The predecessor pack
expressed this with Blender's EXACT boolean solver, which meant the asset
pipeline could only run inside Blender, was slow, and could not be tested.

## Options considered

**A. Keep a mesh boolean solver.** Familiar, handles arbitrary geometry.
Requires a heavyweight dependency, produces meshes needing repair, and gives no
usable occupancy representation.

**B. Half-edge / BRep kernel.** Fully general. Large, subtle, and enormous
overkill for a modular building kit.

**C. Sets of disjoint axis-aligned boxes.** Exact closed-form difference (at
most six boxes), no solver, no dependency. Cannot express non-axis-aligned
shapes.

## Decision

**C**, with 2D-profile extrusion as an escape hatch for pitched roofs and
anything else that genuinely is not axis aligned.

## Consequences

**Good.**

- Runs anywhere: CI, an agent's sandbox, a machine with no Blender.
- Occupancy is not an approximation of the mesh; it *is* the solid. Clash tests
  return exact shared volumes.
- Collision is free and correct: a disjoint box set is already a valid convex
  decomposition, and because apertures are carved out of it, the doorway is a
  hole in the collision too.
- Builds are deterministic. Coordinates snap to a 1e-6 lattice, so the same
  input produces byte-identical output on any machine — asserted by a test.
- Surface extraction is combinatorial: for each plane, the visible surface is a
  2D rectangle-set difference between the material on each side. Abutting boxes
  weld into one watertight shell with no solver.

**Bad, and handled.**

- Rotation must be axis-aligned to stay exact. Modular pieces are restricted to
  90-degree yaw, which is stated as a contract with its reason; off-axis
  rotation falls back to a conservative bounding box and the validator says so.
- Extruded profiles need an approximate occupancy. The staircase is
  *conservative inner*, so it can produce false negatives but never false
  positives — the safe direction for a clash check — and the shortfall is
  published as `occupancy.approximation_tolerance` rather than hidden. The slab
  count is solved, not guessed: it doubles until every slab yields a box filling
  at least half its column, because a steep thin section can otherwise produce
  *no* occupancy at all, which is exactly the kind of silent hole this project
  exists to prevent.
- Greedy-merged rectangles create T-junctions. A global per-axis break set
  subdivides every rectangle edge at every coordinate any face uses, and
  polygons with collinear vertices are fanned from an added centroid rather than
  a corner — fanning from a corner emits zero-area triangles across collinear
  runs and silently drops the split edges, reopening the shell. Both were found
  by the manifold test, not by looking at renders.
