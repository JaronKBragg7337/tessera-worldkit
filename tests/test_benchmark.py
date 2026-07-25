"""The constrained-agent benchmark, pinned as a regression test.

SPDX-License-Identifier: 0BSD

A real draft written by a model with no checkout, no terminal and no renderer.
If a future change stops the validator catching this class of mistake, this
fails. See benchmarks/constrained_agent/README.md.
"""
import importlib.util
import json
import os

import pytest

from tessera.assemble import AssemblyError
from tessera.validate import validate_layout

V1 = "benchmarks/constrained_agent/deepseek_safehouse_v1.py"


def _load(root, path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(root, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exec_patched(root):
    """The draft with only the round-2 one-line repair applied."""
    path = os.path.join(root, V1)
    source = open(path, encoding="utf-8").read()
    source = source.replace('surface="top" if i == 1 else "top_x")',
                            'surface="top_x")')
    namespace = {"__name__": "patched", "__file__": path}
    exec(compile(source, path, "exec"), namespace)
    return namespace


def test_the_original_draft_fails_loudly_with_a_useful_message(root, catalog):
    """Round 1: it must not run, and the error must name the alternatives."""
    module = _load(root, V1, "deepseek_v1")
    with pytest.raises(AssemblyError) as exc:
        module.build(catalog)
    message = str(exc.value)
    assert "has no connector 'top'" in message
    assert "top_x" in message, "the error must list what the asset does have"


def test_the_one_line_repair_runs_but_does_not_validate(root, catalog):
    """Round 2: running is not the same as being correct."""
    module = _load(root, V1, "deepseek_v1b")
    namespace = _exec_patched(root)
    builder = namespace["build"](catalog)
    layout = builder.to_layout()

    result = validate_layout(layout, catalog)
    assert not result.ok, "a script that merely runs must not be mistaken for a valid one"
    found = {d.code for d in result.diagnostics}
    for expected in ("TSR_LAYOUT_INTERSECTION", "TSR_LAYOUT_BURIED",
                     "TSR_LAYOUT_FLOATING", "TSR_LAYOUT_UNBALANCED"):
        assert expected in found, "the benchmark must still surface %s" % expected
    assert len(result.errors) >= 25, \
        "only %d errors; the validator has gone quiet on a known-bad draft" % len(result.errors)


def test_duplicate_walls_are_caught_as_whole_volume_overlaps(root, catalog):
    """The clearest signal in the whole report: a full asset volume of overlap."""
    namespace = _exec_patched(root)
    result = validate_layout(namespace["build"](catalog).to_layout(), catalog)
    wall_volume = next(a["geometry"]["signed_volume"] for a in catalog["assets"]
                       if a["id"].endswith("wall.straight.4m"))
    exact = [d for d in result.errors
             if d.code == "TSR_LAYOUT_INTERSECTION"
             and abs(d.actual - wall_volume) < 1e-3]
    assert exact, "an exactly duplicated wall should overlap by its own full volume"


def test_the_repaired_safe_house_validates(root, catalog):
    """Round 5, and the standard every example in this repository is held to."""
    module = _load(root, "examples/safehouse/build.py", "safehouse")
    layout = module.build(catalog).to_layout()
    result = validate_layout(layout, catalog)
    assert result.ok, "\n".join(d.human() for d in result.errors)
    assert not result.warnings, "\n".join(d.human() for d in result.warnings)
    assert layout["placement_method"]["explicit"] == 0
