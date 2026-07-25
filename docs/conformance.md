# Conformance

SPDX-License-Identifier: CC0-1.0

Tessera is an implementation *and* a contract. This page separates them, so that
"Tessera-compatible" means something other than "used our code".

Each level is independently claimable. You do not have to implement the level
below the one you want. See
[`decisions/0008`](decisions/0008-scope-and-replaceable-layers.md) for why.

---

## Level 0 — Consumer

*You read a catalog and place assets correctly.*

You must:

- read `tessera.asset/1` and refuse any `schema` you do not implement
- work in canonical space: right-handed, Z-up, +Y forward, metres, degrees,
  ZYX-intrinsic rotation
- ground with `world_z = supporting_surface_z + pivot.base_offset_z`, and use
  `placement.support.datum_connector` instead when the asset declares one
- honour `placement.grid.policy`, `allowed_rotations`, `allow_pitch_roll` and
  `allowed_scaling`
- use `collision.hulls` and never let an engine generate collision
- treat an unknown `connectors[].kind` as non-mating rather than guessing

You may ignore everything else in the record.

**Self-check:** `./tessera validate --layout <your layout>` exits 0.

## Level 1 — Validator

*You check layouts yourself.*

You must implement, at minimum, the rules whose absence produces silent damage:
`layout.grounded` (floating and buried), `layout.intersection`,
`layout.support` and `layout.support.balance`, `layout.aperture_clear`, and
`layout.catalog_pinned`.

Diagnostics must carry `code`, `what`, `where`, `why`, `expected`, `actual` and
`fix`, and should carry `fix_transform` where a correction exists. A diagnostic
without a fix costs a round trip; that is the whole point of the format.

**Self-check:** agree with `tessera validate` on the known-good layouts *and* on
every fixture in `tests/fixtures/broken_layouts.py`. `adapters/three/` is a
worked example of exactly this, held to Python by
`tools/export_parity.py`.

## Level 2 — Producer

*You emit a conformant catalog from geometry you made yourself.*

This is the level that matters if you already own assets. You do not need our
kernel or our kit — only to fill the record honestly:

- every geometric field **measured**, never asserted
- `occupancy` as disjoint boxes, with `approximation_tolerance` set truthfully
  when it is not exact
- `collision.hulls` derived from the occupancy *after* apertures are carved, so
  openings survive
- `apertures` with real `clear_width` / `clear_height` and an honest
  `traversable`
- connectors with unit `normal`, unit `tangent`, and the two orthogonal
- `provenance` and `license` complete

**Self-check:** `./tessera validate --catalog <your catalog>` exits 0. The 19
asset rules run against any catalog, whoever built it.

**Not yet supplied:** an importer that measures existing meshes for you. Today
you must produce the record yourself. This is the largest gap for anyone
arriving with their own art, and it is on the roadmap.

## Level 3 — Verified adapter

*You import into an engine, and prove it.*

An adapter is not conformant because it runs. It is conformant when a script
demonstrates, against the real engine:

- imported bounds match `dimensions.bounds` after the documented conversion
- collision hull count matches `collision.hull_count`
- **a traversable aperture is void in the imported collision**
- a layout's instances land at their declared transforms

`tools/verify_blender.py` (81 checks, in CI) and `tools/verify_unreal.py` (94
checks, local) are the reference implementations.

This level exists because it was learned the hard way: the Unreal adapter
documented its coordinate mapping as an axis swap for weeks. The real mapping is
a Y-negation. Both are valid handedness flips, which is exactly why review did
not catch it — only running it did.

---

## Versioning

The contract version is separate from the repository version. A breaking change
is a new schema id (`tessera.asset/2`), never an edit to an existing one.
Additive fields are a minor version and consumers must ignore what they do not
recognise.

Catalogs carry a `fingerprint`; layouts record the one they were composed
against. Any implementation that composes layouts should record it too, so that
composing on one device and executing on another fails loudly instead of
producing a building full of gaps.

## Claiming conformance

There is no certification and no registry. State the level, name the check you
ran, and let people reproduce it — the same standard
[`engine-support.md`](engine-support.md) holds our own adapters to.
