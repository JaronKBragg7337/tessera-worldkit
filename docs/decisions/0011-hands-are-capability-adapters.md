# 0011 — Hands are capability adapters

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

A desktop coding agent can hold a checkout, execute Python, inspect files, run
an engine and keep its work. An assistant in a phone app may have only text and
attachments. A cloud agent falls somewhere between those two.

Treating the least capable environment as the product ceiling would discard the
capability of stronger agents. Treating every environment as if it were a
desktop wastes turns on commands that cannot run.

## Decision

Tessera exposes the same contract through progressively richer hands:

1. **chat** — a compact, fingerprinted specification;
2. **browser** — specification, plan preview and a labelled runtime subset;
3. **sandbox** — zero-dependency source, full validation, repair and selected
   generated assets;
4. **desktop** — the complete repository and engine adapters.

The layers are additive. A richer target never receives a weakened contract in
exchange for convenience.

Hosted surfaces are replaceable adapters. GitHub Pages currently hosts the
Workshop because it is static and public. It does not own projects, identities
or canonical data. The repository builds the site and remains useful when the
host is absent.

## Why repair revalidates candidates

`fix_transform` makes an error actionable, but a connection exists in a graph.
Moving one end of a broken seam can move the break to its other end. Applying
every offered transform at once therefore is not conservative.

`tessera repair` executes each offered transform on a copy, runs the validator
again, and commits only a candidate that strictly reduces the total error
count. This makes the repair tool a hand for the validator rather than a second
source of placement judgment.

## Consequences

- App-based AIs can receive useful execution surfaces without pretending they
  have a local machine.
- Desktop agents and human developers keep the full repository and adapters.
- A hosted full-validation API can be added later without changing the
  contract.
- Saved projects and identity remain out of the first public release, avoiding
  a backend dependency before persistence is actually needed.
- Browser validation must state its coverage. It may never present its runtime
  subset as equivalent to the full Python validator.
