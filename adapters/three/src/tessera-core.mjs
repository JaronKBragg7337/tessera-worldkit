// Tessera core: transforms, occupancy and validation, with no renderer dependency.
// SPDX-License-Identifier: 0BSD
//
// This is a deliberate port of the Python rules, not a reimplementation. Both
// read the same catalog and must reach the same verdict on the same layout;
// `test/parity.test.mjs` asserts exactly that against the Python output. A
// second implementation that disagrees with the first is worse than no second
// implementation, so the parity test is the point of this file existing.

export const CANONICAL_SPACE = 'tessera.space/1';
export const CONTACT_EPSILON = 5e-4;
export const CLASH_VOLUME_EPSILON = 1e-6;
export const SUPPORT_COVERAGE = 0.02;

const DEG = Math.PI / 180;

export function rotationMatrix([yaw, pitch, roll]) {
  const cz = Math.cos(yaw * DEG), sz = Math.sin(yaw * DEG);
  const cy = Math.cos(pitch * DEG), sy = Math.sin(pitch * DEG);
  const cx = Math.cos(roll * DEG), sx = Math.sin(roll * DEG);
  return [
    [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
    [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
    [-sy, cy * sx, cy * cx],
  ];
}

const Q = 1e-6;
const q = (v) => Math.round(v / Q) * Q;

export class Transform {
  constructor(position = [0, 0, 0], rotation = [0, 0, 0], scale = 1) {
    this.position = position;
    this.rotation = rotation;
    this.scale = scale;
    this.m = rotationMatrix(rotation);
  }
  static from(spec) {
    return new Transform(spec.position, spec.rotation_degrees ?? [0, 0, 0],
                         spec.scale ?? 1);
  }
  point(p) {
    const s = this.scale, m = this.m;
    const [x, y, z] = [p[0] * s, p[1] * s, p[2] * s];
    return [
      q(m[0][0] * x + m[0][1] * y + m[0][2] * z + this.position[0]),
      q(m[1][0] * x + m[1][1] * y + m[1][2] * z + this.position[1]),
      q(m[2][0] * x + m[2][1] * y + m[2][2] * z + this.position[2]),
    ];
  }
  direction(d) {
    const m = this.m;
    const out = [
      m[0][0] * d[0] + m[0][1] * d[1] + m[0][2] * d[2],
      m[1][0] * d[0] + m[1][1] * d[1] + m[1][2] * d[2],
      m[2][0] * d[0] + m[2][1] * d[1] + m[2][2] * d[2],
    ];
    const n = Math.hypot(...out) || 1;
    return out.map((c) => Number((c / n).toFixed(9)));
  }
  box(b) {
    const pts = [];
    for (let i = 0; i < 8; i += 1) {
      pts.push(this.point([
        (i & 1) ? b[0] : b[3],
        (i & 2) ? b[1] : b[4],
        (i & 4) ? b[2] : b[5],
      ]));
    }
    return [
      Math.min(...pts.map((p) => p[0])), Math.min(...pts.map((p) => p[1])),
      Math.min(...pts.map((p) => p[2])), Math.max(...pts.map((p) => p[0])),
      Math.max(...pts.map((p) => p[1])), Math.max(...pts.map((p) => p[2])),
    ];
  }
}

export const boxesOverlap = (a, b, gap = 0) => {
  for (let i = 0; i < 3; i += 1) {
    if (a[i] >= b[i + 3] - gap || b[i] >= a[i + 3] - gap) return false;
  }
  return true;
};

export const overlapVolume = (a, b) => {
  let v = 1;
  for (let i = 0; i < 3; i += 1) {
    const d = Math.min(a[i + 3], b[i + 3]) - Math.max(a[i], b[i]);
    if (d <= 0) return 0;
    v *= d;
  }
  return v;
};

const xyOverlapArea = (a, b) => Math.max(0, Math.min(a[3], b[3]) - Math.max(a[0], b[0]))
  * Math.max(0, Math.min(a[4], b[4]) - Math.max(a[1], b[1]));

export function compatible(table, a, b) {
  return (table[a] ?? []).includes(b);
}

export function indexCatalog(catalog) {
  const index = new Map();
  for (const asset of catalog.assets) index.set(asset.id, asset);
  return index;
}

export function resolveInstances(layout, catalog) {
  const index = indexCatalog(catalog);
  return layout.instances.map((spec) => {
    const record = index.get(spec.asset);
    if (!record) return { id: spec.id, asset: spec.asset, missing: true };
    const t = Transform.from(spec);
    return {
      id: spec.id,
      asset: spec.asset,
      record,
      transform: t,
      occupancy: record.occupancy.boxes.map((b) => t.box(b)),
      clearance: record.clearance.boxes.map((b) => t.box(b)),
      apertures: (record.apertures ?? []).map((ap) => ({
        ...ap,
        world: t.box([...ap.bounds.min, ...ap.bounds.max]),
      })),
      connectors: Object.fromEntries((record.connectors ?? []).map((c) => [c.id, {
        ...c,
        position: t.point(c.position),
        normal: t.direction(c.normal),
        tangent: t.direction(c.tangent),
      }])),
      connections: spec.connections ?? [],
    };
  });
}

/**
 * The subset of layout rules that a runtime consumer actually needs: is
 * anything floating, buried, unsupported, intersecting or blocking a doorway.
 * Grid, rotation and scale policy are build-time concerns and stay in Python.
 */
export function validateLayout(layout, catalog) {
  const diagnostics = [];
  const checksRun = ['layout.asset_known', 'layout.intersection',
                     'layout.support', 'layout.grounded', 'layout.aperture_clear'];
  const instances = resolveInstances(layout, catalog);

  for (const inst of instances) {
    if (inst.missing) {
      diagnostics.push({
        code: 'TSR_LAYOUT_UNKNOWN_ASSET', severity: 'error',
        what: 'Instance references an asset that is not in the catalog.',
        where: { instance: inst.id, asset: inst.asset },
        why: 'Nothing else about this instance can be checked.',
        expected: 'an id present in catalog.assets', actual: inst.asset,
        fix: 'load the catalog the layout was authored against',
        rule: 'layout.asset_known',
      });
    }
  }

  const live = instances.filter((i) => !i.missing);
  const bounds = (i) => [
    Math.min(...i.occupancy.map((b) => b[0])), Math.min(...i.occupancy.map((b) => b[1])),
    Math.min(...i.occupancy.map((b) => b[2])), Math.max(...i.occupancy.map((b) => b[3])),
    Math.max(...i.occupancy.map((b) => b[4])), Math.max(...i.occupancy.map((b) => b[5])),
  ];

  const buriedPairs = new Set();

  // support / grounding
  for (const inst of live) {
    const support = inst.record.placement.support ?? {};
    if (!support.requires_support || support.may_float) continue;

    let datumZ; let footprint;
    const datumId = support.datum_connector;
    if (datumId && inst.connectors[datumId]) {
      const c = inst.connectors[datumId];
      datumZ = c.position[2];
      const eh = c.extent_half ?? [0.05, 0.05];
      const yaw = ((inst.transform.rotation[0] % 180) + 180) % 180;
      const [ex, ey] = (yaw < 1e-6) ? [eh[0], eh[1]] : [eh[1], eh[0]];
      footprint = [[c.position[0] - ex, c.position[1] - ey, 0,
                    c.position[0] + ex, c.position[1] + ey, 0]];
    } else {
      datumZ = Math.min(...inst.occupancy.map((b) => b[2]));
      footprint = inst.occupancy.filter((b) => Math.abs(b[2] - datumZ) <= CONTACT_EPSILON)
        .map((b) => [b[0], b[1], 0, b[3], b[4], 0]);
    }
    const area = footprint.reduce((s, f) => s + (f[3] - f[0]) * (f[4] - f[1]), 0) || 1e-9;

    const candidates = [];
    if ((support.rests_on ?? []).includes('terrain')) candidates.push(['terrain', 0]);
    for (const other of live) {
      if (other === inst) continue;
      for (const ob of other.occupancy) {
        if (ob[2] > datumZ + CONTACT_EPSILON) continue;
        const a = footprint.reduce((s, f) => s + xyOverlapArea(f, ob), 0);
        if (a / area >= SUPPORT_COVERAGE) candidates.push([other.id, ob[5]]);
      }
    }
    const where = { instance: inst.id, asset: inst.asset,
                    position: inst.transform.position };
    if (!candidates.length) {
      diagnostics.push({
        code: 'TSR_LAYOUT_UNSUPPORTED', severity: 'error',
        what: 'Nothing is underneath this instance.', where,
        why: 'This asset declares that it requires support.',
        expected: `a surface of kind ${support.rests_on ?? 'any'} beneath it`,
        actual: 'no overlapping geometry below',
        fix: 'place a supporting asset beneath it', rule: 'layout.support',
      });
      continue;
    }
    const above = candidates.filter((c) => c[1] > datumZ + CONTACT_EPSILON);
    if (above.length) {
      const worst = above.reduce((a, b) => (b[1] > a[1] ? b : a));
      const delta = q(worst[1] - datumZ);
      buriedPairs.add([inst.id, worst[0]].sort().join('|'));
      diagnostics.push({
        code: 'TSR_LAYOUT_BURIED', severity: 'error',
        what: 'Instance is sunk into the surface it should rest on.',
        where: { ...where, support: worst[0] },
        why: `Its datum lies ${delta.toFixed(4)} m below the top of ${worst[0]}.`,
        expected: worst[1], actual: datumZ,
        fix: `raise by ${delta.toFixed(4)} m`,
        fix_transform: { translate: [0, 0, delta] }, rule: 'layout.grounded',
      });
      continue;
    }
    const best = candidates.reduce((a, b) => (b[1] > a[1] ? b : a));
    const gap = q(datumZ - best[1]);
    if (gap > CONTACT_EPSILON) {
      diagnostics.push({
        code: 'TSR_LAYOUT_FLOATING', severity: 'error',
        what: 'Instance floats above its support.',
        where: { ...where, support: best[0] },
        why: `A ${gap.toFixed(4)} m gap between the asset and the surface beneath it.`,
        expected: best[1], actual: datumZ,
        fix: `lower by ${gap.toFixed(4)} m`,
        fix_transform: { translate: [0, 0, -gap] }, rule: 'layout.grounded',
      });
    }
  }

  // intersections
  for (let i = 0; i < live.length; i += 1) {
    for (let j = i + 1; j < live.length; j += 1) {
      const a = live[i]; const b = live[j];
      if (!boxesOverlap(bounds(a), bounds(b), CONTACT_EPSILON)) continue;
      if (buriedPairs.has([a.id, b.id].sort().join('|'))) continue;
      let shared = 0;
      for (const ba of a.occupancy) for (const bb of b.occupancy) shared += overlapVolume(ba, bb);
      if (shared > CLASH_VOLUME_EPSILON) {
        diagnostics.push({
          code: 'TSR_LAYOUT_INTERSECTION', severity: 'error',
          what: 'Two instances occupy the same space.',
          where: { instance: a.id, asset: a.asset, other_instance: b.id },
          why: 'Overlapping solids z-fight and break physics.',
          expected: 0, actual: Number(shared.toFixed(6)),
          fix: 'move one instance by one grid step', rule: 'layout.intersection',
        });
      }
    }
  }

  // apertures
  for (const inst of live) {
    const exempt = new Set(inst.connections.map((l) => l.to.instance));
    for (const other of live) {
      for (const l of other.connections) if (l.to.instance === inst.id) exempt.add(other.id);
    }
    for (const ap of inst.apertures) {
      if (!ap.traversable) continue;
      for (const other of live) {
        if (other === inst || exempt.has(other.id)) continue;
        let blocked = 0;
        for (const ob of other.occupancy) blocked += overlapVolume(ob, ap.world);
        if (blocked > CLASH_VOLUME_EPSILON) {
          diagnostics.push({
            code: 'TSR_LAYOUT_APERTURE_BLOCKED', severity: 'error',
            what: 'A traversable opening is blocked by another asset.',
            where: { instance: inst.id, aperture: ap.id, other_instance: other.id },
            why: 'The route through the doorway is obstructed.',
            expected: 'the aperture clear of all geometry',
            actual: Number(blocked.toFixed(6)),
            fix: `move ${other.id} out of the opening`, rule: 'layout.aperture_clear',
          });
        }
      }
    }
  }

  const errors = diagnostics.filter((d) => d.severity === 'error');
  return {
    schema: 'tessera.report/1',
    validator_version: '1.0.0-js',
    subject: layout.name ?? 'layout',
    subject_kind: 'layout',
    status: errors.length ? 'failed' : 'passed',
    counts: { errors: errors.length, warnings: 0, info: diagnostics.length - errors.length },
    coverage: { checks_run: checksRun, checks_run_count: checksRun.length,
                rules_failed: [...new Set(errors.map((d) => d.rule))].sort() },
    diagnostics,
  };
}

/** Solve the world transform that grounds an asset on a supporting surface. */
export function solveGround(record, hostSurfaceZ, x, y, yaw = 0) {
  const support = record.placement.support ?? {};
  let datum = record.dimensions.bounds.min[2];
  if (support.datum_connector) {
    const c = record.connectors.find((k) => k.id === support.datum_connector);
    if (c) datum = c.position[2];
  }
  return { position: [x, y, q(hostSurfaceZ - datum)], rotation_degrees: [yaw, 0, 0], scale: 1 };
}
