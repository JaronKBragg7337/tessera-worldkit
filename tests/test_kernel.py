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


def test_timestamps_are_pinnable_for_reproducible_builds(monkeypatch):
    """SOURCE_DATE_EPOCH must pin the only non-deterministic field.

    Everything else in a catalog is a pure function of the inputs, so the
    timestamp is the only thing that can make two identical builds differ.
    """
    from tessera.measure import utcnow
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    assert utcnow() == "2023-11-14T22:13:20+00:00"
    assert utcnow() == utcnow()
    monkeypatch.delenv("SOURCE_DATE_EPOCH")
    assert utcnow().endswith("+00:00")


@pytest.mark.parametrize("argv", [
    ["--json", "doctor"],
    ["doctor", "--json"],
    ["doctor"],
])
def test_json_flag_works_on_either_side_of_the_subcommand(argv, capsys):
    """An agent writes `tessera doctor --json` without thinking about it.

    Insisting on one position costs a whole failed invocation, which is exactly
    the kind of round-trip this project exists to remove.
    """
    from tessera.cli import main
    assert main(argv) == 0
    out = capsys.readouterr().out
    if "--json" in argv:
        import json
        assert json.loads(out)["blender_required"] is False
    else:
        assert "blender_required" in out


def test_every_text_output_uses_lf(tmp_path, catalog):
    """Byte-identical builds have to survive Windows too.

    Python's text mode translates newlines to CRLF on Windows, so without an
    explicit newline="\\n" the OBJ, MTL, catalog, report and brief writers all
    produce different bytes on a different operating system -- and a Windows
    contributor fails the "committed output is current" check for reasons
    nothing on screen explains. Found by actually building on Windows.
    """
    import json
    from tessera.brief import build_brief, write_brief
    from tessera.catalog import write_catalog
    from tessera.export.obj import write_obj
    from tessera.validate import build_report, validate_asset, Collector
    from tessera.boxset import BoxSet
    from tessera.mesh import surface_from_boxset
    from tessera.contract import MaterialSlot

    mesh = surface_from_boxset(BoxSet.from_box((0, 0, 0), (1, 1, 1)), "M")
    slot = MaterialSlot(0, "M", "structure")

    outputs = []
    obj = tmp_path / "probe.obj"
    write_obj(str(obj), mesh, [slot], "probe")
    outputs += [obj, tmp_path / "probe.mtl"]

    cat = tmp_path / "catalog.json"
    write_catalog(catalog, str(cat))
    outputs.append(cat)

    collector = Collector()
    validate_asset(catalog["assets"][0], collector)
    rep = tmp_path / "report.json"
    with open(rep, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(build_report(collector, "probe", "asset"), fh, indent=2)
    outputs.append(rep)

    brief = tmp_path / "brief.json"
    write_brief(build_brief(catalog), str(brief))
    outputs.append(brief)

    for path in outputs:
        raw = path.read_bytes()
        assert b"\r\n" not in raw, "%s contains CRLF" % path.name
