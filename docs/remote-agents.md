# Remote and mobile agents

SPDX-License-Identifier: CC0-1.0

## The constraint that actually binds

An assistant running inside a phone app usually cannot inspect a live 3D scene,
drive Blender or Unreal, render repeatedly to diagnose a mistake, or reach the
user's filesystem. Those limits are real, but they are downstream of a harder
one: **it cannot afford to hold the world in context.**

The `shell_v1` catalog is about 30,000 tokens for twelve assets, and it grows
linearly with the kit. A forty-five-asset kit would be roughly 120,000 tokens
before a single wall is placed. No amount of cleverness about rendering helps if
the reference material does not fit.

So the framing that matters is not "the model cannot see". It is:

> Change the task from *look at the world and guess what is wrong* into *read
> structured spatial facts and emit valid transforms* — and make those facts
> cheap enough to hold.

Tessera does the first half by construction. `tessera brief` does the second.

## What a brief costs

```bash
./tessera brief --format text          # ~1,800 tokens
./tessera brief --format json --stats  # ~2,400 tokens
```

| | chars | approx tokens | share |
|---|---|---|---|
| Full catalog, minified | 108,089 | ~30,000 | 100% |
| Brief, JSON | 8,755 | ~2,400 | 8.1% |
| Brief, text | 6,535 | ~1,800 | 6.0% |

Twelve times smaller, and it is not a summary. It is the same facts with
everything placement does not use removed: occupancy boxes, collision hulls,
material and LOD tables, engine import settings, mesh statistics, provenance and
licence. What remains is dimensions, the grounding offset, grid and rotation
policy, support relations, connectors with full frames, apertures with clear
sizes, and clearance volumes — plus a header carrying the space convention, the
stack heights, the mating table and the default tolerances once instead of
twelve times.

## Why "sufficient" is a fact here, not a claim

Compression is easy; compression that still works is the question. So the digest
is round-tripped rather than trusted:

`tessera.brief.expand()` rebuilds the minimal catalog shape the placement solver
consumes, and
`tests/test_brief.py::test_a_scene_built_from_the_brief_alone_validates_against_the_full_catalog`
assembles a 37-instance workshop from a brief — the builder never sees the real
catalog — then validates the result **against the full catalog**. Zero errors.

If the digest ever drops something placement depends on, that test fails. It is
the same discipline as the JavaScript parity test: a second representation is
only useful if something holds it to the first.

## Three levels of capability, one contract

### Level 1 — specification only

The agent holds a brief, emits a `tessera.layout/1` document, and renders
nothing. Everything downstream is somebody else's job.

```
user request -> brief in context -> layout JSON -> handed off
```

Sufficient for: composing a building, laying out a street, placing props.

### Level 2 — remote validation loop

The agent submits its layout to something that holds the full catalog — a
server, a desktop agent, a CI job — and gets back a `tessera.report/1`. It
applies each `fix_transform` and resubmits.

```
layout -> validate -> report with fix_transform -> patch -> revalidate
```

This is the loop the diagnostics were designed for. The agent never sees
geometry; it sees `expected 0.5000, actual 0.8700, translate Z by -0.3700`, and
a test asserts that applying that delta clears the error. Each round trip is a
few hundred tokens rather than a screenshot.

### Level 3 — connected execution

The validated layout goes to an engine adapter, which builds the scene.

```
layout -> adapters/{three,blender,unreal,unity} -> playable scene
```

The same document serves all three levels, which is the point. A layout composed
on a phone at level 1 is byte-identical to one composed by a desktop agent with
the whole catalog in memory. **This is additive in both directions** — nothing
about the digest removes capability from an agent that has a filesystem and an
engine. It is the same contract at two budgets.

## The pin that makes the split safe

Splitting composition from execution introduces one failure mode that is worse
than anything it solves: the two sides holding different catalogs. A wall that
was 4.00 m when the layout was composed and 4.20 m when it was executed produces
a building full of gaps, and *nothing reports an error*, because both halves are
individually correct.

So every catalog carries a `fingerprint` — a hash of everything a consumer can
depend on, with timestamps excluded so a rebuild does not invalidate every
layout ever composed. Every layout records the fingerprint it was composed
against. The validator refuses a mismatch:

```
TSR_LAYOUT_CATALOG_MISMATCH
  declared 0e52a8027687   loaded 91b3fd0c14a2
  why  Every coordinate in this layout was solved from asset dimensions that
       may since have changed. Validating it against a different catalog would
       report success on a scene that no longer fits together.
```

A layout with no pin at all warns rather than fails, because refusing to
validate hand-written JSON would be obstructive — but it says so.

The brief carries the same fingerprint, so an agent that later needs collision
hulls knows exactly which catalog to ask for and can prove it received the right
one.

## Worked shape of a level-1 exchange

```
system:  <output of `tessera brief --format text`>        ~1,800 tokens
user:    a small workshop, one door, one window, room for a workbench
agent:   {"schema":"tessera.layout/1", "catalog":{"fingerprint":"0e52a802..."},
          "instances":[...]}                              ~1,200 tokens
server:  tessera validate --layout -> {"status":"failed", "diagnostics":[
           {"code":"TSR_LAYOUT_FLOATING","where":{"instance":"wall_03"},
            "fix_transform":{"translate":[0,0,-0.37]}}]}   ~300 tokens
agent:   applies the delta, resubmits                      ~100 tokens
server:  {"status":"passed"}
```

Under 4,000 tokens end to end for a validated building, with no image generated,
transmitted or interpreted at any point.

## What is still missing

Honest list, in the order it would help most.

1. **A hosted validation endpoint.** Level 2 currently assumes the caller can
   run Python. A small stateless service wrapping `validate` would remove that.
2. **Low-resolution previews.** Not for the agent to interpret — for the *user*
   to glance at. An orthographic plan render from occupancy boxes is cheap and
   needs no renderer.
3. **Layout diffs.** Resending a whole layout to change one wall wastes the
   budget the brief just saved. A patch format keyed on instance id would make
   the repair loop nearly free.
4. **Per-kit brief slicing.** `--only wall,roof` for agents that know what they
   need, taking a 2,400-token brief under 800.
5. **The intent layer.** Discussed below; it is the deepest of these and the
   easiest to get wrong.

## The intent layer, and the mistake to avoid

Geometry says where a thing is. It does not say *why*. An agent asked for "a
gas station with two entrances, a storage room, and enough clearance for the
player" is reasoning about rooms, entrances, cover and spawn areas, and none of
those words exist in the contract today.

The tempting move is to add `room` and `entrance` as asset roles. That is wrong,
and worth stating clearly: **a room is not a thing you place.** No asset is a
room. A room is a region that *emerges* from an arrangement of walls, and an
entrance is a relationship between a region, an aperture and the outside. Making
them asset fields would put them at the wrong level and guarantee they drift out
of sync with the geometry — the exact failure this project was built to end.

The right level is a **layout overlay**: declared regions, validated against the
geometry already present.

```json
"regions": [
  {"id": "sales_floor", "intent": "room", "bounds": {...},
   "entrances": ["wall_doorway_4m_01#door"]},
  {"id": "store", "intent": "storage", "bounds": {...},
   "entrances": ["wall_doorway_4m_02#door"]},
  {"id": "spawn_a", "intent": "spawn_safe_area", "bounds": {...},
   "requires": {"clear_height": 2.0, "reachable_from": "sales_floor"}}
]
```

The value is not the labels. It is that every one of them becomes **falsifiable**
against data the contract already carries:

| Declared intent | Checkable because |
|---|---|
| `room` is enclosed | occupancy boxes are exact, so a flood fill either escapes or does not |
| `entrance` is real | it must name a traversable aperture whose clear size admits the reference character |
| region is reachable | flood fill from another region must arrive through a declared entrance |
| `spawn_safe_area` is safe | it must contain a character capsule with no occupancy intersection |
| `cover` is cover | a sight line from a named direction must be blocked by occupancy |
| `loot_zone` is placeable | it must have floor beneath it and headroom above |

A semantic layer that cannot be checked is decoration, and decoration drifts. A
semantic layer that can be checked is a second contract, and it makes the
diagnostics far more useful to a remote agent: `TSR_REGION_UNREACHABLE — the
storage room has no entrance a character can pass through` is a sentence an
agent can act on without seeing anything.

This needs the flood-fill reachability work already scheduled in
[`ROADMAP.md`](../ROADMAP.md) M4, so it is designed here and built there rather
than half-shipped now. The same rule applied to characters: decide the
integration before the first vertex, then build it properly once.
