# 0002 — Blender is a consumer, not a dependency

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

The predecessor pack ran entirely inside Blender. Every build, every export,
every preview required `blender -b --python ...`. Nothing could be tested in CI,
and an agent working in a sandbox could not regenerate a single asset.

## Decision

The core pipeline — generation, measurement, catalog, validation, GLB and OBJ
export — is **standard-library Python 3.10+ with zero runtime dependencies**.
Blender is one optional consumer among four.

## Consequences

- `./tessera build` runs in an agent's sandbox, in CI, and on a fresh machine.
- glTF is written directly. glTF is JSON plus a byte buffer, so a compliant
  binary writer is about two hundred lines; the output is verified watertight by
  an independent third-party parser on every commit.
- FBX is the one thing that genuinely needs Blender, because there is no
  reasonable pure-Python writer. It is optional and nothing depends on it.
- The bevel-and-weighted-normal finishing pass — the shading treatment that made
  the predecessor pack read as one coherent set — moves to
  `adapters/blender/tessera_blender.py --finish`. It is a rendering
  improvement, not a correctness requirement, and it never changes silhouettes,
  so the contract stays true whether or not it has been applied.
- The Blender adapter asserts rather than assumes: `check_bounds()` raises if an
  imported mesh is not the size the contract promised, which is precisely the
  axis-conversion mistake an unverified adapter is most likely to make.
