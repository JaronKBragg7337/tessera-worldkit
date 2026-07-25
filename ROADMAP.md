# Roadmap

SPDX-License-Identifier: CC0-1.0

## Where this is right now

**Done and verified.** The placement contract, the exact geometry kernel, 18
original parts, 41 validation rules with agent-readable diagnostics, the
reachability solver, the context-budgeted brief, three validated example
buildings, and four verified targets — core, three.js and Blender in CI, Unreal
against a real 5.6.1 install.

**Next, in order.** Interior walls, doorways and corners come first: without
them an interior room can be closed but not entered, which blocks every
multi-room building — safe house, checkpoint, warehouse, village. Then the gable
end wall and second-storey walls, which the renders exposed. Then the intent
layer, which is the largest remaining reduction in agent reasoning but benefits
from having more to reason about.

**Read first if you are new here.** [`AGENTS.md`](AGENTS.md) if you are an
agent. [`docs/decisions/0008`](docs/decisions/0008-scope-and-replaceable-layers.md)
for why scope is wide and coupling is not.
[`docs/conformance.md`](docs/conformance.md) for what compatibility means.
[`benchmarks/constrained_agent/`](benchmarks/constrained_agent/) for how the
project tests itself against a real agent.

---

Every milestone below has acceptance tests that either pass or do not. There are
no items reading "support characters" or "add assets", because those cannot be
finished — only abandoned.

**Ordering principle:** rank work by how much agent back-and-forth it removes,
not by what is missing from an asset list. Forty assets an agent places
correctly on the first attempt are worth more than two hundred it has to be
corrected on.

---

## M1 — The contract, proven on a vertical slice ✅ complete

Prove the central claim on twelve parts rather than attempting a library.

- [x] Exact box-set CSG kernel, pure standard library, deterministic
- [x] Watertight surface extraction with T-junction repair
- [x] `tessera.asset/1` covering every field in the placement contract
- [x] Twelve original parts: foundation, floor, wall, corner, doorway, door,
      window wall, window, roof panel, ridge cap, crate, workbench
- [x] Pure-Python GLB writer, plus OBJ/MTL
- [x] 19 asset rules and 17 layout rules, each with a diagnostic carrying
      what/where/why/expected/actual/fix
- [x] `fix_transform` on every correctable error
- [x] Workshop shell assembled from metadata alone
- [x] JSON Schemas that are tested against the shipped data
- [x] JavaScript port held to Python's verdict on every commit
- [x] 0BSD/CC0 split with a machine-readable per-asset provenance manifest

**Acceptance, all met**

| Test | Target | Actual |
|---|---|---|
| Manual placement corrections in the demonstration | 0 | **0** |
| Instances solved from the contract | 100% | **41 / 41** |
| Seams discovered and verified automatically | ≥ 30 | **46** |
| Layout rules with a fixture that breaks them | 100% | **15 / 15** |
| Asset rules with a fixture that breaks them | 100% | **12 / 12** |
| Assets independently verified watertight | 12 / 12 | **12 / 12** |
| Runtime dependencies | 0 | **0** |
| Engines with an executable, CI-verified path | ≥ 1 | **1** (JS/glTF) |

---

## M2 — Engine adapters promoted from unverified

Three adapters are written but have never been run against their engine.
[`docs/engine-support.md`](docs/engine-support.md) says so. This milestone makes
that table read `verified-locally` or better.

- [x] **Blender — done, and `verified-in-ci`.** `pip install bpy` gives a
      headless Blender as a Python module, so `tools/verify_blender.py` runs on
      every commit with no display and no manual step. 81 checks against Blender
      5.0.1: bounds to ~1e-8 m on all 18 assets, triangle counts, hull counts, a
      doorway's collision void where its aperture is, a 37-instance layout at
      its declared transforms, and FBX export preserving `UCX_<mesh>_##`.
- [x] **Unreal 5 — done, `verified-locally`.** `tools/verify_unreal.py` runs
      headless against Unreal 5.6.1: 94 checks, 0 failed. Bounds to 0.0000 cm on
      all 18 assets, hull counts matching `collision.hull_count`, a 37-instance
      layout at its declared transforms, and the doorway aperture void where
      Unreal's own auto-collision would have sealed it. Not in CI because the
      engine is a licensed multi-gigabyte install.
- [ ] Unreal: a `PlayerStart` outside the building pathing through the doorway
      to a point inside, so the aperture is proven at runtime and not only in
      the collision data.
- [ ] **Unity — blocked on a licence, not on work.** Unity 6000.4.11f1 is
      installed on the verification machine and batch mode refuses to start with
      "Found 0 entitlement groups and 0 free entitlements". One interactive sign
      in to Unity Hub unblocks it; see `docs/engine-support.md`. Then: all 18
      GLBs import as prefabs, `BuildLayout` instantiates every instance, a
      `CharacterController` of the reference dimensions walks through the
      doorway in play mode, and no convex `MeshCollider` exists in the scene.
- [ ] **three.js.** `adapters/three/viewer.html` renders the workshop, and an
      automated screenshot diff against a committed reference stays within
      tolerance.
- [ ] A `--check` mode in each adapter that exits non-zero on mismatch, so the
      above can run headless.

**Done when** the support matrix contains no `script-provided-unverified` row,
and each promoted row names the command that proves it. Blender and Unreal are
done; Unity is not.

---

## M2.5 — Constrained-agent benchmark ✅ complete

A real draft from a model with no checkout, terminal, engine or renderer, run
and repaired using only validator output. See
[`benchmarks/constrained_agent/`](benchmarks/constrained_agent/).

- [x] The draft preserved verbatim and pinned as a regression fixture
- [x] Run unchanged, every failure classified as API misuse, geometric
      invalidity, incomplete contract or missing semantic capability
- [x] Repaired to zero errors in four rounds with nothing rendered
- [x] `TSR_LAYOUT_UNBALANCED` and `TSR_LAYOUT_UNDERSUPPORTED` added, because a
      4 x 4 m slab cantilevered off one wall edge used to validate clean
- [x] Documented which mistakes `tessera brief` would have prevented

**Acceptance, all met**

| Test | Target | Actual |
|---|---|---|
| Structural defects caught that a human reviewer found | all | **all, plus 2 more** |
| Repair rounds to a valid layout | < 6 | **4** |
| Renders or screenshots needed | 0 | **0** |
| New rules with regression tests, no false positives on known-good scenes | yes | **yes** |

---

## M3a — Traversal, and reachability as a measured property ✅ complete

The benchmark showed a second storey with interior access was not expressible,
so a constrained agent asked for one had no honest option. Closed by adding the
parts *and* the check, because the parts alone would only have moved the lie one
level up.

- [x] `stair.straight.4m` — lands exactly on the floor above, one collision hull
      per tread, headroom declared as clearance
- [x] `stair.stoop.1m2` — exists because the solver refused a finished scene
      whose door was open and whose floor was 0.50 m above the ground outside
- [x] `floor.opening.4m` — a stairwell carved as a vertical aperture
- [x] `beam.4m` and `column.3m` — column plus beam equals wall height exactly,
      enforced by `config.validate()`, so a floor lands on one plane
- [x] `railing.4m`
- [x] `src/tessera/navigate.py` — character-aware flood fill over exact occupancy
- [x] `layout.reachability` claims, proven or refuted by the validator
- [x] `TSR_LAYOUT_UNREACHABLE`, `TSR_LAYOUT_STAIR_UNUSABLE`
- [x] The two-storey safe house the benchmark could not have

**Acceptance, all met**

| Test | Target | Actual |
|---|---|---|
| Two-storey building with interior access, 0 manual corrections | yes | **yes, 36 instances** |
| Routes proven rather than asserted | all | **4 / 4** |
| Removing the stair makes the claim fail | yes | **yes** |
| Stacked crates rejected as a staircase | yes | **yes** |
| False positives on known-good scenes | 0 | **0** |
| Solver never claims a route that does not exist | conservative | **box test, not capsule** |

---

## M3 — Kit expansion, contract unchanged

The contract should not need to change to describe more building. If it does,
that is the finding.

- [x] Straight stair, stoop, floor with a stairwell, beam, column, railing — M3a
- [ ] L-turn and half-landing stairs, ramp, ladder
- [ ] **Interior corner and doorway pieces**, so an interior room can be closed
      *and* entered. The L corner closes a perimeter without overlap but carries
      no opening, which is why the benchmark repair could only build an alcove
- [ ] A shorter beam, so a stairwell can be trimmed without a beam crossing the
      flight — the two-storey example is shaped around not having one
- [ ] **A gable end wall.** Rendering the workshop showed daylight straight
      through both ends of the roof. Every rule passes, because an open gable is
      not floating, buried, intersecting or unreachable — it is simply a missing
      piece, and only a picture showed it. Worth remembering that the validator
      is not a substitute for looking once.
- [ ] **Second-storey perimeter walls, and a roof that can sit on them.** The
      two-storey example has no roof, and cannot: the mezzanine floor finishes
      at 3.70 while the roof bears at 3.50, so a gable would cut through it. A
      real second storey needs its own walls above the mezzanine to carry the
      roof.
- [ ] Junctions: inner-corner trim, wall-to-floor trim, column caps — the pieces
      that stop assembled kits showing seams
- [ ] Roof: hip corner, cross-gable valley, eave fascia, dormer
- [ ] Openings: double door, garage/roller door, glazed double-height window
- [ ] Ground: road straight/corner/T/cross, kerb, crossing, gravel, concrete pad
- [ ] A second visual theme sharing the same grid and connector kinds
- [ ] LOD generation with `lods[]` populated and screen sizes tested

**Acceptance**

- [ ] ≥ 45 assets, all passing the 19 asset rules unchanged
- [ ] A two-storey building with an internal staircase assembles with 0 manual
      corrections and 0 validation errors
- [ ] A 4 × 4 block road network assembles from connectors alone
- [ ] `tessera.asset/1` is unchanged, or the change is an additive minor version
      with a written migration note
- [ ] Total kit triangles under 60k

---

## M1.5 — Constrained-context agents ✅ complete

Added after the observation that the binding limit for a phone assistant is not
vision but context budget: the catalog was ~30,000 tokens for twelve assets and
grows linearly.

- [x] `tessera brief` — a digest at 8% of the catalog (~2,400 tokens JSON,
      ~1,800 as text), carrying everything placement needs and nothing else
- [x] `tessera.brief/1` schema, tested against the shipped data
- [x] `brief.expand()` round-trip, so sufficiency is testable
- [x] Catalog `fingerprint` and layout pinning, with
      `TSR_LAYOUT_CATALOG_MISMATCH` for a mismatch and a warning when unpinned
- [x] `docs/remote-agents.md` — the three capability levels, the repair loop,
      and the design for a checkable intent layer

**Acceptance, all met**

| Test | Target | Actual |
|---|---|---|
| Brief size relative to the catalog | < 15% | **8.1%** |
| Brief in approximate tokens | < 4,000 | **~2,400** |
| Scene assembled from a brief alone, validated against the full catalog | 0 errors | **0 errors, 37 instances** |
| Catalog mismatch detected | yes | **yes** |
| Fingerprint stable across rebuilds, unstable across geometry changes | yes | **yes** |

---

## External review, 2026-07-25

An independent evaluation was asked to behave like an agent trying to build a
small environment and to be neither charitable nor overly critical. Its central
finding is accepted and the README has been corrected to match it:

> Tessera stops an agent from guessing measurable placement facts. It does not
> yet stop the agent from guessing what world should be built.

It scored geometric placement, collision and agent onboarding highly, and asset
breadth (3/10), semantic world generation (2/10) and visual production readiness
(3/10) low. That split is fair and is the real shape of the project today.

Acted on immediately:

- [x] The README's "stops guessing" claim corrected, and a "what it does not do"
      section added rather than left to be discovered
- [x] **Validation no longer depends on the author remembering to ask.** Every
      traversable opening is audited whether or not a route was declared, and a
      layout with openings but no claims is told so. This was the sharpest
      technical finding: a layout could omit the one check that mattered and
      still pass clean
- [x] The workshop and single-storey safe house, both of which were silently
      unaudited, now carry stoops and declared routes
- [x] `docs/conformance.md`, so "Tessera-compatible" can mean something other
      than "used our code"

Logged, in the review's own priority order:

- [ ] **1. Intent schema and intent validation** — the largest remaining burden.
      Designed in `docs/remote-agents.md`, built in M4
- [ ] **2. Automatic enclosure and roofing** — M4
- [ ] **3. Interior wall, doorway and corner system** — M3
- [ ] **4. Completeness validation.** Detect an expected enclosure surface that
      is simply absent. This is the gable-end class of defect: every rule passes
      and a picture shows daylight through the building
- [ ] **5. `tessera repair`** — apply every `fix_transform` to a fixed point
- [ ] **6. Road, terrain, gate, fence and checkpoint assets** — M3
- [ ] **7. Runtime navigation verified in every supported engine** — M2
- [ ] **8. A verified interactive browser demo.** No public demo is currently
      discoverable, which the review correctly noted
- [ ] **9. A multi-agent benchmark measuring total tokens and elapsed work**
      against a conventional workflow. Catalog compression is measured;
      end-to-end saving is not
- [ ] **10. More visual themes and production detailing**

On asset breadth: 3/10 is an accurate snapshot and **not a policy**. The kit
will grow substantially — M3 alone adds traversal variants, interior walls and
doorways, junction trim, more roof forms, roads, ground, openings and a second
theme, and there is no ceiling after that. What is deliberate is the *ordering*:
assets are ranked by how much agent guesswork they remove, not by count. Forty
assets an agent places correctly on the first attempt are worth more than two
hundred it has to be corrected on, and the eighteen that exist were chosen to
prove the contract end to end rather than to look like a library. Growth is also
not the only route — under
[`decisions/0008`](docs/decisions/0008-scope-and-replaceable-layers.md) anyone
can supply their own kit and keep everything else.

One criticism genuinely is not a defect: validators will never establish
unspecified intent. That is what layer 5 is for, not a hole in layers 0–4.

---

## M4 — Layout intelligence and the intent layer

Today an agent must still decide *where* a building goes. This milestone gives
it a solver for the parts that are mechanical.

- [ ] `Builder.enclose(footprint)` — walls a rectangular or L-shaped plan
      automatically, choosing corners, straights and openings
- [ ] `Builder.roof(footprint, style)` — gable, hip and shed roofs solved from
      the plan
- [ ] Pathability check: flood-fill the walkable volume from a seed and report
      unreachable rooms, using the aperture data already present
- [ ] `tessera repair --layout` — apply every `fix_transform` and re-validate,
      iterating to a fixed point or reporting what it cannot fix
- [ ] A cost metric per layout: guesses avoided, corrections applied
- [ ] **A checkable intent layer.** Regions declared as a layout overlay --
      `room`, `entrance`, `storage`, `cover`, `loot_zone`, `spawn_safe_area` --
      not as asset roles. A room is not a thing you place; it emerges from an
      arrangement of walls, and putting it on an asset would guarantee it drifts
      out of sync with the geometry. Designed in
      [`docs/remote-agents.md`](docs/remote-agents.md); it depends on the flood
      fill above, which is why it lives here rather than being half-shipped.
- [ ] A layout patch format keyed on instance id, so a repair round trip costs
      hundreds of tokens rather than a whole layout
- [ ] `--only <roles>` slicing for briefs, taking a 2,400-token digest under 800
- [ ] Orthographic plan previews rendered from occupancy boxes -- for the *user*
      to glance at, not for an agent to interpret

**Acceptance**

- [ ] `enclose()` produces a sealed, validated shell for 10 random rectangular
      plans between 2×2 and 6×4 bays, 0 errors each
- [ ] Pathability correctly reports the room as unreachable when the door leaf
      is closed and reachable when it is open
- [ ] `tessera repair` fixes ≥ 90% of injected single-instance perturbations in
      one pass across all 15 fixtures
- [ ] Every declared region intent is falsifiable: an enclosure claim fails on a
      wall-less region, an entrance claim fails when it names an aperture the
      reference character cannot pass, a `spawn_safe_area` fails when a
      character capsule intersects occupancy, and `cover` fails when the sight
      line from its named direction is unobstructed

---

## M5 — Characters

Designed in [`docs/characters.md`](docs/characters.md) before any geometry
exists, because the integration decision has to be made first. **One character
end to end, held to a quality bar, before any second character.**

Acceptance tests are listed in that document. Summary:

- [ ] one character generated end to end by script, from parameters only
- [ ] every vertex has 1–4 normalised influences
- [ ] no joint through its full range loses more than 8% local volume or
      self-intersects
- [ ] the character's capsule passes through `wall.doorway.4m` in the assembled
      workshop, checked by the existing aperture rules
- [ ] a weapon mesh mates `socket_hand_r` and passes connector validation
- [ ] Unity Humanoid retarget reports no missing required bones
- [ ] Unreal skeleton import reports no retarget warnings
- [ ] provenance shows `origin: original-generated`, `source_inputs: []`

**Explicitly not a goal:** a large character count. Ten mediocre characters are
worth less than one that deforms correctly and retargets cleanly.

---

## Not planned

Recorded so nobody spends a week discovering these were deliberate.

| Not doing | Why |
|---|---|
| A renderer | Tessera describes; it does not draw |
| A USD-competitive scene format | `layout.json` is a transform list, on purpose |
| Third-party asset ingestion, even CC0 | The licensing claim rests on nothing external being read. See [`docs/provenance-policy.md`](docs/provenance-policy.md) |
| Runtime dependencies | Zero is a feature: it runs in an agent's sandbox |
| Non-axis-aligned rotation for modular pieces | Exactness of occupancy and collision is worth more than free rotation |
| Photoreal materials | Shading here is geometric; PBR maps are a downstream choice |
