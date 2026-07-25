# Changelog

SPDX-License-Identifier: CC0-1.0

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: the repository and the `tessera.asset/1` contract version separately;
a breaking contract change is a new schema id, never a silent edit.

## [0.2.0] — 2026-07-25

Reachability becomes a measured property, and the traversal gap the
constrained-agent benchmark exposed is closed.

### Added

- **Six traversal parts** — straight stair, entrance stoop, floor with a
  stairwell, beam, column, railing. Column plus beam equals wall height exactly,
  enforced by `config.validate()`.
- **`src/tessera/navigate.py`** — character-aware flood fill over exact
  occupancy. Conservative by construction: the character is tested as a box,
  larger than the capsule it stands for, so any route it confirms is real.
- **`layout.reachability`** — declared routes the validator proves or refutes,
  plus `TSR_LAYOUT_UNREACHABLE` and `TSR_LAYOUT_STAIR_UNUSABLE`.
- **`examples/safehouse_two_storey`** — the building the benchmark asked for,
  with proven interior access.
- **`tessera brief`** — the catalog at ~193 tokens per asset, with a round trip
  that makes sufficiency testable.
- **Catalog fingerprints and layout pinning**, so composing on one device and
  executing on another fails loudly.
- **`TSR_LAYOUT_UNBALANCED` / `TSR_LAYOUT_UNDERSUPPORTED`** — a slab cantilevered
  off one wall edge used to validate clean.

### Fixed

- Support contact was thresholded **per box** rather than per instance, so any
  support with detailing on it was discarded and whatever rested on it reported
  as floating.
- The step-up limit was 25 cm, which made every real staircase unclimbable.
- An unbounded terrain plane made flood fill non-terminating.
- Off-axis rotation inflates the footprint AABB, so plausibility judgements are
  now skipped there rather than guessed.
- `tessera brief` budget is per asset, not absolute, so kit growth is not
  reported as a regression.

## [0.1.0] — 2026-07-25

First release. Milestone M1 complete: the placement contract proven on a
twelve-part vertical slice.

### Added

- **Geometry kernel** — exact CSG on sets of disjoint axis-aligned boxes, pure
  standard library, deterministic to a 1e-6 lattice. Watertight surface
  extraction with global T-junction repair. Convex-profile extrusion with a
  solved-resolution conservative inner occupancy staircase.
- **`tessera.asset/1` placement contract** — stable ids, semantic roles,
  provenance, units and axes, measured and grounded bounds, pivot with
  rationale, forward/up/right, allowed rotations and scaling with rationale,
  grid policy, connectors with normals and tangents and per-connector
  tolerances, occupancy, clearance, apertures, collision, material slots, LOD
  slots, engine import expectations, validation status, licence.
- **Twelve original parts** (`kits/shell_v1`) — foundation pad, floor slab,
  straight wall, L corner, doorway wall, door leaf, window wall, glazed window
  leaf, pitched roof panel, ridge cap, crate, workbench.
- **Validation** — 19 asset rules, 17 layout rules. Every diagnostic states
  what, where, why, expected, actual and a fix; correctable errors ship
  `fix_transform`.
- **Assembly** — `Builder.ground()` and `Builder.mate()` solve placements from
  the contract; `autoconnect()` discovers seams.
- **Export** — pure-Python glTF 2.0 binary writer, OBJ/MTL, world-space UV0 and
  packed non-overlapping UV1.
- **CLI** — `build`, `validate`, `catalog`, `describe`, `assemble`, `doctor`,
  with meaningful exit codes and `--json` throughout.
- **Adapters** — three.js (validator port + scene builder + reference viewer),
  Blender (import, collision, finishing, FBX), Unreal 5, Unity.
- **Schemas** — asset, catalog, layout, report; tested against the shipped data.
- **Licensing** — 0BSD code, CC0-1.0 assets, per-asset provenance records and a
  machine-readable manifest.
- **Tests** — 59 Python, 4 Node. Every validator rule has a fixture built to
  break it.

### Notes

- Blender, Unreal and Unity adapters are `script-provided-unverified`. See
  [`docs/engine-support.md`](docs/engine-support.md). Promotion is milestone M2.
- No code was copied from either predecessor repository. Concepts carried
  forward and rejected are recorded in
  [`docs/decisions/0000-lineage.md`](docs/decisions/0000-lineage.md) and in
  `provenance/manifest.json`.
