# Architecture

SPDX-License-Identifier: CC0-1.0

## The thesis

The bottleneck in agent-built worlds is not how many assets exist. It is **how
much the agent has to guess**. Every guess costs a render, a screenshot, a
visual estimate and a retry.

So the ordering principle for everything in this repository is: *rank work by
how much agent back-and-forth it removes*, not by what is missing from an asset
list. Forty assets an agent places correctly on the first attempt are worth more
than two hundred it has to be corrected on.

That principle produced a specific shape.

```
                     kits/shell_v1/config.py
                     one source of truth, with a validate()
                     that refuses impossible combinations
                                  |
                                  v
                     kits/shell_v1/parts.py
                     12 part functions -> BoxSet solids
                                  |
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
  tessera/boxset.py         tessera/mesh.py          tessera/measure.py
  exact CSG on              surface extraction        derive EVERY contract
  disjoint AABBs            watertight by             field by measurement
        |                   construction                     |
        |                         |                          |
        +-------------------------+--------------------------+
                                  |
                                  v
                        build/catalog.json
                        the placement contract
                                  |
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
  tessera/assemble.py     tessera/validate/          adapters/
  solve placements        19 asset rules             three | blender
  from the contract       17 layout rules            unreal | unity
        |                         |
        +------------> layout.json <-------- validated, with fix_transform
```

## The four decisions that shape everything

### 1. Solids are sets of disjoint axis-aligned boxes

Architectural geometry is unions and differences of boxes. An axis-aligned box
difference has an exact closed form — at most six boxes — so a solid built this
way needs no boolean solver, no mesh repair, and no dependency.

Three consequences, and they are the reason this kernel exists:

- **The pipeline runs anywhere.** CI, a sandbox, a laptop with no Blender. The
  predecessor pack could only build inside Blender, so it could not be tested.
- **Occupancy is not an approximation of the mesh; it *is* the solid.** "Do
  these two placed assets intersect" is an exact test with an exact shared
  volume, not an AABB guess.
- **Collision is free and correct.** A set of disjoint boxes is already a valid
  convex decomposition. Because apertures are carved out of that set, the
  doorway is a hole in the collision too.

Where boxes genuinely cannot express the shape — a pitched roof — the kernel
extrudes a 2D profile instead, and occupancy becomes a *conservative inner*
staircase whose shortfall is published as `occupancy.approximation_tolerance`.
The approximation can produce false negatives but never false positives, which
is the safe direction for a clash check, and consumers widen their tests by the
declared amount rather than pretending it is exact.

### 2. Every contract field is measured, never asserted

`measure.py` derives bounds, grounded bounds, pivot offsets, footprints,
occupancy, collision hulls, apertures and mesh health from the solid at build
time. Nothing is typed in by hand.

This is the difference between a catalog an agent can trust and a README it has
to second-guess. Prose drifts from geometry; measurements cannot.

### 3. Holes are recorded at the moment they are cut

`BoxSet.carve_aperture()` removes material **and remembers what the hole is
for** — its kind, its traversal axis, whether you are meant to walk through it.
`subtract()` just removes material.

That distinction is what turns three separate documentation warnings into three
executable tests:

- is the opening big enough for a character? (`clear_width`, `clear_height`,
  `fits_capsule.admits_reference_character`)
- does collision seal it? (`asset.collision.preserves_apertures`)
- has something been placed in the route? (`layout.aperture_clear`)

### 4. Diagnostics carry the fix, not just the complaint

A diagnostic that says `invalid placement` costs exactly as much as no
diagnostic. Every Tessera error answers what, where, why, expected, actual and
fix — and where a correction exists, ships it as data:

```json
{"code": "TSR_LAYOUT_FLOATING", "fix_transform": {"translate": [0, 0, -0.372]}}
```

The agent applies it and re-runs. `tests/test_validators.py` asserts that doing
so actually clears the error.

## Module map

| Module | Responsibility |
|---|---|
| `units.py` | The one canonical space, and every engine conversion, in one table |
| `boxset.py` | Exact CSG on disjoint AABBs; apertures |
| `mesh.py` | Surface extraction, T-junction repair, prism extrusion, mesh health |
| `contract.py` | The vocabulary: roles, connector kinds, the compatibility table, scale classes |
| `measure.py` | Derive the whole contract from a solid |
| `transform.py` | Instance transforms; exact under 90-degree rotation, conservative otherwise |
| `catalog.py` | Placement policy by category; assemble and write the catalog |
| `assemble.py` | Solve placements and discover seams |
| `validate/asset.py` | 19 build-time rules |
| `validate/layout.py` | 17 scene rules |
| `validate/diagnostics.py` | The diagnostic shape and the coverage collector |
| `validate/report.py` | One report, rendered for humans and for machines |
| `export/glb.py` | Pure-Python glTF 2.0 binary writer |
| `export/uv.py` | World-space UV0, packed UV1 |
| `navigate.py` | Character-aware walkable graph over occupancy; reachability |
| `brief.py` | The context-budgeted digest, and its round trip |
| `cli.py` | `build`, `validate`, `catalog`, `describe`, `assemble`, `brief`, `doctor` |

## Why the validator has two implementations

`adapters/three/src/tessera-core.mjs` is a deliberate port of the layout rules a
*runtime* consumer needs — floating, buried, unsupported, intersecting, blocked
apertures. Build-time concerns (grid, rotation, scale, connector policy) stay in
Python, which is authoritative.

A second implementation that disagrees with the first is worse than no second
implementation, so `tools/export_parity.py` records Python's verdict on the
known-good layout and all 15 broken fixtures, and `adapters/three/test/` holds
JavaScript to it on every commit.

## What is deliberately not here

- **A renderer.** Tessera describes; it does not draw. The viewer in
  `adapters/three/` is a reference, not a product.
- **A scene format war.** `layout.json` is a transform list. It is not trying to
  be USD.
- **Runtime dependencies.** Zero, on purpose.
- **Third-party assets.** Not one, on purpose. See
  [`provenance-policy.md`](provenance-policy.md).
