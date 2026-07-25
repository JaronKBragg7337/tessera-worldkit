"""The digest must be small enough to afford and complete enough to use.

SPDX-License-Identifier: 0BSD

A compressed catalog is only interesting if it is *sufficient*. The test that
matters here is not that the brief is small -- that is easy and uninteresting --
but that a solver fed nothing except the brief produces a layout that validates
against the full catalog it was derived from.
"""
import json

import pytest

from tessera.assemble import Builder
from tessera.brief import build_brief, expand, render_text
from tessera.validate import validate_layout


@pytest.fixture(scope="module")
def brief(catalog):
    return build_brief(catalog)


def test_brief_fits_a_constrained_context(brief, catalog):
    """The whole point: a phone assistant cannot spend 30k tokens on a kit."""
    full = len(json.dumps(catalog, separators=(",", ":")))
    compact = len(json.dumps(brief, separators=(",", ":")))
    text = len(render_text(brief))
    assert compact < full * 0.15, "brief is %.1f%% of the catalog" % (100 * compact / full)
    assert text < compact, "the text rendering should be cheaper than JSON"
    # roughly 3.6 characters per token
    assert compact / 3.6 < 4000, "brief must fit a small context budget"


def test_brief_keeps_everything_placement_needs(brief):
    for a in brief["assets"]:
        assert "size" in a and len(a["size"]) == 3
        assert "base" in a, "%s has no grounding offset" % a["id"]
        assert "grid" in a and "yaw" in a
        assert a["c"], "%s has no connectors" % a["id"]
        for c in a["c"]:
            assert len(c) == len(brief["legend"]["c"])
            assert c[2] in ("p", "s")
    assert brief["mates"], "the compatibility table must travel with the brief"
    assert brief["stack"]["floor_top"] > 0
    assert brief["fingerprint"]


def test_brief_drops_only_what_placement_does_not_need(brief):
    """The heavy blocks must be gone from the assets themselves.

    They are still *named*, once, in the legend's `omitted` field -- so a
    consumer knows what it does not have and where to get it -- which is why
    this scans the asset entries rather than the whole document.
    """
    assets = json.dumps(brief["assets"])
    for absent in ("occupancy", "collision", "provenance", "signed_volume",
                   "base_color", "sha256", "engine", "rationale", "license"):
        assert absent not in assets, "%s should not be in an asset entry" % absent
    assert "occupancy" in brief["legend"]["omitted"], \
        "the brief must say what it dropped"


def test_expansion_round_trips_the_placement_fields(brief, catalog):
    expanded = expand(brief)
    assert len(expanded["assets"]) == len(catalog["assets"])
    by_id = {a["id"]: a for a in catalog["assets"]}
    for a in expanded["assets"]:
        original = by_id[a["id"]]
        assert a["pivot"]["base_offset_z"] == pytest.approx(
            original["pivot"]["base_offset_z"], abs=1e-6)
        assert a["placement"]["allowed_rotations"] == \
            original["placement"]["allowed_rotations"]
        assert len(a["connectors"]) == len(original["connectors"])
        for c, o in zip(a["connectors"], original["connectors"]):
            assert c["id"] == o["id"] and c["kind"] == o["kind"]
            assert c["position"] == pytest.approx(o["position"], abs=1e-4)
            assert c["normal"] == pytest.approx(o["normal"], abs=1e-6)
            assert c["mating_mode"] == o.get("mating_mode", "point")


def test_a_scene_built_from_the_brief_alone_validates_against_the_full_catalog(
        brief, catalog):
    """The claim, made testable.

    The builder here never sees the real catalog. It sees only what a phone
    assistant could afford to hold. If the digest ever drops something placement
    depends on, this fails.
    """
    stub = expand(brief)
    b = Builder(stub, "built from the brief alone")
    A = brief["id_prefix"]
    BAY = brief["grid"]["module"]

    pads, floors = {}, {}
    for gx in range(3):
        for gy in range(3):
            pads[(gx, gy)] = b.ground(A + "foundation.pad.4m", gx * BAY, gy * BAY)
            floors[(gx, gy)] = b.ground(A + "floor.slab.4m", gx * BAY, gy * BAY,
                                        on=pads[(gx, gy)])
    span = BAY * 3
    corners = {
        "sw": b.ground(A + "wall.corner.4m", 0, 0, yaw=0, on=floors[(0, 0)]),
        "se": b.ground(A + "wall.corner.4m", span, 0, yaw=90, on=floors[(2, 0)]),
        "ne": b.ground(A + "wall.corner.4m", span, span, yaw=180, on=floors[(2, 2)]),
        "nw": b.ground(A + "wall.corner.4m", 0, span, yaw=270, on=floors[(0, 2)]),
    }
    doorway = b.ground(A + "wall.doorway.4m", BAY, 0, yaw=0, on=floors[(1, 0)])
    window = b.ground(A + "wall.window.4m", 2 * BAY, span, yaw=180, on=floors[(1, 2)])
    b.ground(A + "wall.straight.4m", 0.2, BAY, yaw=90, on=floors[(0, 1)])
    b.ground(A + "wall.straight.4m", span - 0.2, 2 * BAY, yaw=270, on=floors[(2, 1)])
    b.mate(A + "door.leaf.1m2", "hinge", doorway, "jamb_neg_y")
    b.mate(A + "window.leaf.1m8", "mount", window, "jamb_neg_y")

    south = [b.ground(A + "roof.panel.4m", i * BAY, 0, yaw=0,
                      on=corners["sw"] if i == 0 else doorway,
                      surface="top_x" if i == 0 else "top") for i in range(3)]
    for i in range(3):
        b.ground(A + "roof.panel.4m", (i + 1) * BAY, span, yaw=180,
                 on=window if i == 1 else corners["ne"],
                 surface="top" if i == 1 else "top_x")
    for panel in south:
        b.mate(A + "roof.ridge.4m", "seat", panel, "ridge_cap")
    b.autoconnect()

    layout = b.to_layout("assembled from a 2.4k-token digest")
    assert layout["instance_count"] == 37
    assert layout["placement_method"]["explicit"] == 0

    # validated against the FULL catalog, not the stub it was built from
    layout["catalog"]["fingerprint"] = catalog["fingerprint"]
    result = validate_layout(layout, catalog)
    assert result.ok, "\n".join(d.human() for d in result.errors)


def test_a_stale_catalog_is_refused_rather_than_silently_accepted(catalog, layout):
    """The failure mode of composing on one device and executing on another."""
    import copy
    stale = copy.deepcopy(layout)
    stale["catalog"]["fingerprint"] = "0" * 64
    result = validate_layout(stale, catalog)
    codes = {d.code for d in result.diagnostics}
    assert "TSR_LAYOUT_CATALOG_MISMATCH" in codes
    assert not result.ok


def test_an_unpinned_layout_warns(catalog, layout):
    import copy
    unpinned = copy.deepcopy(layout)
    unpinned["catalog"].pop("fingerprint", None)
    result = validate_layout(unpinned, catalog)
    codes = {d.code for d in result.diagnostics}
    assert "TSR_LAYOUT_CATALOG_UNPINNED" in codes
    assert result.ok, "an unpinned layout is a warning, not an error"


def test_fingerprint_ignores_timestamps_but_not_geometry(catalog):
    import copy
    from tessera.catalog import fingerprint
    same = copy.deepcopy(catalog)
    same["generated_utc"] = "1999-01-01T00:00:00+00:00"
    same["assets"][0]["provenance"]["created_utc"] = "1999-01-01T00:00:00+00:00"
    assert fingerprint(same) == fingerprint(catalog), \
        "a rebuild must not invalidate every layout ever composed"

    changed = copy.deepcopy(catalog)
    changed["assets"][0]["dimensions"]["size"][0] += 0.2
    assert fingerprint(changed) != fingerprint(catalog), \
        "a real dimensional change must invalidate composed layouts"
