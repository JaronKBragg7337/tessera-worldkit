# Tessera Workshop

SPDX-License-Identifier: CC0-1.0

The public Workshop is a capability adapter for AI environments:

<https://jaronkbragg7337.github.io/tessera-worldkit/>

It is deliberately static, public, account-free and useful offline after the
first load. GitHub Pages is the delivery mechanism, not a dependency of the
contract. If the site disappears, the same operations remain in the repository
and in the downloadable sandbox pack.

## One core, four surfaces

| Receiver | What the Workshop gives it | What it does not pretend |
|---|---|---|
| Chat app | a sliced, fingerprinted Markdown/JSON capsule | that text-only confidence is validation |
| Browser agent | the capsule, an orthographic plan and a runtime-safe check | that five browser rules equal the full validator |
| Code sandbox | a self-contained ZIP with Python source, full catalog, selected generated assets, validation and repair | that the sandbox has an engine |
| Desktop agent | the complete repository and adapters | that an installed engine is licensed or activated |

Every surface comes from `build/catalog.json`. The website does not maintain a
copy of asset dimensions, connector frames or placement rules in handwritten
JavaScript.

## The hands

### Select

```bash
./tessera brief --only wall,id:*.doorway.* --format text
```

Selectors accept semantic roles, short asset-id globs, or explicit
`role:` / `id:` prefixes. A wall-only text brief is currently about 830 tokens,
instead of putting the roughly 56,700-token full catalog into context.

### Package

```bash
./tessera pack \
  --target sandbox \
  --only foundation,floor,wall,wall_opening,door \
  --prompt "build an enterable two-room workshop" \
  --out tessera-workshop-handoff.zip
```

`chat`, `browser`, `sandbox` and `desktop` targets receive the same catalog
fingerprint and different executable surfaces. ZIP entries have fixed metadata
and stable ordering, so the same input produces byte-identical packs.

### Check and repair

```bash
./tessera validate --layout layout.json --json
./tessera repair --layout layout.json --out repaired-layout.json --json
```

Repair never invents a transform. It tries transforms emitted by the validator
against copies of the layout, revalidates each candidate, and commits only the
candidate that strictly reduces the error count. If no offered transform proves
an improvement, it stops and reports a partial repair.

The browser uses the JavaScript runtime subset: known assets, support and
grounding, intersections and blocked traversable apertures. Its result is
labelled as a subset in the interface. The sandbox pack carries the full Python
validator and is the path for a complete claim.

## Rebuild the public site

```bash
python3 tools/build_workshop.py --out dist
python3 -m http.server 8000 --directory dist
```

The build copies the browser validator port, the current catalog and all four
validated examples, then generates chat and sandbox downloads. `dist/` is
ignored because GitHub Actions rebuilds it from the committed source.

## No backend yet

There is intentionally no database, login or server function in this version.
A static first release proves the browser hand and preserves the strongest
privacy and replaceability properties:

- pasted layouts never leave the device;
- no service credential can become a project dependency;
- anyone can fork and host the same Workshop;
- the repository stays the source of truth.

A future stateless full-validation endpoint can sit behind Vercel or another
replaceable host. Saved projects and collaboration could use Supabase later,
with row-level security and explicit export, but neither is needed for the
Workshop to work.
