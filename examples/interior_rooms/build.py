"""A room partitioned from a building corner, closed and entered.

SPDX-License-Identifier: 0BSD

The first M3 interior example had to stand free of the perimeter. A regular
partition beginning at a perimeter wall's body face drove its lower 0.03 m
through the proud plinth, while stopping on the next grid step left a slot.

``wall.junction.trim.3m8`` closes that gap. Its rebated end mates to a dedicated
receiver on either face of a perimeter wall, clearing the plinth at floor level,
and its other end lands on the next 4 m bay line. An ordinary interior doorway
and corner continue from there without handed variants.

This scene reuses the south and west perimeter walls as two sides of a room.
Two junction trims, one interior doorway and one interior corner form the other
two sides. Three reachability claims prove that the character can get in and
back out. ``tests/test_navigation.py`` swaps the interior doorway for a solid
wall and requires ``TSR_LAYOUT_UNREACHABLE`` -- the control that proves the
route is through the door rather than around an unclosed junction.

Run:  python3 examples/interior_rooms/build.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tessera.assemble import Builder      # noqa: E402
from tessera.catalog import load_catalog  # noqa: E402

A = "tsr:shell/"
BAY = 4.0

#: The shell. 4 x 3 bays. The gable direction has to span exactly
#: ``derived.building_span_for_one_gable``, which is why it is 3 bays deep and
#: not 4 -- a roof is not free to be any size.
BAYS_X, BAYS_Y = 4, 3
SPAN_X, SPAN_Y = BAY * BAYS_X, BAY * BAYS_Y

def build(catalog):
    b = Builder(catalog, name="Room Inside a Building")
    wall_t = catalog["config"]["WALL_THICKNESS"]

    # ------------------------------------------------------------- ground
    pads = {(gx, gy): b.ground(A + "foundation.pad.4m", gx * BAY, gy * BAY)
            for gx in range(BAYS_X) for gy in range(BAYS_Y)}
    floors = {k: b.ground(A + "floor.slab.4m", k[0] * BAY, k[1] * BAY, on=pad)
              for k, pad in pads.items()}

    def slab(x, y):
        """The slab under a point, so grounding names a real host."""
        return floors[(min(int(x // BAY), BAYS_X - 1),
                       min(int(y // BAY), BAYS_Y - 1))]

    # ---------------------------------------------------------- perimeter
    # Four L corners and the straight middles between them: 16 x 12 m closed
    # with no overlapping geometry, exactly as the workshop and the safehouse
    # close 12 x 12.
    corners = {
        "sw": b.ground(A + "wall.corner.4m", 0.0, 0.0, yaw=0.0, on=floors[(0, 0)]),
        "se": b.ground(A + "wall.corner.4m", SPAN_X, 0.0, yaw=90.0, on=floors[(3, 0)]),
        "ne": b.ground(A + "wall.corner.4m", SPAN_X, SPAN_Y, yaw=180.0, on=floors[(3, 2)]),
        "nw": b.ground(A + "wall.corner.4m", 0.0, SPAN_Y, yaw=270.0, on=floors[(0, 2)]),
    }
    entrance = b.ground(A + "wall.doorway.4m", BAY, 0.0, yaw=0.0, on=floors[(1, 0)])
    south_junction_host = b.ground(
        A + "wall.straight.4m", 2 * BAY, 0.0, yaw=0.0, on=floors[(2, 0)])
    window = b.ground(A + "wall.window.4m", 3 * BAY, SPAN_Y, yaw=180.0,
                      on=floors[(2, 2)])
    b.ground(A + "wall.straight.4m", 2 * BAY, SPAN_Y, yaw=180.0, on=floors[(1, 2)])
    west_junction_host = b.ground(
        A + "wall.straight.4m", wall_t, BAY, yaw=90.0, on=floors[(0, 1)])
    b.ground(A + "wall.straight.4m", SPAN_X - wall_t, 2 * BAY, yaw=270.0,
             on=floors[(3, 1)])

    b.mate(A + "door.leaf.1m2", "hinge", entrance, "jamb_neg_y")
    b.mate(A + "window.leaf.1m8", "mount", window, "jamb_neg_y")

    # The threshold. The floor is 0.50 m above the terrain outside, which is
    # twice what the reference character can step up -- proven, not assumed, by
    # the stoop's own usability check.
    b.place(A + "stair.stoop.1m2", (5.4, -0.60, 0.0), yaw=0.0)

    # ---------------------------------------------------------- the room
    # The south and west perimeter walls are two room sides. The transforms
    # below, including which end carries the rebate, are solved from the
    # dedicated wall_face / wall_junction connector pair.
    south_trim = b.mate(
        A + "wall.junction.trim.3m8", "perimeter",
        south_junction_host, "partition_pos_x_pos_y")
    west_trim = b.mate(
        A + "wall.junction.trim.3m8", "perimeter",
        west_junction_host, "partition_pos_x_neg_y")

    # The north side continues from the west trim with the one opening. The
    # corner is then solved from the doorway's far seam, and its return leg
    # meets the south trim automatically to close the east side.
    interior_doorway = b.mate(
        A + "wall.interior.doorway.4m", "edge_neg_x",
        west_trim, "partition")
    b.mate(
        A + "wall.interior.corner.4m", "edge_pos_x",
        interior_doorway, "edge_pos_x")

    # No leaf is hung in the interior doorway. The front door has one because a
    # house is entered through a door that shuts; a shut leaf here would turn
    # the claim below into a statement about the leaf rather than about the
    # room, which is not what is being demonstrated.

    # ------------------------------------------------------------ fitting
    # Props here are pivoted at their centre, not at a corner, and the workbench
    # carries a 0.70 m working clearance on its -Y face. Both are in the
    # catalog; placing one 0.9 m from a wall because a wall is 4 m long is how
    # you get TSR_LAYOUT_BURIED from something that looked fine in plan.
    b.ground(A + "prop.workbench", 5.0, 5.8, yaw=0.0, on=slab(5.0, 5.8))
    b.ground(A + "prop.crate.small", 10.5, 6.5, yaw=12.0, on=slab(10.5, 6.5))
    # ...and one in the corridor, where a guard post would go.
    b.ground(A + "prop.crate.small", 14.9, 1.2, yaw=-18.0, on=slab(14.9, 1.2))

    # --------------------------------------------------------------- roof
    # A gable across Y, which spans exactly 2 x ROOF_RUN. Four panels a side.
    south = [b.ground(A + "roof.panel.4m", i * BAY, 0.0, yaw=0.0,
                      on=corners["sw"] if i == 0 else entrance,
                      surface="top_x" if i == 0 else "top")
             for i in range(BAYS_X)]
    for i in range(BAYS_X):
        b.ground(A + "roof.panel.4m", (i + 1) * BAY, SPAN_Y, yaw=180.0,
                 on=window if i == 2 else corners["ne"],
                 surface="top" if i == 2 else "top_x")
    for panel in south:
        b.mate(A + "roof.ridge.4m", "seat", panel, "ridge_cap")

    b.discovered_connections = b.autoconnect()
    return b


def main():
    catalog = load_catalog(os.path.join(ROOT, "build", "catalog.json"))
    b = build(catalog)
    ground = catalog["derived"]["floor_top_z"]

    layout = b.to_layout(
        "A 16 x 12 m shell with a room partitioned from its south-west corner. "
        "The room reuses two perimeter walls; two rebated junction trims, one "
        "interior doorway and one interior corner close the other sides without "
        "overlapping the perimeter plinth."
    )
    layout["discovered_connections"] = b.discovered_connections

    # Each claim is proven by flood fill or reported as a lie. Remove the
    # doorway and the second and third stop being true -- which is what
    # tests/test_navigation.py asserts, so "enterable" is measured rather than
    # described.
    layout["reachability"] = [
        {"label": "terrain up the stoop to the threshold",
         "from": [6.0, -1.6, 0.0], "to": [6.0, -0.15, ground], "must": True},
        {"label": "corridor into the room through the interior doorway",
         "from": [6.0, 9.0, ground], "to": [6.0, 6.0, ground], "must": True},
        {"label": "back out of the room to the entrance",
         "from": [10.0, 6.0, ground], "to": [6.0, 1.0, ground], "must": True},
    ]

    out = os.path.join(HERE, "layout.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(layout, fh, indent=2)
    print("wrote %s" % out)
    print("  instances                %d" % layout["instance_count"])
    print("  solved from the contract %d" % layout["placement_method"]["solved_from_contract"])
    print("  seams discovered         %d" % b.discovered_connections)
    print("  reachability claims      %d" % len(layout["reachability"]))
    return layout


if __name__ == "__main__":
    main()
