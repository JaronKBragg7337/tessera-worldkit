"""Every rule must fire on a case built to break it.
SPDX-License-Identifier: 0BSD"""
import copy

import pytest

from broken_layouts import ASSET_CASES, CASES
from tessera.validate import (
    Collector, build_report, render_terminal, validate_asset, validate_layout,
)


def codes(collector):
    return {d.code for d in collector.diagnostics}


def test_good_catalog_passes(catalog):
    c = Collector()
    for a in catalog["assets"]:
        validate_asset(a, c)
    assert c.ok, "\n".join(d.human() for d in c.errors)


def test_good_layout_passes(catalog, layout):
    c = validate_layout(layout, catalog)
    assert c.ok, "\n".join(d.human() for d in c.errors)


def test_good_layout_verifies_every_declared_connection(catalog, layout):
    c = validate_layout(layout, catalog)
    stats = c.connection_stats
    assert stats["declared"] > 0
    assert stats["verified"] == stats["declared"], \
        "%d of %d connections failed verification" % (
            stats["declared"] - stats["verified"], stats["declared"])


@pytest.mark.parametrize("name", sorted(CASES))
def test_layout_rule_fires(catalog, layout, name):
    mutate, expected = CASES[name]
    broken = mutate(layout)
    c = validate_layout(broken, catalog)
    assert expected in codes(c), (
        "%s did not produce %s; produced %s" % (name, expected, sorted(codes(c))))
    assert not c.ok, "%s must fail validation" % name


@pytest.mark.parametrize("name", sorted(ASSET_CASES))
def test_asset_rule_fires(catalog, name):
    mutate, expected, target = ASSET_CASES[name]
    assets = copy.deepcopy(catalog["assets"])
    picked = None
    for a in assets:
        if target is None or a["id"].endswith(target):
            picked = mutate(a)
            break
    assert picked is not None
    c = Collector()
    validate_asset(picked, c)
    assert expected in codes(c), (
        "%s did not produce %s; produced %s" % (name, expected, sorted(codes(c))))


def test_diagnostics_are_actionable(catalog, layout):
    """Every error must say what, why, expected, actual and a fix."""
    broken = CASES["floating"][0](layout)
    c = validate_layout(broken, catalog)
    for d in c.errors:
        assert d.what and d.what.endswith("."), d.code
        assert d.why, "%s has no why" % d.code
        assert d.fix, "%s has no fix" % d.code
        assert d.expected is not None or d.actual is not None, d.code
        assert d.rule, "%s has no rule id" % d.code


def test_floating_fix_transform_actually_fixes_it(catalog, layout):
    """The machine-applicable correction must make the layout pass.

    This is the property that turns the validator from a report into a repair
    loop: an agent applies fix_transform and re-runs, with no rendering.
    """
    broken = CASES["floating"][0](layout)
    c = validate_layout(broken, catalog)
    floats = [d for d in c.errors if d.code == "TSR_LAYOUT_FLOATING"]
    assert floats
    for d in floats:
        target = d.where["instance"]
        delta = d.fix_transform["translate"]
        for inst in broken["instances"]:
            if inst["id"] == target:
                inst["position"] = [inst["position"][i] + delta[i] for i in range(3)]
    again = validate_layout(broken, catalog)
    assert not [d for d in again.errors if d.code == "TSR_LAYOUT_FLOATING"], \
        "applying fix_transform did not clear the floating error"


def test_report_renders_for_humans_and_machines(catalog, layout):
    c = validate_layout(CASES["intersection"][0](layout), catalog)
    report = build_report(c, "test", "layout")
    assert report["status"] == "failed"
    assert report["counts"]["errors"] > 0
    assert report["coverage"]["checks_run_count"] >= 15
    text = render_terminal(report, colour=False)
    assert "TSR_LAYOUT_INTERSECTION" in text
    assert "why" in text and "fix" in text
    import json
    json.dumps(report)  # must be serialisable
