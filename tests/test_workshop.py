"""The public Workshop must be generated from the repository contract.

SPDX-License-Identifier: 0BSD
"""
import json
from pathlib import Path
import re
import zipfile

from tools.build_workshop import build


def test_workshop_build_is_self_contained(root, tmp_path):
    out = tmp_path / "dist"
    result = build(out)
    assert result["assets"] >= 22
    for required in (
        "index.html", "styles.css", "app.mjs", "sw.js",
        "lib/tessera-core.mjs", "data/catalog.json", "data/brief.json",
        "data/workshop.json", "downloads/tessera-chat.zip",
        "downloads/tessera-sandbox.zip",
    ):
        assert (out / required).is_file(), required

    site = json.loads((out / "data" / "workshop.json").read_text())
    catalog = json.loads((out / "data" / "catalog.json").read_text())
    brief = json.loads((out / "data" / "brief.json").read_text())
    assert site["catalog"]["fingerprint"] == catalog["fingerprint"] \
        == brief["fingerprint"]
    assert site["privacy"] == {
        "login": False, "telemetry": False, "uploads_leave_device": False,
    }
    assert len(site["examples"]) == 4

    with zipfile.ZipFile(out / "downloads" / "tessera-sandbox.zip") as archive:
        assert "src/tessera/validate/layout.py" in archive.namelist()


def test_workshop_entrypoint_has_no_broken_relative_file_links(tmp_path):
    out = tmp_path / "dist"
    build(out)
    html = (out / "index.html").read_text(encoding="utf-8")
    local = re.findall(r'(?:href|src)="\./([^"#?]+)"', html)
    for relative in local:
        if relative.endswith("/"):
            relative += "index.html"
        assert (out / relative).exists(), relative
