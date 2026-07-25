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
| **Blender** | `adapters/blender/tessera_blender.py` | `verified-in-ci` | 81 checks against **Blender 5.0.1** on every commit: all 18 assets import with bounds matching the contract to ~1e-8 m, triangle counts survive, collision hulls are built one per declared hull, a doorway's collision is void where its aperture is, a 37-instance layout lands at its declared transforms to 1.9e-7 m, and FBX export keeps the `UCX_<mesh>_##` names Unreal binds collision by |
| **Unreal Engine 5** | `adapters/unreal/tessera_unreal.py` | `verified-locally` | 94 checks against **Unreal Engine 5.6.1**, headless: all 18 assets import with bounds matching the contract to **0.0000 cm**, collision is rebuilt one hull per declared hull and persists, a 37-instance layout spawns at its declared transforms to **0.0000 cm**, and a doorway's collision is void where its aperture is. Not in CI: Unreal needs a licensed multi-gigabyte install, so it cannot follow Blender's pip route |
| **Unity** | `adapters/unity/Editor/TesseraImporter.cs` | `script-provided-unverified` | reviewed and structurally checked; not compiled against a Unity install |

> **The asset counts above are 18, and the kit now has 21.** The three M3
> interior pieces — `wall.interior.4m`, `wall.interior.doorway.4m`,
> `wall.interior.corner.4m` — have not been through either engine yet. Blender
> is `verified-in-ci`, so its run covers them on the next commit and the count
> becomes 21 when that run is read, not before. Unreal is `verified-locally`
> and needs `tools/verify_unreal.py` re-run by hand against the licensed
> install; until someone does, its 94 checks describe the 18 assets that were
> present at the last run. Restating a number an engine has not actually
> produced is exactly the kind of claim this table exists to prevent.

### What Unreal actually does with collision

Worth stating plainly, because it is the founding claim of this repository and
it now has an engine behind it rather than an argument:

```
VERIFY ok  doorway collision leaves the aperture void   0 hull(s) in the opening
VERIFY ok  Unreal would have sealed it without us       auto-generated 1 convex hull(s)
```

Unreal puts a single 18-DOP convex hull over a doorway wall on import. That hull
seals the doorway. Tessera replaces it with the 17 hulls of the carved solid and
the opening stays open.

Setting the mesh pipeline's `collision` property to `False` **does not prevent
this** — it generated a hull either way in 5.6. So the adapter no longer tries to
prevent it: it imports, removes whatever arrived, and rebuilds from the contract.

Two further things that only running it revealed. The imported asset path cannot
be constructed, because Interchange nests the result at
`<dest>/<file stem>/StaticMeshes/<name>`; ask the task what it produced. And
`FKBoxElem` X/Y/Z are *full* extents rather than half, which was confirmed by
asking Unreal to fit a box to a known mesh and reading back what it stored.

### How Blender is verified without a Blender install

`pip install bpy` gives a headless Blender as a Python module, so
`tools/verify_blender.py` runs in CI with no display, no GUI and no manual step.
That is the difference between an adapter that is *claimed* to work and one that
is *checked* to.

Running it found three real defects that reading the code did not:

* `finish()` raised on Blender 4.1+. The guard was written
  `obj.data.use_auto_smooth = True if hasattr(...) else None`, which still
  performs the assignment. It reads like a guard and is not one.
* `wipe()` used operators, which depend on a view-layer context headless Blender
  does not always have. When it silently did nothing, the next import found its
  name taken and Blender appended `.001` — quietly breaking the `UCX_<mesh>_##`
  convention, so meshes would import into Unreal with **no collision at all** and
  nothing would say why.
* Auto-smooth has moved twice across Blender versions and needed handling for
  both, plus a path for neither.

### Rendering

`tools/render_previews.py` renders the asset sheet and the assembled scenes with
the same headless Blender. It uses Cycles rather than Workbench: Workbench is an
OpenGL engine and needs libEGL, which a headless container does not have, while
Cycles is a pure software path tracer and runs anywhere the rest of the pipeline
runs. Denoising is off because it is the largest memory consumer here and a
small container kills the process with no traceback at all.

Renders are documentation, not verification, and nothing in them is asserted by
a test. They did earn their keep immediately, though: the first correct framing
of the workshop showed daylight through both gable ends. No rule catches that —
an open gable is not floating, buried, intersecting or unreachable. It is a
missing piece, and only a picture showed it.

### What Blender verification proves transitively

The GLB writer is pure Python with no Blender involved, so a real DCC tool
reading those files and reproducing the contract's declared bounds to 1e-8 m
independently confirms the exporter, the glTF Y-up conversion, and the contract
itself. Two independent implementations agreeing is worth more than either one
asserting.

The two remaining unverified adapters each end with a **self-check that fails loudly**
rather than silently producing wrong geometry — for example
`tessera_blender.check_bounds()` raises if an imported mesh is not the size the
contract promised, which is exactly the axis-conversion mistake an unverified
adapter is most likely to make.

Promoting an adapter from `script-provided-unverified` requires the acceptance
tests in [`ROADMAP.md`](../ROADMAP.md) M2. Until then, this table says so.
Blender has been promoted; Unreal and Unity have not.

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
| Unreal | +Z | +X | left | cm | `(x,y,z) -> (x*100, -y*100, z*100)` | handled by the importer |
| Unity | +Y | +Z | left | m | `(x,y,z) -> (x, z, y)` | reversed |
| glTF / three.js | +Y | −Z | right | m | `(x,y,z) -> (x, z, -y)` | unchanged |

Two notes that cause most real bugs:

- **Unreal negates Y; it does not swap X and Y.** This adapter documented a swap
  for weeks and it was wrong. Both a swap and a Y-negation are valid
  right-to-left handedness flips, which is exactly why the mistake survives
  inspection — but they differ by a 90-degree rotation, so every layout instance
  would have been placed rotated and mirrored relative to its own geometry. The
  mapping now in the table was *measured*: a 4.00 x 0.26 x 3.00 m wall imports
  to X 0..400, Y -23..3, Z 0..300.
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
