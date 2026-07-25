// Tessera Workshop. SPDX-License-Identifier: 0BSD
import { resolveInstances, validateLayout } from './lib/tessera-core.mjs';

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const clone = (value) => JSON.parse(JSON.stringify(value));

const targetProfiles = {
  chat: {
    title: 'Chat capsule',
    summary: 'Assumes attachments and text only. It asks for a layout and requires the AI to say when validation did not run.',
    validate: 'none in the chat itself',
  },
  browser: {
    title: 'Browser handoff',
    summary: 'Carries the contract into a browser-operable tool with preview, a runtime check, downloads, and no login.',
    validate: 'runtime-safe browser subset',
  },
  sandbox: {
    title: 'Sandbox kit',
    summary: 'Adds the zero-dependency Python CLI, the full validator, selected generated assets, and exact repair.',
    validate: 'full Python validator',
  },
  desktop: {
    title: 'Desktop handoff',
    summary: 'Keeps the full repository, generated assets, tests, and engine adapters. Nothing is compressed away.',
    validate: 'full validator plus adapter checks',
  },
};

const state = {
  manifest: null,
  catalog: null,
  brief: null,
  target: 'chat',
  selectedRoles: new Set(),
  capsule: '',
  handoff: null,
  layout: null,
  report: null,
};

async function boot() {
  try {
    const [manifest, catalog, brief] = await Promise.all([
      fetch('./data/workshop.json').then(assertFetch).then((r) => r.json()),
      fetch('./data/catalog.json').then(assertFetch).then((r) => r.json()),
      fetch('./data/brief.json').then(assertFetch).then((r) => r.json()),
    ]);
    Object.assign(state, { manifest, catalog, brief });
    const roles = [...new Set(brief.assets.map((asset) => asset.role))].sort();
    roles.forEach((role) => state.selectedRoles.add(role));
    renderFacts();
    renderRoles(roles);
    renderTarget();
    renderExamples();
    await loadExample(manifest.examples[0].file);
    $('#coverageNote').textContent =
      `This browser checks ${manifest.browser_validation.checks} runtime rules. ` +
      `The downloadable sandbox runs the complete ${manifest.full_validation.checks}-rule validator.`;
    $('#buildCapsule').click();
  } catch (error) {
    showFatal(error);
  }
}

function assertFetch(response) {
  if (!response.ok) throw new Error(`Could not load ${response.url}: ${response.status}`);
  return response;
}

function renderFacts() {
  $('#assetCount').textContent = state.catalog.asset_count;
  $('#fingerprint').textContent = state.catalog.fingerprint.slice(0, 12);
}

function renderRoles(roles) {
  const root = $('#roles');
  root.replaceChildren(...roles.map((role) => {
    const count = state.brief.assets.filter((asset) => asset.role === role).length;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'role-chip';
    button.dataset.role = role;
    button.setAttribute('aria-pressed', 'true');
    button.textContent = `${role} · ${count}`;
    button.addEventListener('click', () => {
      state.selectedRoles.has(role)
        ? state.selectedRoles.delete(role)
        : state.selectedRoles.add(role);
      button.setAttribute('aria-pressed', String(state.selectedRoles.has(role)));
      refreshHandoff();
    });
    return button;
  }));
}

function renderTarget() {
  $$('.target').forEach((button) => {
    button.classList.toggle('active', button.dataset.target === state.target);
  });
  const profile = targetProfiles[state.target];
  $('#outputTitle').textContent = profile.title;
  $('#capabilityReadout').innerHTML =
    `<strong>${profile.title}.</strong> ${profile.summary} ` +
    `<span>Validation: ${profile.validate}.</span>`;
  updateEstimate();
}

function selectedBrief() {
  const brief = clone(state.brief);
  brief.assets = brief.assets.filter((asset) => state.selectedRoles.has(asset.role));
  brief.asset_count = brief.assets.length;
  brief.selection = {
    roles: [...state.selectedRoles].sort(),
    source_asset_count: state.brief.asset_count,
  };
  return brief;
}

function buildHandoff() {
  const brief = selectedBrief();
  if (!brief.assets.length) {
    state.handoff = null;
    state.capsule = '';
    $('#scopeStatus').textContent = 'select pieces';
    $('#scopeStatus').className = 'status-pill bad';
    $('#capsuleOutput').textContent = 'Choose at least one asset role.';
    $('#copyCapsule').disabled = true;
    $('#downloadCapsule').disabled = true;
    $('#downloadJson').disabled = true;
    updateEstimate();
    return;
  }
  const prompt = $('#taskPrompt').value.trim();
  const profile = targetProfiles[state.target];
  const handoff = {
    schema: 'tessera.handoff/1',
    target: state.target,
    prompt,
    catalog: {
      kit: brief.kit,
      fingerprint: brief.fingerprint,
      contract_version: brief.contract_version,
    },
    environment: {
      can_execute: state.target !== 'chat',
      validation: profile.validate,
    },
    brief,
    rules: [
      'Do not guess dimensions; read the included brief.',
      'Record the catalog fingerprint in every layout.',
      'Do not claim validation unless a validator actually returned passed.',
      'Apply fix_transform as data and re-run validation.',
      'If the requested world is not expressible, identify what is missing.',
    ],
  };
  state.handoff = handoff;
  state.capsule = renderCapsule(handoff);
  $('#capsuleOutput').textContent = state.capsule;
  $('#scopeStatus').textContent = `${brief.asset_count} pieces`;
  $('#scopeStatus').className = 'status-pill ok';
  $('#copyCapsule').disabled = false;
  $('#downloadCapsule').disabled = false;
  $('#downloadJson').disabled = false;
  updateEstimate();
}

function renderCapsule(handoff) {
  const runnable = handoff.target === 'chat'
    ? 'You cannot assume a terminal. Return tessera.layout/1 JSON and write "validation not run" unless a tool actually ran it.'
    : handoff.target === 'browser'
      ? 'Use the Tessera Workshop browser check. Label it as a runtime subset; use the sandbox for full validation.'
      : 'Run `python3 tessera validate --layout layout.json --json`. Apply exact fixes with `python3 tessera repair --layout layout.json --out repaired-layout.json --json`.';
  return [
    '# Tessera AI handoff',
    '',
    'Use your judgment for game intent. Use Tessera for measurable placement, connection, collision and checking.',
    '',
    '## Task',
    '',
    handoff.prompt || 'Build or continue the requested world.',
    '',
    '## Environment instruction',
    '',
    runnable,
    '',
    '## Rules',
    '',
    ...handoff.rules.map((rule) => `- ${rule}`),
    '',
    '## Fingerprinted placement brief',
    '',
    '```json',
    JSON.stringify(handoff.brief),
    '```',
    '',
  ].join('\n');
}

function updateEstimate() {
  if (!state.brief) return;
  const draft = state.capsule || renderCapsule({
    target: state.target,
    prompt: $('#taskPrompt').value.trim(),
    rules: [],
    brief: selectedBrief(),
  });
  const tokens = Math.round(draft.length / 3.6);
  $('#capsuleCost').textContent =
    `${state.selectedRoles.size} roles · ~${tokens.toLocaleString()} tokens`;
}

function refreshHandoff() {
  if (state.handoff) buildHandoff();
  else updateEstimate();
}

function renderExamples() {
  const select = $('#exampleSelect');
  select.replaceChildren(...state.manifest.examples.map((example) => {
    const option = document.createElement('option');
    option.value = example.file;
    option.textContent = `${example.name} · ${example.instances} instances`;
    return option;
  }));
}

async function loadExample(file) {
  const layout = await fetch(`./data/examples/${file}`).then(assertFetch).then((r) => r.json());
  setLayout(layout);
  runBrowserValidation();
}

function setLayout(layout) {
  state.layout = layout;
  $('#layoutInput').value = JSON.stringify(layout, null, 2);
  $('#layoutName').textContent = layout.name || 'Untitled layout';
  $('#downloadLayout').disabled = false;
  drawPlan(layout);
}

function parseLayout() {
  const layout = JSON.parse($('#layoutInput').value);
  setLayout(layout);
  return layout;
}

function runBrowserValidation() {
  try {
    const layout = parseLayout();
    const report = validateLayout(layout, state.catalog);
    state.report = report;
    renderReport(report);
    $('#downloadReport').disabled = false;
    return report;
  } catch (error) {
    state.report = null;
    $('#validationStatus').textContent = 'invalid JSON';
    $('#validationStatus').className = 'status-pill bad';
    $('#reportSummary').textContent = '';
    $('#diagnostics').replaceChildren(diagnosticItem({
      code: 'WORKSHOP_PARSE_ERROR',
      what: error.message,
      fix: 'Correct the JSON and run the check again.',
    }));
    return null;
  }
}

function renderReport(report) {
  const ok = report.status === 'passed';
  $('#validationStatus').textContent = ok ? 'runtime check passed' : 'needs work';
  $('#validationStatus').className = `status-pill ${ok ? 'ok' : 'bad'}`;
  $('#reportSummary').innerHTML = [
    ['errors', report.counts.errors],
    ['warnings', report.counts.warnings],
    ['checks run', report.coverage.checks_run_count],
  ].map(([label, value]) => `<div><strong>${value}</strong><span>${label}</span></div>`).join('');
  const list = $('#diagnostics');
  const visible = report.diagnostics.length
    ? report.diagnostics.slice(0, 30)
    : [{ code: 'TSR_BROWSER_CLEAR', what: 'No runtime errors found in the browser subset.',
      fix: 'Run the full sandbox validator before claiming full validation.' }];
  list.replaceChildren(...visible.map(diagnosticItem));
}

function diagnosticItem(diagnostic) {
  const item = document.createElement('li');
  const code = document.createElement('code');
  code.textContent = diagnostic.code;
  const what = document.createElement('p');
  what.textContent = diagnostic.what || '';
  item.append(code, what);
  if (diagnostic.fix) {
    const fix = document.createElement('p');
    fix.textContent = `Fix: ${diagnostic.fix}`;
    item.append(fix);
  }
  return item;
}

function repairBrowserLayout() {
  let current;
  try {
    current = parseLayout();
  } catch {
    runBrowserValidation();
    return;
  }
  let applied = 0;
  for (let pass = 0; pass < 5; pass += 1) {
    const baseline = validateLayout(current, state.catalog);
    if (baseline.status === 'passed') break;
    const candidates = [];
    for (const diagnostic of baseline.diagnostics) {
      const target = diagnostic.where?.instance;
      const transform = diagnostic.fix_transform;
      if (!target || !transform) continue;
      const candidate = clone(current);
      const instance = candidate.instances.find((entry) => (entry.id || entry.name) === target);
      if (!instance || !applyTransform(instance, transform)) continue;
      const result = validateLayout(candidate, state.catalog);
      if (result.counts.errors < baseline.counts.errors) {
        candidates.push({ candidate, result, target, transform });
      }
    }
    candidates.sort((a, b) => a.result.counts.errors - b.result.counts.errors
      || a.target.localeCompare(b.target));
    if (!candidates.length) break;
    current = candidates[0].candidate;
    applied += 1;
  }
  setLayout(current);
  const report = runBrowserValidation();
  if (report) {
    $('#validationStatus').textContent += applied ? ` · ${applied} fix${applied === 1 ? '' : 'es'}` : ' · no safe fix';
  }
}

function applyTransform(instance, transform) {
  if (Array.isArray(transform.translate) && transform.translate.length === 3) {
    instance.position = (instance.position || [0, 0, 0])
      .map((value, index) => Number((value + transform.translate[index]).toFixed(9)));
    return true;
  }
  if (Array.isArray(transform.set_rotation)) {
    instance.rotation_degrees = [...transform.set_rotation];
    return true;
  }
  if (Number.isFinite(transform.rotate_z_by)) {
    const rotation = [...(instance.rotation_degrees || [0, 0, 0])];
    rotation[0] = (rotation[0] + transform.rotate_z_by) % 360;
    instance.rotation_degrees = rotation;
    return true;
  }
  if (Number.isFinite(transform.set_scale)) {
    instance.scale = transform.set_scale;
    return true;
  }
  return false;
}

function drawPlan(layout) {
  const canvas = $('#planCanvas');
  const rect = canvas.getBoundingClientRect();
  const ratio = Math.min(devicePixelRatio || 1, 2);
  canvas.width = Math.max(1, Math.floor(rect.width * ratio));
  canvas.height = Math.max(1, Math.floor(rect.height * ratio));
  const context = canvas.getContext('2d');
  context.scale(ratio, ratio);
  const width = rect.width;
  const height = rect.height;
  context.clearRect(0, 0, width, height);

  let instances;
  try {
    instances = resolveInstances(layout, state.catalog).filter((item) => !item.missing);
  } catch {
    return;
  }
  const boxes = instances.flatMap((instance) =>
    instance.occupancy.map((box) => ({ box, instance })));
  if (!boxes.length) return;
  const minX = Math.min(...boxes.map(({ box }) => box[0]));
  const minY = Math.min(...boxes.map(({ box }) => box[1]));
  const maxX = Math.max(...boxes.map(({ box }) => box[3]));
  const maxY = Math.max(...boxes.map(({ box }) => box[4]));
  const padding = 30;
  const scale = Math.min(
    (width - padding * 2) / Math.max(maxX - minX, 1),
    (height - padding * 2) / Math.max(maxY - minY, 1),
  );
  const offsetX = (width - (maxX - minX) * scale) / 2;
  const offsetY = (height - (maxY - minY) * scale) / 2;
  const palette = ['#9bc88b', '#7bc8c2', '#f0bd69', '#a79ad8', '#d78e78', '#829eaa'];
  const roles = [...new Set(instances.map((item) => item.record.semantic_role))].sort();
  const roleColor = new Map(roles.map((role, index) => [role, palette[index % palette.length]]));

  context.strokeStyle = 'rgba(155,200,139,.08)';
  context.lineWidth = 1;
  for (let gx = Math.floor(minX / 4) * 4; gx <= maxX; gx += 4) {
    const x = offsetX + (gx - minX) * scale;
    context.beginPath(); context.moveTo(x, 0); context.lineTo(x, height); context.stroke();
  }
  for (let gy = Math.floor(minY / 4) * 4; gy <= maxY; gy += 4) {
    const y = height - offsetY - (gy - minY) * scale;
    context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke();
  }

  boxes.sort((a, b) => a.box[2] - b.box[2]);
  for (const { box, instance } of boxes) {
    const x = offsetX + (box[0] - minX) * scale;
    const y = height - offsetY - (box[4] - minY) * scale;
    const w = Math.max(1, (box[3] - box[0]) * scale);
    const h = Math.max(1, (box[4] - box[1]) * scale);
    const color = roleColor.get(instance.record.semantic_role);
    context.globalAlpha = .16 + Math.min(.42, box[5] * .045);
    context.fillStyle = color;
    context.fillRect(x, y, w, h);
    context.globalAlpha = .62;
    context.strokeStyle = color;
    context.strokeRect(x, y, w, h);
  }
  context.globalAlpha = 1;
  context.fillStyle = '#9ea89c';
  context.font = '11px ui-monospace, monospace';
  context.fillText(`top view · ${(maxX - minX).toFixed(1)} × ${(maxY - minY).toFixed(1)} m`, 14, height - 14);
}

function download(name, content, type) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([content], { type }));
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

function showFatal(error) {
  $('#capsuleOutput').textContent = `Workshop could not start: ${error.message}`;
  $('#scopeStatus').textContent = 'load failed';
  $('#scopeStatus').className = 'status-pill bad';
}

$$('.target').forEach((button) => button.addEventListener('click', () => {
  state.target = button.dataset.target;
  renderTarget();
  refreshHandoff();
}));
$('#selectAll').addEventListener('click', () => {
  state.brief.assets.forEach((asset) => state.selectedRoles.add(asset.role));
  $$('.role-chip').forEach((button) => button.setAttribute('aria-pressed', 'true'));
  refreshHandoff();
});
$('#selectNone').addEventListener('click', () => {
  state.selectedRoles.clear();
  $$('.role-chip').forEach((button) => button.setAttribute('aria-pressed', 'false'));
  refreshHandoff();
});
$('#taskPrompt').addEventListener('input', refreshHandoff);
$('#buildCapsule').addEventListener('click', buildHandoff);
$('#copyCapsule').addEventListener('click', async () => {
  await navigator.clipboard.writeText(state.capsule);
  $('#copyCapsule').textContent = 'Copied';
  setTimeout(() => { $('#copyCapsule').textContent = 'Copy'; }, 1200);
});
$('#downloadCapsule').addEventListener('click', () =>
  download('tessera-ai-handoff.md', state.capsule, 'text/markdown'));
$('#downloadJson').addEventListener('click', () =>
  download('tessera-ai-handoff.json', JSON.stringify(state.handoff, null, 2), 'application/json'));
$('#exampleSelect').addEventListener('change', (event) => loadExample(event.target.value));
$('#layoutFile').addEventListener('change', async (event) => {
  const [file] = event.target.files;
  if (!file) return;
  $('#layoutInput').value = await file.text();
  runBrowserValidation();
});
$('#runValidation').addEventListener('click', runBrowserValidation);
$('#repairLayout').addEventListener('click', repairBrowserLayout);
$('#downloadLayout').addEventListener('click', () =>
  download('tessera-layout.json', JSON.stringify(state.layout, null, 2), 'application/json'));
$('#downloadReport').addEventListener('click', () =>
  download('tessera-browser-report.json', JSON.stringify(state.report, null, 2), 'application/json'));
addEventListener('resize', () => { if (state.layout) drawPlan(state.layout); });

if ('serviceWorker' in navigator) {
  addEventListener('load', () => navigator.serviceWorker.register('./sw.js').catch(() => {}));
}

boot();
