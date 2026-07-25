# Changelog

SPDX-License-Identifier: CC0-1.0

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: the repository and the `tessera.asset/1` contract version separately;
a breaking contract change is a new schema id, never a silent edit.

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
