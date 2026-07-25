"""Reachability: the property that used to be unfalsifiable.

SPDX-License-Identifier: 0BSD

A benchmark draft stacked three crates where a staircase belonged and wrote
"two stories with interior access". Every geometric rule passed. These tests
exist so that claim can never pass again.
"""
import importlib.util
import json
import os

import pytest

from tessera.navigate import NavGrid, grid_from_instances
from tessera.validate import validate_layout
from tessera.validate.layout import Instance


def _grid(catalog, layout):
    index = {a["id"]: a for a in catalog["assets"]}
    return grid_from_instances([Instance(s, index[s["asset"]])
                                for s in layout["instances"]])


@pytest.fixture(scope="module")
def two_storey(root, catalog):
    """Assembled against the fixture catalog, not read from disk.

    Reading the committed layout would fail the catalog pin, because the
    fixture builds without meshes and therefore fingerprints differently. That
    the pin fires here is the pin working.
    """
    path = os.path.join(root, "examples", "safehouse_two_storey", "build.py")
    spec = importlib.util.spec_from_file_location("two_storey_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = module.build(catalog)
    layout = builder.to_layout()
    ground = catalog["derived"]["floor_top_z"]
    upper = ground + catalog["derived"]["storey_height"]
    layout["reachability"] = [
        {"label": "terrain up the stoop to the threshold",
         "from": [6.0, -1.6, 0.0], "to": [6.0, -0.15, ground], "must": True},
        {"label": "ground floor to mezzanine",
         "from": [6.0, 2.0, ground], "to": [6.0, 10.0, upper], "must": True},
        {"label": "mezzanine back down to the ground floor",
         "from": [6.0, 10.0, upper], "to": [2.0, 2.0, ground], "must": True},
        {"label": "outside cannot reach the mezzanine except through the house",
         "from": [14.0, 14.0, 0.0], "to": [6.0, 10.0, upper], "must": False},
    ]
    return layout


@pytest.fixture(scope="module")
def interior_rooms(root, catalog):
    """The free-standing room, assembled against the fixture catalog."""
    path = os.path.join(root, "examples", "interior_rooms", "build.py")
    spec = importlib.util.spec_from_file_location("interior_rooms_build", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = module.build(catalog)
    layout = builder.to_layout()
    ground = catalog["derived"]["floor_top_z"]
    layout["reachability"] = [
        {"label": "terrain up the stoop to the threshold",
         "from": [6.0, -1.6, 0.0], "to": [6.0, -0.15, ground], "must": True},
        {"label": "corridor into the room through the interior doorway",
         "from": [8.0, 1.0, ground], "to": [8.0, 6.0, ground], "must": True},
        {"label": "back out of the room to the entrance",
         "from": [12.0, 8.0, ground], "to": [2.0, 1.0, ground], "must": True},
    ]
    return layout


def test_the_world_has_an_edge(catalog):
    """Without one, a flood fill started outdoors never terminates.

    The terrain plane is standable everywhere it is empty, so an unbounded grid
    walks away forever. This is not an optimisation; it is what makes the
    question answerable.
    """
    grid = NavGrid([(0.0, 0.0, 0.0, 4.0, 4.0, 0.3)])
    assert grid.nx > 0 and grid.ny > 0
    assert not grid.in_bounds(-1, 0)
    assert not grid.in_bounds(0, grid.ny)
    reached = grid.flood(grid.locate((2.0, 2.0, 0.3)))
    assert 0 < len(reached) < grid.nx * grid.ny * 4


def test_a_step_taller_than_the_character_blocks_the_route(catalog):
    """0.6 m up is a wall as far as walking is concerned."""
    grid = NavGrid([
        (0.0, 0.0, 0.0, 4.0, 4.0, 0.2),      # low platform
        (4.0, 0.0, 0.0, 8.0, 4.0, 0.8),      # high platform, 0.6 m above it
    ])
    ok, detail = grid.route_exists((2.0, 2.0, 0.2), (6.0, 2.0, 0.8))
    assert not ok, detail
    assert detail["reason"] == "no_route"


def test_a_step_within_the_limit_does_not(catalog):
    grid = NavGrid([
        (0.0, 0.0, 0.0, 4.0, 4.0, 0.2),
        (4.0, 0.0, 0.0, 8.0, 4.0, 0.6),      # 0.4 m above, inside step_up
    ])
    ok, _ = grid.route_exists((2.0, 2.0, 0.2), (6.0, 2.0, 0.6))
    assert ok


def test_reachability_is_conservative_not_optimistic(catalog):
    """A gap narrower than the character must be refused.

    Everywhere this solver says you can stand, you can -- the character is
    tested as a box, which is larger than the capsule it stands for. It may
    refuse a squeeze that would work. That is the safe direction.
    """
    # The goal has to be fully enclosed. A single wall, however long, has ends,
    # and the solver correctly walks around them -- which it did, twice, while
    # this test was being written.
    grid = NavGrid([
        (0.0, 0.0, 0.0, 8.0, 6.0, 0.2),                  # floor
        (3.0, 1.0, 0.0, 3.2, 2.6, 2.5),                  # west wall, lower half
        (3.0, 3.0, 0.0, 3.2, 5.0, 2.5),                  # west wall, upper half
        (3.0, 1.0, 0.0, 6.0, 1.2, 2.5),                  # south
        (3.0, 4.8, 0.0, 6.0, 5.0, 2.5),                  # north
        (5.8, 1.0, 0.0, 6.0, 5.0, 2.5),                  # east
    ])
    ok, _ = grid.route_exists((1.0, 3.0, 0.2), (4.5, 3.0, 0.2))
    assert not ok, "a 0.4 m gap must not admit a 0.7 m character"

    wider = NavGrid([
        (0.0, 0.0, 0.0, 8.0, 6.0, 0.2),
        (3.0, 1.0, 0.0, 3.2, 2.2, 2.5),                  # same room, 1.2 m gap
        (3.0, 3.4, 0.0, 3.2, 5.0, 2.5),
        (3.0, 1.0, 0.0, 6.0, 1.2, 2.5),
        (3.0, 4.8, 0.0, 6.0, 5.0, 2.5),
        (5.8, 1.0, 0.0, 6.0, 5.0, 2.5),
    ])
    ok2, detail = wider.route_exists((1.0, 3.0, 0.2), (4.5, 3.0, 0.2))
    assert ok2, ("a 1.2 m doorway must admit a 0.7 m character, or the solver "
                 "is uselessly pessimistic: %s" % detail)


def test_the_two_storey_house_proves_every_route_it_claims(catalog, two_storey):
    result = validate_layout(two_storey, catalog)
    assert result.ok, "\n".join(d.human() for d in result.errors)
    proven = [d for d in result.diagnostics
              if d.code == "TSR_LAYOUT_REACHABILITY_PROVEN"]
    assert len(proven) == len(two_storey["reachability"])


def test_interior_access_between_storeys_is_real(catalog, two_storey):
    """The exact claim the benchmark draft made falsely."""
    grid = _grid(catalog, two_storey)
    ground = catalog["derived"]["floor_top_z"]
    upper = ground + catalog["derived"]["storey_height"]
    ok, detail = grid.route_exists((6.0, 2.0, ground), (6.0, 10.0, upper))
    assert ok, detail
    back, _ = grid.route_exists((6.0, 10.0, upper), (2.0, 2.0, ground))
    assert back, "a staircase you cannot come back down is not interior access"


def test_removing_the_stair_removes_the_access(catalog, two_storey):
    """The control. If this still passed, the test above would prove nothing."""
    import copy
    crippled = copy.deepcopy(two_storey)
    crippled["instances"] = [i for i in crippled["instances"]
                             if "stair_straight" not in i["id"]]
    grid = _grid(catalog, crippled)
    ground = catalog["derived"]["floor_top_z"]
    upper = ground + catalog["derived"]["storey_height"]
    ok, _ = grid.route_exists((6.0, 2.0, ground), (6.0, 10.0, upper))
    assert not ok, "the mezzanine is reachable with no stair in the building"

    result = validate_layout(crippled, catalog)
    codes = {d.code for d in result.diagnostics}
    assert "TSR_LAYOUT_UNREACHABLE" in codes
    assert not result.ok


def test_stacked_crates_are_not_a_staircase(catalog, two_storey):
    """What the benchmark draft actually built, checked directly."""
    import copy
    from tessera.assemble import Builder
    b = Builder(catalog, "crate ladder")
    pad = b.ground("tsr:shell/foundation.pad.4m", 0, 0)
    floor = b.ground("tsr:shell/floor.slab.4m", 0, 0, on=pad)
    crate = b.ground("tsr:shell/prop.crate.small", 1.0, 1.0, on=floor)
    for _ in range(2):
        crate = b.ground("tsr:shell/prop.crate.small", 1.0, 1.0,
                         on=crate, surface="top")
    layout = b.to_layout()
    ground = catalog["derived"]["floor_top_z"]
    grid = _grid(catalog, layout)
    ok, _ = grid.route_exists((3.0, 3.0, ground),
                              (1.0, 1.0, ground + catalog["derived"]["storey_height"]))
    assert not ok, "three crates must not count as a route to the next storey"


def test_a_doorway_you_cannot_step_up_to_is_not_an_entrance(catalog):
    """Found by this solver in a scene that had already passed every other rule.

    The workshop's floor sits 0.50 m above the ground outside. The door was
    open, the aperture was wide enough, collision preserved it -- and nobody
    could get in.
    """
    from tessera.assemble import Builder
    b = Builder(catalog, "threshold")
    pad = b.ground("tsr:shell/foundation.pad.4m", 0, 0)
    floor = b.ground("tsr:shell/floor.slab.4m", 0, 0, on=pad)
    b.ground("tsr:shell/wall.doorway.4m", 0, 0, yaw=0.0, on=floor)
    without = _grid(catalog, b.to_layout())
    ok, _ = without.route_exists((2.0, -1.5, 0.0), (2.0, 2.0, 0.5))
    assert not ok, "0.50 m is more than a character can step up"

    b.place("tsr:shell/stair.stoop.1m2", (1.4, -0.60, 0.0), yaw=0.0)
    with_stoop = _grid(catalog, b.to_layout())
    ok2, detail = with_stoop.route_exists((2.0, -1.5, 0.0), (2.0, 2.0, 0.5))
    assert ok2, detail


# ------------------------------------------------------- M3 interior pieces
# An interior room has to be two things at once, and before the interior
# doorway existed it could only be one: the L corner closes a corner without
# overlapping anything but carries no opening, so a room boxed in with corners
# alone had no way in. These four tests hold both halves.

def test_the_interior_room_proves_every_route_it_claims(catalog, interior_rooms):
    result = validate_layout(interior_rooms, catalog)
    assert result.ok, "\n".join(d.human() for d in result.errors)
    proven = [d for d in result.diagnostics
              if d.code == "TSR_LAYOUT_REACHABILITY_PROVEN"]
    assert len(proven) == len(interior_rooms["reachability"])


def test_the_interior_room_can_be_entered(catalog, interior_rooms):
    """Closed *and* enterable. The thing M3 existed to make expressible."""
    grid = _grid(catalog, interior_rooms)
    ground = catalog["derived"]["floor_top_z"]
    ok, detail = grid.route_exists((8.0, 1.0, ground), (8.0, 6.0, ground))
    assert ok, detail
    back, _ = grid.route_exists((12.0, 8.0, ground), (2.0, 1.0, ground))
    assert back, "a room you cannot leave is a trap, not a room"


def test_swapping_the_doorway_for_a_wall_seals_the_room(catalog, interior_rooms):
    """The control, and the whole point.

    Replace the one interior doorway with a solid interior wall at the same
    transform and the room must become unreachable. If this still passed, the
    test above would be proving nothing about the doorway -- it would only be
    proving that a flood fill can find *some* route, which it can, around the
    outside of the room.
    """
    import copy
    sealed = copy.deepcopy(interior_rooms)
    swapped = 0
    for inst in sealed["instances"]:
        if inst["asset"] == "tsr:shell/wall.interior.doorway.4m":
            inst["asset"] = "tsr:shell/wall.interior.4m"
            swapped += 1
    assert swapped == 1, "the example is meant to have exactly one way in"

    grid = _grid(catalog, sealed)
    ground = catalog["derived"]["floor_top_z"]
    ok, _ = grid.route_exists((8.0, 1.0, ground), (8.0, 6.0, ground))
    assert not ok, ("the room is enterable with no opening in it, so the "
                    "doorway was never what was letting the character in")

    result = validate_layout(sealed, catalog)
    codes = {d.code for d in result.diagnostics}
    assert "TSR_LAYOUT_UNREACHABLE" in codes
    assert not result.ok


def test_the_interior_corner_carries_no_opening(catalog):
    """Stated as a constraint in the part, asserted here so it stays true.

    A room whose partition sides are one module each is closed by corners alone
    and cannot be entered. That is a property of the room and it is why the
    example uses a three-module side; if someone later carves an aperture into
    the corner to "fix" it, this test says so.
    """
    index = {a["id"]: a for a in catalog["assets"]}
    corner = index["tsr:shell/wall.interior.corner.4m"]
    assert corner["apertures"] == []

    doorway = index["tsr:shell/wall.interior.doorway.4m"]
    assert len(doorway["apertures"]) == 1
    hole = doorway["apertures"][0]
    assert hole["traversable"]
    assert hole["fits_capsule"]["admits_reference_character"], (
        "an interior doorway the reference character cannot pass is not a door")
    # Same clear opening as the exterior doorway, so one leaf serves both.
    outside = index["tsr:shell/wall.doorway.4m"]["apertures"][0]
    assert hole["clear_width"] == outside["clear_width"]
    assert hole["clear_height"] == outside["clear_height"]
