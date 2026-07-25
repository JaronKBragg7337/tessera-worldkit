"""The catalog must be internally coherent and self-describing.
SPDX-License-Identifier: 0BSD"""
import pytest

from tessera.contract import (
    CONNECTOR_COMPATIBILITY, CONNECTOR_KINDS, SCALE_CLASSES, SCHEMA_ID,
)
from tessera.units import ENGINE_SPACES


def test_every_asset_declares_the_contract(catalog):
    for a in catalog["assets"]:
        assert a["schema"] == SCHEMA_ID
        for key in ("dimensions", "pivot", "axes", "placement", "connectors",
                    "occupancy", "clearance", "collision", "materials",
                    "geometry", "provenance", "license", "validation"):
            assert key in a, "%s missing %s" % (a["id"], key)


def test_compatibility_table_is_symmetric():
    for kind, partners in CONNECTOR_COMPATIBILITY.items():
        assert kind in CONNECTOR_KINDS
        for p in partners:
            assert p in CONNECTOR_KINDS, "%s -> unknown %s" % (kind, p)
            assert kind in CONNECTOR_COMPATIBILITY.get(p, ()), \
                "%s accepts %s but not the reverse" % (kind, p)


def test_geometry_matches_declared_dimensions(catalog):
    for a in catalog["assets"]:
        b = a["dimensions"]["bounds"]
        for i in range(3):
            assert a["dimensions"]["size"][i] == pytest.approx(
                b["max"][i] - b["min"][i], abs=1e-6)


def test_occupancy_is_disjoint_and_inside_the_bounds(catalog):
    for a in catalog["assets"]:
        b = a["dimensions"]["bounds"]
        tol = a["occupancy"]["approximation_tolerance"] + 1e-6
        assert a["occupancy"]["disjoint"], a["id"]
        for box in a["occupancy"]["boxes"]:
            for i in range(3):
                assert box[i] >= b["min"][i] - tol
                assert box[i + 3] <= b["max"][i] + tol


def test_collision_never_seals_a_traversable_aperture(catalog):
    from tessera.boxset import boxes_overlap
    found = 0
    for a in catalog["assets"]:
        for ap in a["apertures"]:
            if not ap["traversable"]:
                continue
            found += 1
            ab = ap["bounds"]
            box = (ab["min"][0], ab["min"][1], ab["min"][2],
                   ab["max"][0], ab["max"][1], ab["max"][2])
            for hull in a["collision"]["hulls"]:
                assert not boxes_overlap(tuple(hull), box, gap=5e-4), \
                    "%s collision seals %s" % (a["id"], ap["id"])
    assert found >= 1, "the kit must contain at least one traversable aperture"


def test_modular_pivots_sit_on_the_base(catalog):
    for a in catalog["assets"]:
        if a["semantic_role"] in ("roof", "roof_trim", "door", "window"):
            continue
        assert a["pivot"]["base_offset_z"] == pytest.approx(0.0, abs=5e-4), a["id"]


def test_engine_space_conversions_round_trip():
    for name, space in ENGINE_SPACES.items():
        p = (1.0, 2.0, 3.0)
        out = space.convert_point(p)
        back = [0.0, 0.0, 0.0]
        for engine_axis, (src, sign) in enumerate(space.axis_map):
            back[src] = out[engine_axis] * sign / space.linear_scale
        assert tuple(round(v, 9) for v in back) == p, name


def test_scale_classes_are_distinct():
    assert len(set(SCALE_CLASSES.values())) == len(SCALE_CLASSES)
