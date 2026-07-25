# 0000 — Lineage: what was carried forward, and what was not

SPDX-License-Identifier: CC0-1.0 · Status: accepted

Tessera was designed after inspecting two earlier repositories. Neither became
the architecture, neither was merged, and no code was copied from either. Both
remain intact.

## `asset-pack-ue-threejs-blender-unity` ("ModKit")

38 procedurally generated CC0 meshes exported to FBX and GLB, built by
`scripts/build_kit.py` on top of a Blender bmesh helper library, with every
dimension coming from one `kit_config.py`. A 70-instance example scene, Unreal
import/LOD/validate editor scripts, a UV texel-density checker, and a three.js
viewer.

Its own `ROADMAP.md` diagnosed the fatal gap precisely: the only
machine-readable output was `asset,triangles,vertices`.

**Carried forward**

| Idea | Where it lives now |
|---|---|
| One source of truth for every dimension, no hard-coded sizes | `kits/shell_v1/config.py` |
| A `validate()` that refuses impossible parameter combinations | `config.validate()`, now returning structured diagnostics |
| Explicit, documented pivot conventions per category | `pivot.convention` + `pivot.rationale`, now enforced by a rule |
| Every mesh produced by script; no hand-placed vertices | `kits/shell_v1/parts.py` |
| World-space consistent UV0 texel density, packed UV1 | `src/tessera/export/uv.py` |
| An assembled example scene as ground truth | `examples/workshop_shell/` |
| Honest documentation of what is *not* authored | `docs/engine-support.md` verification statuses |

**Rejected**

| Rejected | Why |
|---|---|
| Blender as a hard pipeline dependency | Nothing could run in CI or in an agent's sandbox. This was the single largest limitation. |
| Boolean-modifier CSG (spawn temp objects, apply modifier) | Slow, fragile, Blender-bound. Replaced by exact box-set CSG. |
| 214 MB of committed binaries, including a promo video | Build outputs belong in releases |
| `exports/` treated as source | It is generated; change the generator |
| Unauthored collision | Auto-convex seals doorways. Now derived from the carved solid. |
| A hardcoded absolute Windows path in an editor script | Portability |

## `World-Printer-Lab-For-3D-Worlds`

A three.js laboratory: a 26-family parametric part catalog, Supabase-backed
multiplayer placement, and — the valuable part — a working connector contract.

**Carried forward**

| Idea | Where it lives now |
|---|---|
| Connectors as position + normal + kind | `contract.Connector`, with a `tangent` added |
| Mating gated on *opposed normals*, not proximity alone | `layout.connector.direction` |
| Connectors derived from measured grounded bounds | `measure.py` — now the rule for every field |
| Scale classes as standards that refuse to mate across | `SCALE_CLASSES`, `layout.connector.scale_class` |
| Fail-closed admission with provenance, SHA-256 and rejection reasons | The provenance policy and the validator's non-zero exits |
| "Reject rather than silently rescale" | `Builder.mate()` raises rather than approximating |

**Rejected**

| Rejected | Why |
|---|---|
| `dims: [X, Z, Y]` and `measuredDims: [x, z, y]` axis ambiguity | A permanent footgun. One canonical space now, converted only at engine boundaries. |
| Magic tolerances (`opposition < -0.965`) buried in snapping code | Now `tolerance.angle_degrees`, travelling with the connector |
| Supabase coupling | Persistence is not a world-building concern |
| Legacy version sprawl (`legacy/v1`, `v2d`, `v3`, `public/v2`, `v2/`) | The same 935-line file existed four times |
| MIT licence | 0BSD/CC0 is broader, and MIT's notice clause is a condition |
| The CC0 asset-sourcing plan (Kenney, Quaternius, Poly Haven) | Original-only. That document became the quarantine policy instead. |

## The decision

A merge would have inherited Blender-boundness from one and axis ambiguity from
the other. A new repository was cheaper than reconciling them, and it allowed
the one architectural change that made everything else possible: **representing
solids as disjoint axis-aligned boxes**, which removed the solver, removed the
dependency, and made occupancy exact.

Recorded machine-readably in `provenance/manifest.json` under
`conceptual_lineage`, with `"code_copied": "none"` per source.
