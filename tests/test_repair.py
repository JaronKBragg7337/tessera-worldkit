"""The repair hand applies data, not guesses.

SPDX-License-Identifier: 0BSD
"""
from broken_layouts import CASES
from tessera.repair import apply_repair_pass, repair_layout
from tessera.validate import Collector, validate_layout


def test_repair_reaches_a_fixed_point_for_a_floating_instance(catalog, layout):
    broken = CASES["floating"][0](layout)
    repaired, summary, report = repair_layout(broken, catalog)
    assert summary["status"] == "passed"
    assert summary["applied_count"] >= 1
    assert report["counts"]["errors"] == 0
    assert validate_layout(repaired, catalog).ok


def test_repair_refuses_conflicting_transforms(layout):
    collector = Collector()
    collector.error(
        code="A", rule="test", what="A.", where={"instance": layout["instances"][0]["id"]},
        why="test", expected=0, actual=1, fix="move",
        fix_transform={"translate": [0, 0, 1]})
    collector.error(
        code="B", rule="test", what="B.", where={"instance": layout["instances"][0]["id"]},
        why="test", expected=0, actual=1, fix="move",
        fix_transform={"translate": [0, 0, -1]})
    repaired, applied, skipped = apply_repair_pass(layout, collector)
    assert not applied
    assert skipped and skipped[0]["reason"].startswith("conflicting")
    assert repaired == layout
