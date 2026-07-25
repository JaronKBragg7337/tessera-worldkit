// The JS validator must agree with the Python validator.
// SPDX-License-Identifier: 0BSD
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validateLayout, Transform, solveGround } from '../src/tessera-core.mjs';

const root = new URL('../../../', import.meta.url).pathname;
const catalog = JSON.parse(readFileSync(`${root}build/catalog.json`, 'utf8'));
const layout = JSON.parse(readFileSync(`${root}examples/workshop_shell/layout.json`, 'utf8'));
const expected = JSON.parse(readFileSync(`${root}build/parity-expected.json`, 'utf8'));

test('the known-good layout passes in JavaScript too', () => {
  const report = validateLayout(layout, catalog);
  assert.equal(report.status, 'passed',
    JSON.stringify(report.diagnostics.slice(0, 3), null, 2));
});

test('JS and Python agree on every broken fixture', () => {
  for (const [name, want] of Object.entries(expected.cases)) {
    const broken = JSON.parse(readFileSync(`${root}build/fixtures/${name}.json`, 'utf8'));
    const report = validateLayout(broken, catalog);
    const codes = new Set(report.diagnostics.map((d) => d.code));
    if (want.js_should_detect) {
      assert.ok(codes.has(want.code),
        `${name}: JS produced ${[...codes]} but Python found ${want.code}`);
    }
  }
});

test('transform conversions match the Python reference exactly', () => {
  for (const c of expected.transforms) {
    const t = new Transform(c.position, c.rotation, c.scale);
    assert.deepEqual(t.point(c.input_point).map((v) => Number(v.toFixed(6))),
                     c.expected_point);
    assert.deepEqual(t.direction(c.input_direction).map((v) => Number(v.toFixed(6))),
                     c.expected_direction);
  }
});

test('the grounding solver reproduces the assembled heights', () => {
  for (const c of expected.grounding) {
    const record = catalog.assets.find((a) => a.id === c.asset);
    const solved = solveGround(record, c.surface_z, c.x, c.y, c.yaw);
    assert.equal(Number(solved.position[2].toFixed(6)), c.expected_z,
      `${c.asset} grounded to the wrong height`);
  }
});
