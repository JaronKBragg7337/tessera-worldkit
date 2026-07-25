# 0008 — Scope is wide; every layer is replaceable

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

Two framings were considered for how far Tessera should go.

The first was a fence: decide what Tessera will never become, and refuse
anything outside it. That protects the project from swallowing gameplay, but it
also means telling people "we don't do roads" when roads are obviously wanted.

The second, which is the one adopted, came from the project owner:

> Maybe it's not the scope that needs to end. We can do full and all, but people
> can also choose to leave things out if they have another way.

That is the better position, and it is more precise than it first sounds. What
kills a framework is not breadth. It is **coupling**. A project that grows roads,
terrain, characters and interiors is only a problem if taking one of them out
breaks the rest.

## Decision

Scope may grow without limit. Coupling may not.

The rule for adding anything is not "is this in scope" but:

> **Can somebody who already has their own version of this drop ours, keep
> everything else, and still be Tessera-compatible?**

If yes, build it. If no, the seam is wrong and the seam is the thing to fix
first.

## The layers

Each layer depends only on the contract, never on the layer below it.

| Layer | What it is | Replace it if you have |
|---|---|---|
| **0 — Contract** | `tessera.asset/1`, `tessera.layout/1` | nothing; this is the only hard dependency |
| **1 — Geometry kernel** | the box-set CSG and mesh extraction | your own modelling pipeline |
| **2 — Kit** | `shell_v1`, the replaceable parts kit | your own assets |
| **3 — Validation** | the asset and layout rules | your own checker |
| **4 — Assembly** | `Builder`, connector solving, `autoconnect` | your own placement code |
| **5 — Intent** | regions, rooms, entrances *(planned)* | your own level-design tooling |
| **6 — Adapters** | Blender, Unreal, Unity, three.js | your own importer |

A consumer picks the layers they want. Somebody with a finished art pipeline
takes layers 0, 3 and 6 and supplies their own 1 and 2. Somebody with a level
editor takes 0–4 and ignores 5.

## What this obliges us to do

Breadth is only safe if the seams are real, so:

1. **Every layer must be usable without the layer below it.** `tessera validate`
   already runs against any conformant `catalog.json`, whoever produced it. That
   property is now a rule rather than an accident, and must not regress.
2. **Conformance has to be declarable.** See
   [`docs/conformance.md`](../conformance.md). Without stated levels, "compatible"
   means "used our code", and no ecosystem forms around that.
3. **New layers ship with their seam.** A road system that only works with our
   road assets is a coupling failure, not a feature.
4. **No layer may become a runtime dependency of the contract.** The contract has
   zero dependencies and that is what makes it safe to depend on.

## What this deliberately does *not* decide

That Tessera should build everything. Only that nothing is excluded *by category*,
and that anything included must be removable. Priorities still live in
[`ROADMAP.md`](../../ROADMAP.md), and the ordering principle there is unchanged:
rank work by how much agent back-and-forth it removes.

## The one genuine boundary

Not a scope limit — a truthfulness limit.

Tessera must not claim to have removed reasoning it has not removed. An external
evaluation put this precisely:

> Tessera stops an agent from guessing measurable placement facts. It does not
> yet stop the agent from guessing what world should be built.

That is accurate, and the README has been corrected to match it. Layer 5 exists
to narrow that gap; until it does, the gap is stated rather than papered over.
