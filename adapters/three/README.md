# @tessera/three

Catalog loader, placement solver and runtime validator for three.js and plain
JavaScript.

`src/tessera-core.mjs` has no dependencies at all and runs under Node. It is a
deliberate port of the Python rules, and `test/parity.test.mjs` asserts that
both implementations reach the same verdict on the same layouts using ground
truth recorded by `tools/export_parity.py`. A second implementation that
disagrees with the first is worse than no second implementation.

`src/tessera-three.mjs` builds a scene. You pass three.js in rather than the
package depending on it, so no version is pinned and nothing gets bundled twice.

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { TesseraScene, validateLayout } from '@tessera/three/three';

const tessera = new TesseraScene({ THREE, GLTFLoader, baseUrl: './build/' });
const catalog = await tessera.loadCatalog('./build/catalog.json');
const layout  = await (await fetch('./examples/workshop_shell/layout.json')).json();

const report = validateLayout(layout, catalog);
if (report.status === 'failed') console.error(report.diagnostics);

scene.add(await tessera.buildLayout(layout));
scene.add(tessera.collisionHelper(layout));   // prove the doorway survived
scene.add(tessera.apertureHelper(layout));    // show where you can walk
```

## Coordinates

The shipped GLB files are already in glTF's Y-up right-handed space. Layout
transforms are in canonical Tessera space, which is Z-up right-handed.
`applyTransform` does the conversion `(x, y, z) -> (x, z, -y)`, with yaw about
canonical Z becoming rotation about three.js Y. Do not convert twice.

## Scope

The runtime validator implements the rules a consumer needs at load time:
floating, buried, unsupported, intersecting, blocked apertures and unknown
assets. Grid, rotation, scale and connector policy are build-time concerns and
stay in the Python validator, which is authoritative.

```
npm test
```
