# 0005 — A second implementation must be held to the first

SPDX-License-Identifier: CC0-1.0 · Status: accepted

## Context

Runtime consumers need to validate a layout at load time — is anything floating,
buried, unsupported, intersecting, or blocking a doorway. Shipping Python to a
browser is not an option, so the rules exist twice.

Two implementations that disagree are worse than one, because now nobody knows
which verdict to believe.

## Decision

Python is authoritative. The JavaScript port implements only the subset a
runtime consumer needs; grid, rotation, scale and connector policy stay in
Python as build-time concerns and are explicitly listed as out of scope.

`tools/export_parity.py` records Python's verdict on the known-good layout and
on all fifteen broken fixtures, plus reference transform conversions and every
grounding solve from the assembled scene. `adapters/three/test/parity.test.mjs`
holds JavaScript to that recorded ground truth on every commit.

## Consequences

- A rule change in Python that is not mirrored fails the JS test, so drift is
  loud rather than silent.
- The JS scope is declared in data (`js_covered_rules`), not in prose, so "the
  browser did not catch it" has a checkable answer.
- Transform conversion is tested numerically against Python output rather than
  by inspection, which is how sign errors in a handedness flip actually get
  caught.
