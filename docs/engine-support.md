# Engine support

SPDX-License-Identifier: CC0-1.0

**Nothing on this page is claimed as "supported" without an executable path.**
Documentation-only integration is how a repository accumulates three engines it
has never actually run.

Each adapter has a verification status, and the status is the honest one:

| Status | Means |
|---|---|
| `verified-in-ci` | runs on every commit, in this repository, and fails the build if it breaks |
| `verified-locally` | executed and confirmed by a person, but not on every commit |
| `script-provided-unverified` | complete and reviewed, but never executed against the real engine |
| `planned` | not written |

---

## Current status

| Target | Adapter | Status | What is actually proven |
|---|---|---|---|
| **Engine-neutral core** | `src/tessera/` | `verified-in-ci` | 59 tests: kernel invariants, contract coherence, 15 layout rules, 12 asset rules, schema conformance, deterministic builds |
| **JavaScript / three.js** | `adapters/three/` | `verified-in-ci` | 4 Node tests: the JS validator reaches the same verdict as Python on the known-good layout and on all 15 broken fixtures; transform conversions match the Python reference exactly; the grounding solver reproduces every assembled height |
| **glTF / GLB output** | `src/tessera/export/glb.py` | `verified-in-ci` | every exported mesh is re-loaded by an independent third-party parser and confirmed watertight, winding-consistent, and of exactly the expected volume and extents |
| **Blender** | `adapters/blender/tessera_blender.py` | `script-provided-unverified` | parses, imports without `bpy`, and its argument handling is exercised; the import path itself has not been run against Blender in CI |
| **Unreal Engine 5** | `adapters/unreal/tessera_unreal.py` | `script-provided-unverified` | parses, imports without `unreal`, and its coordinate conversions are unit-tested; the import path has not been run against an editor |
| **Unity** | `adapters/unity/Editor/TesseraImporter.cs` | `script-provided-unverified` | reviewed and structurally checked; not compiled against a Unity install |

The three unverified adapters each end with a **self-check that fails loudly**
rather than silently producing wrong geometry — for example
`tessera_blender.check_bounds()` raises if an imported mesh is not the size the
contract promised, which is exactly the axis-conversion mistake an unverified
adapter is most likely to make.

Promoting an adapter from `script-provided-unverified` requires the acceptance
tests in [`ROADMAP.md`](../ROADMAP.md) M2. Until then, this table says so.

---

## Coordinate conversions

Canonical Tessera space is **right-handed, Z-up, +Y forward, metres**. Every
conversion below lives in exactly one place in code
(`src/tessera/units.py::ENGINE_SPACES`) so an adapter cannot invent its own, and
each is unit-tested for round-trip fidelity.

| Engine | Up | Forward | Handed | Unit | Point mapping | Winding |
|---|---|---|---|---|---|---|
| Tessera (canonical) | +Z | +Y | right | m | identity | — |
| Blender | +Z | +Y | right | m | identity | unchanged |
| Unreal | +Z | +X | left | cm | `(x,y,z) -> (y*100, x*100, z*100)` | reversed |
| Unity | +Y | +Z | left | m | `(x,y,z) -> (x, z, y)` | reversed |
| glTF / three.js | +Y | −Z | right | m | `(x,y,z) -> (x, z, -y)` | unchanged |

Two notes that cause most real bugs:

- **Unreal's X/Y swap is the handedness flip.** Do not apply an extra mirror on
  top of it. Winding is reversed so normals stay outward.
- **The shipped `.glb` files are already in glTF space.** Blender's importer
  applies its own Y-up-to-Z-up conversion, which lands the mesh back in
  canonical space. That is correct — but it means you must not convert again.
  Layout transforms, by contrast, are always canonical and *do* need converting.
  Each adapter does it in one function; find that function before adding a
  second.

---

## Import expectations

Each asset carries an `engine` block with the settings that target expects, so
an importer never has to guess:

```json
"unreal": {
  "import_uniform_scale": 1.0,
  "combine_meshes": false,
  "auto_generate_collision": false,
  "collision_source": "UCX_ hulls from occupancy",
  "note": "auto collision seals apertures; use the shipped hulls"
}
```

The one setting that is non-negotiable on every engine: **do not let the engine
generate collision.** Convex hulls seal doorways. Use `collision.hulls`.

---

## Formats

| Format | Written by | Notes |
|---|---|---|
| `.glb` | `src/tessera/export/glb.py` | Canonical distribution format. Pure Python writer, no dependency. Flat-shaded: vertices are split per face by design, so a loader that reports "not watertight" before merging vertices is telling you about the shading, not the geometry. |
| `.obj` / `.mtl` | `src/tessera/export/obj.py` | The debugging format of last resort — every tool on earth opens it, including a text editor. |
| `.fbx` | `adapters/blender` only | There is no reasonable pure-Python FBX writer, so this is the one output that genuinely requires Blender. It is optional, and nothing else in the pipeline depends on it. |

UV0 is a world-space planar projection at a fixed metres-per-repeat, so one
tiling material appears at the same scale on a wall and on a crate. UV1 is a
packed, non-overlapping unwrap suitable for a lightmap or AO bake; charts are
coplanar face groups scaled by true world area. Unreal can still generate its
own at import — UV1 exists so Unity, Godot and three.js get a usable channel
without doing the work.
