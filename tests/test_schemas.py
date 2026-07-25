"""The shipped JSON Schemas must actually describe the shipped data.
SPDX-License-Identifier: 0BSD

A schema nobody validates against is documentation that rots.
"""
import json
import os

import pytest

jsonschema = pytest.importorskip("jsonschema")


def _load(root, name):
    with open(os.path.join(root, "schema", name), encoding="utf-8") as fh:
        return json.load(fh)


def _registry(root):
    from referencing import Registry, Resource
    resources = []
    for name in ("asset.schema.json", "catalog.schema.json",
                 "layout.schema.json", "report.schema.json"):
        doc = _load(root, name)
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


def test_every_asset_validates(root, catalog):
    schema = _load(root, "asset.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    for asset in catalog["assets"]:
        errors = sorted(validator.iter_errors(asset), key=lambda e: e.path)
        assert not errors, "%s: %s" % (asset["id"], errors[0].message)


def test_catalog_validates(root, catalog):
    schema = _load(root, "catalog.schema.json")
    validator = jsonschema.Draft202012Validator(schema, registry=_registry(root))
    errors = sorted(validator.iter_errors(catalog), key=lambda e: e.path)
    assert not errors, errors[0].message


def test_layout_validates(root, layout):
    schema = _load(root, "layout.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(layout), key=lambda e: e.path)
    assert not errors, errors[0].message


def test_brief_validates(root, catalog):
    from tessera.brief import build_brief
    schema = _load(root, "brief.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(build_brief(catalog)), key=lambda e: e.path)
    assert not errors, errors[0].message


def test_report_validates(root, catalog, layout):
    from tessera.validate import build_report, validate_layout
    schema = _load(root, "report.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    from broken_layouts import CASES
    for name in ("floating", "intersection", "aperture_blocked"):
        c = validate_layout(CASES[name][0](layout), catalog)
        report = build_report(c, name, "layout")
        errors = sorted(validator.iter_errors(report), key=lambda e: e.path)
        assert not errors, "%s: %s" % (name, errors[0].message)
