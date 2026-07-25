# AGENTS.md

Instructions for AI coding agents working with Tessera. Humans want
[`README.md`](README.md).

Read this file completely before your first tool call. It is short, and it is
the difference between one pass and six.

---

## 1. What this repository is for

You are probably here to build a world. The expensive part of that is not
modelling — it is the correction loop: place, render, notice it is floating,
adjust, render again. Tessera exists to delete that loop.

**Everything you would normally infer from a picture is already a number in
`build/catalog.json`.** If you find yourself about to render something in order
to estimate a dimension, a height, a facing or a gap, stop: the answer is in the
catalog and it is exact.

---

## 2. Start here, in this order

```bash
./tessera build                     # regenerate meshes + catalog (a few seconds)
./tessera catalog                   # one line per asset: size, pivot, connectors
./tessera describe wall.doorway.4m  # the full contract for one asset
```

Then read one asset record end to end. Fifteen seconds there saves you an hour.

---

## 3. The rules that actually matter

### 3.1 Never guess a dimension

Every asset publishes `dimensions.size`, `dimensions.bounds` and
`dimensions.grounded_bounds`, all measured from the solid at build time. They
cannot be stale. Read them.

### 3.2 Never guess a height

`pivot.base_offset_z` is the only number you need to ground something:

```
world_z = supporting_surface_z + asset.pivot.base_offset_z
```

For every modular piece in this kit that value is `0.0`, because there is one
pivot rule for the whole kit rather than one per category. When an asset cannot
use it — a roof panel whose eave overhang hangs below its bearing plane — it
declares `placement.support.datum_connector` instead, and *that* connector's Z
is the grounding datum. Check for it; do not assume the lowest vertex.

Better: do not compute it at all. `Builder.ground()` does it for you.

### 3.3 Never place by eye when you can solve

```python
from tessera.assemble import Builder
b = Builder(catalog, "my scene")

pad   = b.ground("tsr:shell/foundation.pad.4m", 0, 0)          # on terrain
floor = b.ground("tsr:shell/floor.slab.4m", 0, 0, on=pad)      # Z solved
wall  = b.ground("tsr:shell/wall.straight.4m", 0, 0, on=floor) # Z solved
b.mate("tsr:shell/door.leaf.1m2", "hinge", doorway, "jamb_neg_y")  # full transform solved
b.autoconnect()                                                # find every seam
```

`ground()` reads the host's supporting-surface connector and the guest's support
datum. `mate()` picks the yaw that makes two connectors face each other and
solves the translation that makes their points coincide. If no legal yaw works
it **raises with the reason** rather than placing something approximately right.
A refusal you can act on beats a placement you have to check.

### 3.4 If your context is tight, use the brief

```bash
./tessera brief --format text                 # ~3,300 tokens instead of ~56,700
./tessera brief --only wall --format text     # ~830 tokens
```

It carries everything needed to place an asset: sizes, grounding offsets, grid
and rotation policy, support relations, full connector frames, apertures,
clearances, the mating table and the stack heights. It drops what placement does
not use, and its `legend.omitted` names exactly what it dropped.

If you later need collision hulls or provenance, fetch `full_catalog`. The
brief's `fingerprint` proves you received the matching one.

If the next agent is in a different environment, package the hands it can use:

```bash
./tessera pack --target chat --only wall,wall_opening --out handoff.zip
./tessera pack --target sandbox --layout layout.json --out handoff.zip
```

Targets are additive: `chat` is a compact specification, `browser` adds the
public Workshop, `sandbox` adds the full zero-dependency validator and selected
assets, and `desktop` keeps the complete repository and adapters.

**Record that fingerprint in any layout you emit.** `Builder` does it for you. A
layout composed against one catalog and executed against another produces a
building full of gaps with no error anywhere; the pin turns that into
`TSR_LAYOUT_CATALOG_MISMATCH`.

### 3.5 Declare the routes that matter

Every traversable opening is audited automatically, but that only proves each
door works in isolation. It does not prove the places they lead to are connected.

```json
"reachability": [
  {"label": "outside to the mezzanine", "from": [6, -1.6, 0], "to": [6, 10, 3.7],
   "must": true},
  {"label": "the vault stays sealed", "from": [6, 2, 0.5], "to": [9, 9, 0.5],
   "must": false}
]
```

The validator proves or refutes each one by flooding the walkable volume. A
claim that turns out to be false is reported; `must: false` catches the reverse,
which is a containment bug and worth checking in a game.

### 3.6 Always validate, and read the fix

```bash
./tessera validate --layout my_layout.json --report report.json
```

Exit code `0` means it passed, `1` means it found errors, `2` means it could not
run. Every error carries:

| Field | Use it for |
|---|---|
| `what` | one sentence, for your log |
| `where` | instance, asset, connector, aperture, coordinates |
| `why` | the rule and its reasoning — read this before disagreeing |
| `expected` / `actual` | the numbers |
| `fix` | the corrective action in words |
| `fix_transform` | **the correction as data — apply it directly** |

`fix_transform` is the point. `{"translate": [0, 0, -0.372]}` means: add that to
the instance's position and re-run. Do not render to confirm; re-run the
validator. There is a test in `tests/test_validators.py` asserting that applying
`fix_transform` clears the error it came from.

### 3.7 Never let an engine generate collision

`collision.hulls` is a valid convex decomposition of the solid, and because
apertures were carved out of the same box set, doorways are holes in the
collision too. Turn `auto_generate_collision` **off** in Unreal, do not add a
convex `MeshCollider` in Unity, and use the shipped hulls. The adapters in
`adapters/` already do this. `collision.auto_convex_would_seal_apertures` tells
you when it matters.

### 3.8 Respect the placement policy, and read its reason

`placement.grid.policy` is one of:

| Policy | Meaning |
|---|---|
| `module` | must land on the bay grid — walls, floors, foundations |
| `module_xy` | plan position on the grid, height solved from geometry — roofs |
| `mated` | positioned by solving a connector; a grid check would fight the solver — leaves |
| `free` | decorative; grounding still enforced, position not — props |

`placement.allowed_rotations` is a list of legal yaws, or `null` for
unrestricted. 90-degree steps are not a style choice: at 90-degree steps an
axis-aligned box stays axis aligned, so occupancy, collision and aperture tests
stay *exact*. Every policy field ships with a `rationale` string. Read it before
you decide the rule is wrong.

### 3.9 Do not scale modular pieces

`placement.allowed_scaling` is `1.0 .. 1.0` for everything structural, with the
reason attached. Scaling moves connectors off the grid, and the piece stops
seaming with the rest of the kit. Props allow `0.75 .. 1.5` uniform.

---

## 4. Adding an asset

1. Write a function in `kits/shell_v1/parts.py` that returns the part dict.
   Build the solid with `BoxSet` (`.add`, `.subtract`, `.carve_aperture`) or
   `extrude_profile` for anything not axis-aligned.
2. **Never hard-code a dimension.** Every measurement comes from
   `kits/shell_v1/config.py`. Need a new constant? Add it there, and add a check
   to `config.validate()` that refuses combinations which would produce broken
   geometry.
3. **Cut holes with `carve_aperture`, not `subtract`.** `subtract` removes
   material; `carve_aperture` removes material *and records what the hole is
   for*, which is what makes traversal, collision and blockage checkable.
4. Declare connectors with `conn(...)`. Give every one a `normal` **and** a
   `tangent`; the tangent is what stops a piece mating correctly but rolled 90
   degrees.
5. Add the function to `PARTS`.
6. Run the loop:

```bash
./tessera build && ./tessera validate && python3 -m pytest tests -q
```

New assets are validated by the same 19 rules as everything else, so a bad pivot
or a connector floating in space fails the build rather than reaching a scene.

---

## 5. Definition of done

- [ ] `./tessera build` completes with no config errors
- [ ] `./tessera validate` exits `0`
- [ ] `python3 examples/workshop_shell/build.py` regenerates the layout
- [ ] `./tessera validate --layout examples/workshop_shell/layout.json` exits `0`
- [ ] `python3 -m pytest tests -q` is green
- [ ] `cd adapters/three && npm test` is green (JS must agree with Python)
- [ ] `python3 tools/export_parity.py && python3 tools/provenance.py` re-run
- [ ] `git diff build/catalog.json` shows only the changes you intended —
      a diff in an asset you did not touch means you altered shared geometry

---

## 5.5 What Tessera will not tell you

It has no opinion on what to build. Footprint, room programme, which wall gets a
window, where the entrance faces, whether it looks finished — all yours. The kit
is 22 structural parts and has no roads, terrain, fences, lighting or gameplay.

If the thing you were asked for is not expressible, **say so and say why** rather
than approximating it. A benchmark agent asked for "two storeys with interior
access" stacked three crates where a staircase belonged, and every geometric rule
passed. Refusing with a reason is a better answer than geometry that validates
and does not work.

## 6. Things that will waste your time

**Do not add a runtime dependency.** The core is standard-library Python 3.10+
and that is a feature: it runs in your sandbox, in CI, and on a machine with no
Blender. `pytest`, `jsonschema` and `trimesh` are test-only and never affect
output.

**Do not edit `build/`.** It is generated. Change the generator.

**Do not commit binaries you did not generate.** See
[`docs/provenance-policy.md`](docs/provenance-policy.md). Anything whose rights
are uncertain is quarantined, not included.

**Do not add third-party assets, even CC0 ones.** The whole licensing story
rests on "nothing external is read at any point". A single downloaded mesh
turns an auditable claim into an unverifiable one. Generate it instead.

**Do not weaken a validator rule to make your scene pass.** If a rule is wrong,
fix the rule *and* add a fixture in `tests/fixtures/broken_layouts.py` proving
it still catches the case it was written for. Deleting a check is not a fix.

**Do not use non-90-degree yaw on modular pieces.** Occupancy falls back to a
conservative bounding box and clash tests stop being exact. Props are exempt and
say so.

**Do not convert coordinates twice.** The shipped GLB files are already in
glTF's Y-up space. Layout transforms are in canonical Z-up space. Each adapter
converts in exactly one function; find it before you add a second one.

---

## 7. Working alongside other agents

Generation is safe to parallelise: every part function is pure, and a build is
deterministic — the same input produces byte-identical output, which is asserted
by `tests/test_kernel.py::test_build_is_deterministic`. The only shared mutable
surface is the `PARTS` list.

Validation is read-only and always safe to run concurrently.

Engine editors are **not** safe to parallelise. Unreal runs one Python
interpreter on the game thread; two agents issuing overlapping calls interleave
into one queue and produce confusing partial state. Prefer the headless adapter
scripts, which run in their own process.
