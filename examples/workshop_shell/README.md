# Workshop Shell

SPDX-License-Identifier: CC0-1.0

The demonstration for milestone M1. A sealed 12 × 12 m workshop assembled from
the twelve-part `shell_v1` kit — **entirely from metadata**.

```bash
./tessera build
python3 examples/workshop_shell/build.py
./tessera validate --layout examples/workshop_shell/layout.json
```

## What it contains

| | |
|---|---|
| Foundation pads | 9 |
| Floor slabs | 9 |
| L corners | 4 |
| Doorway wall | 1, with a 1.20 × 2.20 m walkable aperture |
| Window wall | 1, with a 1.80 × 1.20 m glazed aperture at 1.00 m sill |
| Straight walls | 2 |
| Door leaf, window leaf | 1 each, mated into their apertures |
| Roof panels | 6, in a single gable meeting at y = 6 |
| Ridge caps | 3 |
| Props | 4 (workbench, three crates, one stacked at a free angle) |
| **Total instances** | **41** |

## What it proves

| | |
|---|---|
| Instances solved from the contract | 41 |
| Instances placed by hand | **0** |
| Seams discovered automatically and verified | 46 |
| Manual placement corrections required | **0** |
| Validation errors | **0** |
| Validation warnings | 0 |
| Layout rules evaluated | 17 |

The only informational note is that the doorway aperture is occupied by its own
door leaf — the validator distinguishes a *closed* door from a *blocked* one,
because the leaf declares a connection to the wall it fills.

## How to read `build.py`

It is 90 lines and contains exactly one hard-coded height: the terrain, at zero.

- `b.ground(asset, x, y, on=host)` reads the host's supporting-surface connector
  and the guest's support datum, and solves Z. There is no `z = 0.5` anywhere.
- `b.mate(asset, connector, host, host_connector)` picks the yaw that makes the
  two connectors face each other and solves the translation that makes their
  points coincide. Both the door leaf and the ridge caps are placed this way.
- `b.autoconnect()` then discovers every real seam in the scene — compatible
  kinds, matching scale classes, coincident points, opposed normals — and
  declares it, so the layout records what actually mated rather than what the
  author believed mated.

## Why four corners and three bays per side

A corner piece is an **L** occupying both edges of a bay corner, so a
rectangular perimeter closes with zero overlapping geometry. That means a
building needs at least three bays per side to have a middle segment free for a
door or a window. See
[`docs/decisions/0006-corner-piece-is-an-L.md`](../../docs/decisions/0006-corner-piece-is-an-L.md).

The first version of this scene used two corners on opposite diagonals and let
the remaining two corners overlap. The validator caught it — `0.1223 m³ shared
volume`, twice — which is exactly how that class of mistake is meant to be
found.

## Files

| File | |
|---|---|
| `build.py` | the assembly script |
| `layout.json` | generated: 41 instances with transforms and connections |
| `expected-report.json` | the validation report this layout must produce |
