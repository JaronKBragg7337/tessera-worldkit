"""Portable packs must match the capabilities they advertise.

SPDX-License-Identifier: 0BSD
"""
import json
from pathlib import Path
import zipfile

import pytest

from tessera.brief import build_brief
from tessera.handoff import build_manifest, write_handoff_pack


def test_brief_can_select_roles_and_ids(catalog):
    walls = build_brief(catalog, selectors=["role:wall"])
    assert walls["asset_count"] >= 2
    assert {asset["role"] for asset in walls["assets"]} == {"wall"}

    openings = build_brief(catalog, selectors=["id:*.doorway.*"])
    assert openings["assets"]
    assert all("doorway" in asset["id"] for asset in openings["assets"])

    mixed = build_brief(catalog, selectors=["wall,roof.*"])
    assert {asset["role"] for asset in mixed["assets"]} >= {"wall", "roof"}


def test_empty_selector_is_refused(catalog):
    with pytest.raises(ValueError, match="no assets match"):
        build_brief(catalog, selectors=["id:not-a-real-piece"])


def test_manifest_says_what_the_environment_can_do(catalog):
    brief = build_brief(catalog, selectors=["role:wall"])
    chat = build_manifest(catalog, "chat", brief, "Build a room")
    sandbox = build_manifest(catalog, "sandbox", brief, "Build a room")
    assert chat["environment"]["can_execute"] is False
    assert chat["environment"]["can_validate"] is False
    assert sandbox["environment"]["can_validate"].startswith("full")
    assert chat["catalog"]["fingerprint"] == catalog["fingerprint"]


def test_chat_pack_is_small_and_sandbox_pack_has_hands(
        catalog, layout, root, tmp_path):
    chat_path = tmp_path / "chat.zip"
    sandbox_path = tmp_path / "sandbox.zip"
    write_handoff_pack(
        catalog=catalog, target="chat", out_path=chat_path, repo_root=root,
        prompt="Build a room", selectors=["wall"])
    write_handoff_pack(
        catalog=catalog, target="sandbox", out_path=sandbox_path, repo_root=root,
        prompt="Validate this", selectors=["wall"], layout=layout)

    with zipfile.ZipFile(chat_path) as archive:
        names = set(archive.namelist())
        assert {"AI_START_HERE.md", "handoff.json", "brief.json", "brief.txt"} <= names
        assert not any(name.startswith("src/") for name in names)
        start = archive.read("AI_START_HERE.md").decode()
        assert "validation not run" in start

    with zipfile.ZipFile(sandbox_path) as archive:
        names = set(archive.namelist())
        assert "src/tessera/validate/layout.py" in names
        assert "build/catalog.json" in names
        assert "layout.json" in names
        assert any(name.endswith("wall.straight.4m.glb") for name in names)
        manifest = json.loads(archive.read("handoff.json"))
        assert manifest["contains_layout"]


def test_pack_is_byte_deterministic(catalog, root, tmp_path):
    one = tmp_path / "one.zip"
    two = tmp_path / "two.zip"
    kwargs = dict(
        catalog=catalog, target="sandbox", repo_root=root,
        prompt="Build a room", selectors=["role:wall"])
    write_handoff_pack(out_path=one, **kwargs)
    write_handoff_pack(out_path=two, **kwargs)
    assert one.read_bytes() == two.read_bytes()


def test_executable_pack_refuses_a_non_repository_root(catalog, tmp_path):
    with pytest.raises(ValueError, match="repository root"):
        write_handoff_pack(
            catalog=catalog, target="sandbox", out_path=tmp_path / "bad.zip",
            repo_root=tmp_path, prompt="test")


def test_handoff_manifest_matches_its_schema(catalog, root):
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((Path(root) / "schema" / "handoff.schema.json").read_text())
    brief = build_brief(catalog)
    manifest = build_manifest(catalog, "browser", brief)
    jsonschema.Draft202012Validator(schema).validate(manifest)
