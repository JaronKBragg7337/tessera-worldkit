# Constrained-agent benchmark

SPDX-License-Identifier: CC0-1.0

A real test, not a simulated one.

DeepSeek was asked from a phone chat to *"make a two-story survivor safe house
with one guarded entrance, a storage room and a clear spawn area"*, given
nothing but the GitHub URL of this repository. It had no checkout, no terminal,
no Python, no engine, no connectors and no ability to run or render anything. It
browsed the repository as web pages and wrote a script.

That script is preserved verbatim as
[`deepseek_safehouse_v1.py`](deepseek_safehouse_v1.py). It has been run
unchanged, repaired using only validator output, and the whole process recorded
below.

## What it got right

Working only from public documentation, it found the correct asset namespace and
every asset id, identified `Builder`, `ground()`, `mate()` and `autoconnect()`,
described their semantics accurately, and reproduced the structure of the
workshop example — nine pads, nine slabs, four L corners, middle perimeter
segments, leaves mated into apertures, `on=` for support-solved heights.

It did not invent coordinates, hallucinate asset names, or fall back to generic
three.js. That is the thing being tested, and it passed.

## What it got wrong, and what caught it

| # | Defect | Detected by | Severity |
|---|---|---|---|
| 1 | `surface="top"` on a corner piece, which has `top_x` / `top_y` | `AssemblyError` at build time, naming the six valid connectors | crash |
| 2 | West wall created twice at the same transform | `TSR_LAYOUT_INTERSECTION`, `1.7572 m³` shared — *exactly* one wall's full volume | error |
| 3 | "Storage partition" placed at the east perimeter wall's position | `TSR_LAYOUT_INTERSECTION`, another full `1.7572 m³` | error |
| 4 | Storage doorway at `x=11.5, y=4.5`, off the 0.20 m lattice | `TSR_LAYOUT_OFF_GRID` ×2, with the snap delta | error |
| 5 | Only 4 of 9 second-floor slabs created; `.get(key, floors[key])` silently fell back to the ground floor | `TSR_LAYOUT_BURIED` ×21, all at exactly `0.18 m` — the plinth height | error |
| 6 | Second-floor slab bearing on a single wall edge | `TSR_LAYOUT_UNBALANCED` — **new rule, added because of this** | error |
| 7 | A floor slab whose highest support was a workbench | `TSR_LAYOUT_FLOATING`, then `TSR_LAYOUT_UNDERSUPPORTED` — **new rule** | error → warning |
| 8 | Guard post placed inside the door swing | `TSR_LAYOUT_CLEARANCE_VIOLATED` | warning |
| 9 | A "spawn marker" crate clashing with the workbench | `TSR_LAYOUT_INTERSECTION`, `0.0096 m³` | error |
| 10 | Three stacked crates presented as a staircase | **not detected** — needs M4 reachability | gap |
| 11 | "Clear spawn area" asserted, never tested | **not detected** — needs the M4 intent layer | gap |
| 12 | "Guarded entrance" as a narrative label | **not detected** — needs the M4 intent layer | gap |
| 13 | Reported `Validation errors: 0` without running anything | not a code defect; the model said it could not execute, then quoted output anyway | — |

**36 errors on the first successful run.** Every structural defect a human
reviewer identified was caught, plus two the reviewer missed (#4 and #7).

## Repair log

Every repair came from a diagnostic. **Nothing was rendered or screenshotted at
any point.**

| Round | Action | Result |
|---|---|---|
| 1 | Ran unchanged | `AssemblyError`: corner has no connector `top`; error listed the six it does have |
| 2 | Changed `"top"` → `"top_x"` (one line) | Runs. 63 instances. **36 errors, 1 warning** |
| 3 | Removed the duplicate west wall; moved the storage partition onto the bay line | **28 errors** |
| 4 | Redesigned the second storey — see below | **2 errors**, both `0.0002 m³` plinth clips |
| 5 | Shifted the partition one grid step west | **0 errors, 0 warnings** |

Four rounds from a crash to a validated building, with no visual inspection.

Round 4 was a redesign rather than a mechanical fix, and that distinction
matters: the requested building **is not expressible in `shell_v1`**.

## The finding that matters most

> A second storey with interior access cannot be built from this kit, and no
> amount of repairing the script changes that.

`shell_v1` has no stair, no ladder, no beam, and no floor piece with an opening.
A second-storey slab can only bear on a bay perimeter, and there is no way up.
DeepSeek's stacked crates were not carelessness — they were a model routing
around a missing asset, and producing geometry the validator accepts and a
player cannot climb.

So the benchmark exposed a **kit gap, not just an agent error**. The repaired
[`examples/safehouse`](../../examples/safehouse) builds the three features that
*are* expressible — guarded entrance, storage alcove, clear spawn bay — and says
plainly in its own docstring which requested feature it did not build and why.
That is the behaviour the framework should encourage: refuse and explain, rather
than produce something that validates and does not work.

### The gap is now closed

Six parts were added — stair, stoop, floor with a stairwell, beam, column,
railing — and, more importantly, **reachability became something the framework
measures**. Adding the stair alone would have moved the lie one level up: a
staircase that exists but nobody can climb validates exactly as well as three
crates did.

[`examples/safehouse_two_storey`](../../examples/safehouse_two_storey) is the
building that was asked for. It declares four routes and the validator proves
each by flooding the walkable volume. Delete the staircase and it fails; replace
it with stacked crates and it fails. Both are regression tests.

Building it surfaced two more defects that had been sitting in the validator:

* the support threshold was applied **per box** rather than per instance, so a
  floor resting squarely on two beams saw six 1.3% contacts, discarded every one
  of them, and reported itself floating two metres above a staircase. Anything
  with detailing on it — a lightened beam, a capped column — hit this.
* the step-up limit was 25 cm, which makes *every* real staircase unclimbable: a
  character with a 35 cm radius always has the tread two steps ahead inside its
  body box, and that tread is 40 cm up. Unreal's default `MaxStepHeight` is
  45 cm; modelling a tighter limit than the runtime uses produces false refusals
  on correct geometry.

And one in the kit itself: the workshop's front door was open, wide enough,
collision-correct — and 0.50 m above the ground outside with no step. Nobody
could get in. That is what `stair.stoop.1m2` exists for.

## Two rules exist because of this benchmark

Running the draft surfaced a genuine hole. This validated clean before:

```python
b.ground("tsr:shell/floor.slab.4m", 0, 0, on=wall, surface="top")   # 4x4 m slab
```

A 4 × 4 m floor slab held up by one 4 × 0.2 m wall edge — a 1.8 m cantilever —
passed, because it technically rested on something and cleared the 2% coverage
floor.

Coverage alone cannot fix it: a legitimate second-storey floor bearing only on
four perimeter walls sits at roughly 20% and is perfectly correct. The
discriminator is physical — **an object topples when the centroid of its
footprint leaves the convex hull of its contact patches**:

* `TSR_LAYOUT_UNBALANCED` (error) — centroid outside the hull. It falls.
* `TSR_LAYOUT_UNDERSUPPORTED` (warning) — balanced but touching very little. A
  slab centred on a workbench does not topple, so it is not an error; it is
  almost certainly not what anyone meant.

Both are regression-tested, including the two cases a naive implementation gets
wrong: the good workshop (no false positives) and a real four-wall second storey
(must pass).

## What `tessera brief` would have prevented

DeepSeek read GitHub HTML. It never saw a brief. Had it been given
`tessera brief --format text` — about 1,800 tokens — instead:

| Defect | Prevented? | Why |
|---|---|---|
| #1 corner `top` vs `top_x` | **yes** | the brief lists every connector id, kind and frame per asset |
| #4 off-grid doorway | **yes** | `GRID module 4.00 snap_xy 0.20` is in the header |
| #5 second-floor fallback | partly | `rests_on` is listed, but nothing says which supports are *load-bearing* |
| #6 cantilever | partly | sizes are present; the balance rule now catches what a reading cannot |
| #10 stairs | **no** | the brief cannot list an asset that does not exist |
| #11/#12 semantics | **no** | needs the M4 intent layer |

So the brief would have prevented the only hard crash and one of the two
off-grid errors outright. The rest needed either the validator or assets that do
not exist yet — which is the correct division of labour: the digest carries
facts, the validator carries judgement.

## Reproduce

```bash
./tessera build
cp benchmarks/constrained_agent/deepseek_safehouse_v1.py /tmp/v1.py
mkdir -p examples/_v1 && cp /tmp/v1.py examples/_v1/build.py
python3 examples/_v1/build.py          # AssemblyError, round 1
```

The v1 script is pinned as a regression fixture in
`tests/test_benchmark.py`: if a future change stops the validator catching a
constrained agent's mistakes, that test fails.
