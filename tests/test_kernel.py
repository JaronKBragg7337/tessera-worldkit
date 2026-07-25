"""Geometry kernel invariants. SPDX-License-Identifier: 0BSD"""
import random

import pytest

from tessera.boxset import BoxSet, box_volume, boxes_overlap, split_box
from tessera.mesh import extrude_profile, surface_from_boxset


def test_split_is_a_partition():
    """a - b must tile exactly the part of a outside b, with no overlaps."""
    random.seed(7)
    for _ in range(200):
        a = (0, 0, 0, 4, 4, 4)
        b = tuple([round(random.uniform(-1, 3), 3) for _ in range(3)]
                  + [round(random.uniform(1, 5), 3) for _ in range(3)])
        b = (min(b[0], b[3]), min(b[1], b[4]), min(b[2], b[5]),
             max(b[0], b[3]) + 0.5, max(b[1], b[4]) + 0.5, max(b[2], b[5]) + 0.5)
        pieces = split_box(a, b)
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                assert not boxes_overlap(pieces[i], pieces[j]), "pieces overlap"
        overlap = 0.0
        for k in range(3):
            lo, hi = max(a[k], b[k]), min(a[k + 3], b[k + 3])
            if hi <= lo:
                overlap = None
                break
        expected = box_volume(a)
        if overlap is not None:
            shared = 1.0
            for k in range(3):
                shared *= max(0.0, min(a[k + 3], b[k + 3]) - max(a[k], b[k]))
            expected -= shared
        assert sum(box_volume(p) for p in pieces) == pytest.approx(expected, abs=1e-9)


def test_boxset_stays_disjoint_under_random_ops():
    random.seed(11)
    s = BoxSet.from_box((0, 0, 0), (6, 6, 6))
    for _ in range(30):
        p0 = [round(random.uniform(-1, 5), 2) for _ in range(3)]
        p1 = [round(v + random.uniform(0.3, 2.0), 2) for v in p0]
        (s.add if random.random() < 0.5 else s.subtract)(p0, p1)
        if s.is_empty():
            break
        assert s.is_disjoint()


def test_surface_is_watertight_and_volume_exact():
    s = BoxSet.from_box((0, 0, 0), (4, 0.2, 3))
    s.carve_aperture("d", "door", (1.4, -0.1, 0), (2.6, 0.3, 2.2), axis=1)
    s.carve_aperture("w", "window", (0.3, -0.1, 2.4), (1.0, 0.3, 2.8), axis=1)
    m = surface_from_boxset(s)
    assert m.is_watertight()
    assert m.signed_volume() > 0, "winding must be outward"
    assert m.signed_volume() == pytest.approx(s.volume(), abs=1e-9)


def test_prism_is_watertight():
    m = extrude_profile([(0, 0), (6, 2.5), (6, 2.68), (0, 0.18)], 0, 0, 4)
    assert m.is_watertight()
    assert m.signed_volume() > 0


def test_build_is_deterministic():
    def make():
        s = BoxSet.from_box((0, 0, 0), (4, 0.2, 3))
        s.carve_aperture("d", "door", (1.4, -0.1, 0), (2.6, 0.3, 2.2), axis=1)
        return surface_from_boxset(s)
    a, b = make(), make()
    assert a.positions == b.positions
    assert a.triangles == b.triangles


def test_degenerate_box_is_refused():
    with pytest.raises(ValueError):
        BoxSet.from_box((0, 0, 0), (0, 1, 1))
