# 0003 — Diagnostics carry the correction as data

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

The failure this repository exists to remove is an agent burning a round-trip on
"something looks wrong, let me render it and guess". A diagnostic that says
`invalid placement` costs exactly as much as no diagnostic at all.

## Decision

Every diagnostic answers five questions, and where a correction exists, a sixth:

| Field | |
|---|---|
| `what` | one sentence, no jargon |
| `where` | instance, asset, connector, aperture, coordinates |
| `why` | the rule that broke and the reasoning behind it |
| `expected` / `actual` | the numbers |
| `fix` | the corrective action in words |
| `fix_transform` | **the correction as data** |

## Consequences

- The correction loop becomes apply-and-revalidate instead of
  render-and-squint. `{"translate": [0, 0, -0.372]}` is applied directly; nothing
  is drawn.
- `tests/test_validators.py::test_floating_fix_transform_actually_fixes_it`
  asserts that applying `fix_transform` clears the error it came from. A fix
  that does not fix is a test failure, not a documentation problem.
- `why` is written for a reader who might disagree. Rules that explain
  themselves are far less likely to be deleted by an agent trying to make a
  scene pass — which `AGENTS.md` explicitly forbids anyway.
- Reports record `coverage.checks_run`, because "no errors" only means something
  alongside the list of rules that were actually evaluated.
- Exit codes are meaningful: `0` passed, `1` found errors, `2` could not run.
  An agent can branch on them without parsing anything.
