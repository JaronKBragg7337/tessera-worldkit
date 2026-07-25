"""Portable handoff packs for chat, browser, sandbox and desktop agents.

SPDX-License-Identifier: 0BSD

The pack is a capability adapter.  It does not assume that a phone chat has a
terminal, and it does not remove anything from a desktop agent that does.
Every target receives the same fingerprinted contract in the richest form it
can execute.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import zipfile

from .brief import build_brief, render_text


TARGETS = {
    "chat": {
        "can_execute": False,
        "can_validate": False,
        "delivery": "one compact Markdown capsule plus machine-readable JSON",
    },
    "browser": {
        "can_execute": True,
        "can_validate": "runtime subset in the public Workshop",
        "delivery": "fingerprinted capsule for the browser Workshop",
    },
    "sandbox": {
        "can_execute": True,
        "can_validate": "full 41-rule Python validator",
        "delivery": "self-contained, zero-runtime-dependency ZIP",
    },
    "desktop": {
        "can_execute": True,
        "can_validate": "full validator plus engine adapters",
        "delivery": "source, generated assets and adapters",
    },
}

_SOURCE_ROOTS = ("src/tessera", "kits/shell_v1", "schema")
_DESKTOP_ROOTS = ("adapters", "examples")
_COMMON_FILES = ("tessera", "LICENSE", "LICENSE-CODE", "LICENSE-ASSETS",
                 "AGENTS.md", "docs/remote-agents.md")


def build_manifest(catalog, target, brief, prompt="", layout=None):
    if target not in TARGETS:
        raise ValueError("unknown target %r" % target)
    return {
        "schema": "tessera.handoff/1",
        "target": target,
        "prompt": prompt,
        "catalog": {
            "kit": brief["kit"],
            "fingerprint": brief["fingerprint"],
            "contract_version": brief["contract_version"],
        },
        "asset_count": brief["asset_count"],
        "assets": [asset["id"] for asset in brief["assets"]],
        "environment": TARGETS[target],
        "contains_layout": layout is not None,
        "rules": [
            "Do not guess dimensions; read the included brief.",
            "Record the catalog fingerprint in every layout.",
            "Do not claim validation unless a validator actually returned passed.",
            "Apply fix_transform as data, then re-run validation.",
            "If the requested world is not expressible, say what is missing.",
        ],
    }


def render_start_here(manifest, brief_text):
    prompt = manifest["prompt"].strip() or \
        "Build or continue the requested world using only the included contract."
    env = manifest["environment"]
    lines = [
        "# Tessera AI handoff",
        "",
        "You have been given deterministic hands for the mechanical parts of "
        "world-building. Use your own judgment for the game and its intent; "
        "use Tessera for dimensions, placement, connection and checking.",
        "",
        "## Task",
        "",
        prompt,
        "",
        "## Environment",
        "",
        "- Target: `%s`" % manifest["target"],
        "- Delivery: %s" % env["delivery"],
        "- Can execute: %s" % str(env["can_execute"]).lower(),
        "- Validation available: %s" % env["can_validate"],
        "",
        "## Non-negotiable rules",
        "",
    ]
    lines.extend("- " + rule for rule in manifest["rules"])
    if manifest["target"] in ("sandbox", "desktop"):
        lines += [
            "",
            "## Run",
            "",
            "```bash",
            "python3 tessera doctor --json",
            "python3 tessera validate --layout layout.json --json",
            "python3 tessera repair --layout layout.json --out repaired-layout.json --json",
            "```",
            "",
            "The core uses Python 3.10+ and has zero runtime dependencies.",
        ]
    else:
        lines += [
            "",
            "Return a `tessera.layout/1` JSON document. If you cannot execute "
            "the validator in this environment, say `validation not run`; do "
            "not replace execution with confidence.",
        ]
    lines += ["", "## Placement brief", "", "```text", brief_text, "```", ""]
    return "\n".join(lines)


def _zip_write_bytes(archive, name, data):
    info = zipfile.ZipInfo(name.replace("\\", "/"), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, data)


def _iter_files(root, relative):
    path = root / relative
    if path.is_file():
        yield path, Path(relative)
        return
    if path.is_dir():
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            if "__pycache__" in child.parts:
                continue
            yield child, child.relative_to(root)


def write_handoff_pack(*, catalog, target, out_path, repo_root=".", prompt="",
                       selectors=None, layout=None):
    """Write a deterministic ZIP and return its public manifest summary."""
    root = Path(repo_root).resolve()
    brief = build_brief(catalog, selectors=selectors)
    brief_text = render_text(brief)
    manifest = build_manifest(catalog, target, brief, prompt, layout)
    start_here = render_start_here(manifest, brief_text)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if target in ("sandbox", "desktop"):
        missing = [
            relative for relative in ("tessera", "src/tessera", "kits/shell_v1")
            if not (root / relative).exists()
        ]
        if missing:
            raise ValueError(
                "repository root %s is missing %s"
                % (root, ", ".join(missing)))
    with zipfile.ZipFile(out, "w") as archive:
        _zip_write_bytes(archive, "AI_START_HERE.md", start_here.encode("utf-8"))
        _zip_write_bytes(
            archive, "handoff.json",
            json.dumps(manifest, indent=2).encode("utf-8"))
        _zip_write_bytes(
            archive, "brief.json",
            json.dumps(brief, separators=(",", ":")).encode("utf-8"))
        _zip_write_bytes(archive, "brief.txt", brief_text.encode("utf-8"))
        if layout is not None:
            _zip_write_bytes(
                archive, "layout.json",
                json.dumps(layout, indent=2).encode("utf-8"))

        if target in ("sandbox", "desktop"):
            for relative in _COMMON_FILES:
                for path, name in _iter_files(root, relative):
                    _zip_write_bytes(archive, str(name), path.read_bytes())
            for relative in _SOURCE_ROOTS:
                for path, name in _iter_files(root, relative):
                    _zip_write_bytes(archive, str(name), path.read_bytes())
            _zip_write_bytes(
                archive, "build/catalog.json",
                json.dumps(catalog, indent=2).encode("utf-8"))

            selected = set(manifest["assets"])
            for asset in catalog["assets"]:
                short = asset["id"].split("/")[-1]
                if short not in selected:
                    continue
                for field in ("glb", "obj", "mtl"):
                    rel = asset.get("files", {}).get(field) \
                        or "meshes/%s.%s" % (short, field)
                    if not rel:
                        continue
                    source = root / "build" / rel
                    if source.is_file():
                        _zip_write_bytes(
                            archive, "build/" + rel.replace("\\", "/"),
                            source.read_bytes())

        if target == "desktop":
            for relative in _DESKTOP_ROOTS:
                for path, name in _iter_files(root, relative):
                    _zip_write_bytes(archive, str(name), path.read_bytes())

    return {
        "target": target,
        "out": os.fspath(out),
        "asset_count": brief["asset_count"],
        "fingerprint": brief["fingerprint"],
        "bytes": out.stat().st_size,
    }
