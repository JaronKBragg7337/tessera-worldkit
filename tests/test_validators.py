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


# --------------------------------------------------------------- support rules
# Both discovered by running a real constrained-agent draft. See
# benchmarks/constrained_agent/README.md.

def test_a_cantilevered_slab_is_rejected(catalog):
    """A 4 x 4 floor slab held on one 4 x 0.2 wall edge falls over.

    Before this rule existed it validated clean, because it technically rested
    on something. Coverage alone cannot catch it: a genuine second-storey floor
    bearing only on its perimeter walls has similar coverage and is correct.
    The discriminator is whether the footprint centroid lies inside the convex
    hull of the contact patches.
    """
    from tessera.assemble import Builder
    b = Builder(catalog, "cantilever")
    pad = b.ground("tsr:shell/foundation.pad.4m", 0, 0)
    floor = b.ground("tsr:shell/floor.slab.4m", 0, 0, on=pad)
    wall = b.ground("tsr:shell/wall.straight.4m", 0, 0, yaw=0, on=floor)
    b.ground("tsr:shell/floor.slab.4m", 0, 0, on=wall, surface="top")
    c = validate_layout(b.to_layout(), catalog)
    assert "TSR_LAYOUT_UNBALANCED" in codes(c)
    assert not c.ok


def test_a_slab_balanced_on_a_workbench_warns_but_does_not_fail(catalog):
    """It will not topple, so it is not a placement error -- but say something."""
    from tessera.assemble import Builder
    b = Builder(catalog, "implausible")
    pad = b.ground("tsr:shell/foundation.pad.4m", 0, 0)
    floor = b.ground("tsr:shell/floor.slab.4m", 0, 0, on=pad)
    bench = b.ground("tsr:shell/prop.workbench", 2, 2, on=floor)
    b.ground("tsr:shell/floor.slab.4m", 0, 0, on=bench, surface="worktop")
    c = validate_layout(b.to_layout(), catalog)
    assert "TSR_LAYOUT_UNDERSUPPORTED" in codes(c)
    assert "TSR_LAYOUT_UNBALANCED" not in codes(c), "centrally balanced, so it stands"


def test_a_real_second_storey_on_four_walls_passes(catalog):
    """The case M3 depends on. A rule that failed this would be worse than none."""
    from tessera.assemble import Builder
    b = Builder(catalog, "second storey")
    pad = b.ground("tsr:shell/foundation.pad.4m", 0, 0)
    gnd = b.ground("tsr:shell/floor.slab.4m", 0, 0, on=pad)
    south = b.ground("tsr:shell/wall.straight.4m", 0, 0, yaw=0, on=gnd)
    b.ground("tsr:shell/wall.straight.4m", 4, 4, yaw=180, on=gnd)
    b.ground("tsr:shell/wall.straight.4m", 0.2, 0, yaw=90, on=gnd)
    b.ground("tsr:shell/wall.straight.4m", 3.8, 4, yaw=270, on=gnd)
    upper = b.ground("tsr:shell/floor.slab.4m", 0, 0, on=south, surface="top")
    c = validate_layout(b.to_layout(), catalog)
    for d in c.diagnostics:
        assert d.where.get("instance") != upper["id"], \
            "a floor bearing on four perimeter walls must not be flagged: %s" % d.code


def test_the_good_workshop_has_no_support_false_positives(catalog, layout):
    c = validate_layout(layout, catalog)
    for code in ("TSR_LAYOUT_UNBALANCED", "TSR_LAYOUT_UNDERSUPPORTED"):
        assert code not in codes(c), "%s fired on a known-good scene" % code
