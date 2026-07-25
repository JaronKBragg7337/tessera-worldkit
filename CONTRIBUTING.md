# Contributing

SPDX-License-Identifier: CC0-1.0

## Rights warranty

By submitting a contribution you confirm **all** of the following:

1. You wrote it, or you otherwise hold sufficient rights to release it.
2. You release code under **0BSD** and assets, schemas and documentation under
   **CC0-1.0**, irrevocably.
3. It contains no third-party material — no mesh, texture, model, scan,
   photograph, code snippet or asset, regardless of its licence.
4. It does not copy or closely imitate a protected character, branded design,
   distinctive fictional creation, proprietary game asset or recognisable
   third-party artwork.
5. No employer, client or collaborator has a claim on it.

Point 3 is stricter than the licences require, and deliberately so. The whole
licensing story rests on *nothing external having been read at any point*. One
downloaded file turns an auditable claim into an unverifiable one, and everyone
building a paid product on this inherits that uncertainty. See
[`docs/provenance-policy.md`](docs/provenance-policy.md).

If you are unsure about anything, say so in the pull request. Uncertain material
is quarantined, not merged.

## Before you open a pull request

```bash
./tessera build                                          # regenerate
./tessera validate                                       # 19 asset rules
python3 examples/workshop_shell/build.py                 # reassemble
./tessera validate --layout examples/workshop_shell/layout.json
python3 -m pytest tests -q                               # full suite
(cd adapters/three && npm test)                          # JS must agree
python3 tools/export_parity.py                           # refresh JS ground truth
python3 tools/provenance.py                              # refresh the manifest
```

All of it must be green. CI runs exactly this.

## House rules

**No hard-coded dimensions.** Every measurement comes from
`kits/shell_v1/config.py`. Adding a constant means adding a check to
`config.validate()` that refuses combinations producing broken geometry.

**No runtime dependencies.** The core is standard-library Python 3.10+ and that
is load-bearing: it runs in CI, in an agent's sandbox, and on a machine with no
Blender. Test-only dependencies must not affect output.

**No committed binaries you did not generate.** `build/` is generated; change
the generator.

**Cut holes with `carve_aperture`, not `subtract`.** `subtract` removes
material. `carve_aperture` removes material *and records what the hole is for*,
which is what makes traversal, collision and blockage checkable.

**Every connector needs a tangent.** Without it a mate is a position plus an
ambiguous spin, and a piece can join correctly while rolled 90 degrees.

**Every restriction needs a rationale.** `allowed_scaling`, `allowed_rotations`
and `grid.policy` all carry a prose reason. A rule that explains itself is far
less likely to be deleted by someone — or something — trying to make a scene
pass.

**Never weaken a validator rule to make your scene pass.** If a rule is genuinely
wrong, fix the rule *and* add a fixture to `tests/fixtures/broken_layouts.py`
proving it still catches what it was written for. Deleting a check is not a fix.

## Adding an asset

See [`AGENTS.md` §4](AGENTS.md). Same procedure for humans; it is just written
for a reader who does not skim.

## Adding a validator rule

1. Add it to `validate/asset.py` or `validate/layout.py`.
2. Call `c.check("scope.rule.name")` so it appears in the coverage report even
   when it passes.
3. Write the diagnostic with all six fields, and a `fix_transform` if a
   correction exists.
4. Add a fixture to `tests/fixtures/broken_layouts.py` in the same commit. A
   rule with no fixture is a rule nobody has tested.
5. If runtime consumers need it too, port it to
   `adapters/three/src/tessera-core.mjs` and add its code to `JS_COVERED` in
   `tools/export_parity.py`.

## Style

Python: PEP 8, 4 spaces, 88 columns, no type-checker required but type hints
welcome. JavaScript: ESM, 2 spaces, no build step.

Comments explain **why**, not what. The code already says what it does.
