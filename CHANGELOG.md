# Changelog

SPDX-License-Identifier: CC0-1.0

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: the repository and the `tessera.asset/1` contract version separately;
a breaking contract change is a new schema id, never a silent edit.

## [Unreleased]

Interior rooms, including the wall-to-wall junction. A room can now be closed,
entered, and partitioned directly from a building perimeter without overlapping
the perimeter plinth.

### Added

- **The public Tessera Workshop** — a phone-first, no-login GitHub Pages
  application that slices a handoff by environment and asset role, renders an
  orthographic occupancy plan, runs the labelled JavaScript validation subset,
  and produces downloadable chat and full-validator sandbox packs.
- **`tessera pack`** — deterministic `chat`, `browser`, `sandbox` and `desktop`
  handoff ZIPs. Richer targets add executable surfaces without weakening the
  contract given to constrained ones.
- **`tessera brief --only`** — semantic-role and asset-id glob slicing. Against
  the current kit, a wall-only text brief is about 830 tokens instead of the
  roughly 56,700-token full catalog.
- **`tessera repair`** — tries validator-supplied transforms on copies,
  revalidates them, and commits only a candidate that strictly reduces the
  error count.
- **`tessera.handoff/1`**, the machine-readable capability manifest carried in
  every pack.
- **[`docs/decisions/0011-hands-are-capability-adapters.md`](docs/decisions/0011-hands-are-capability-adapters.md)**.
- **Four interior parts** — `wall.interior.4m`, `wall.interior.doorway.4m`,
  `wall.interior.corner.4m`, `wall.junction.trim.3m8`. 22 assets, all passing
  the same 19 asset rules
  unchanged. The interior aperture is the identical `DOOR_WIDTH × DOOR_HEIGHT`,
  so `door.leaf.1m2` hangs in either without a second leaf asset.
- **`examples/interior_rooms`** — a room partitioned from a corner of a
  16 × 12 m shell, reusing two perimeter walls. 56 instances, 0 errors,
  0 warnings, three routes proven by flood fill.
- **A control test** that swaps the one interior doorway for a solid interior
  wall and requires `TSR_LAYOUT_UNREACHABLE`. Without it, "the room can be
  entered" would only be evidence that a flood fill can find *some* route.
- **`derived.perimeter_inner_face_inset`** and
  **`derived.perimeter_inset_is_on_grid`** — see Known below.
- **Four `config.validate()` checks** behind the new constants:
  `CFG_INTERIOR_THICKNESS_OFF_GRID`, `CFG_INTERIOR_GROOVE_TOO_DEEP`,
  `CFG_INTERIOR_SKIRT_TOO_TALL`, `CFG_INTERIOR_DOOR_PIER_TOO_NARROW`.
- **Five junction configuration checks** keep the trim length, rebate, receiver,
  and bay-line endpoints derived from the kit grid rather than encoded in
  geometry.
- **A repository-owned Unity UPM package and verification project.**
  `Tessera.TesseraVerify.Run` imports all 22 GLBs through pinned Khronos
  UnityGLTF 2.14.1, checks bounds, collision and apertures, builds the two-storey
  layout, and exits non-zero on failure.
- **[`docs/decisions/0009-interior-pieces.md`](docs/decisions/0009-interior-pieces.md)**.
- **[`docs/decisions/0010-wall-junction-bridges-to-the-bay-line.md`](docs/decisions/0010-wall-junction-bridges-to-the-bay-line.md)**.

### Fixed

- **A partition could not terminate flush against a perimeter wall.** A perimeter
  wall's innermost surface is its plinth, `WALL_THICKNESS + PLINTH_PROUD` =
  0.23 m in from the bay line, and 0.23 is not a whole number of `GRID_XY`
  units. A module-length partition on the grid overlapped it by 0.00108 m³ —
  small enough to read as noise — or stopped short and left a 0.17 m slot. The
  dedicated 3.8 m junction now clears the lower plinth, solves its orientation
  from connectors, and ends on the next bay line.
- **Unity's `JsonUtility` cannot deserialize the nested arrays in
  `collision.hulls`.** The adapter now uses Unity's maintained Newtonsoft
  package, so collision data reaches `BuildColliders()` intact.
- **Unity verification was described as one sign-in away while the documented
  batch entry point did not exist.** The missing project and harness now live in
  the repository; the adapter remains unverified until a licensed editor run
  produces a zero-failure report.

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
