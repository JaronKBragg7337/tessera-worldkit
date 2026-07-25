"""A room inside a building -- closed by interior corners, entered by a door.

SPDX-License-Identifier: 0BSD

``examples/safehouse`` partitions a storage alcove and says, in a comment, why
it is an alcove and not a room:

    Deliberately an alcove, open to the west, rather than a sealed room. The
    L corner piece exists so a rectangular *perimeter* closes without overlap;
    it carries no opening, so using two of them to box in an interior room
    would produce a room with no way in.

This is that room, built from the M3 interior pieces. A 16 x 12 m shell with a
free-standing 12 x 8 m room inside it and a circulation corridor all the way
around. The room is closed by four ``wall.interior.corner.4m`` and one
``wall.interior.4m``, and entered through one
``wall.interior.doorway.4m``. Whether it is really closed and really enterable
is not asserted here -- the validator floods the walkable volume and prints::

    INFO TSR_LAYOUT_REACHABILITY_PROVEN  Route proven: corridor into the room.

Why the room does not touch the perimeter
-----------------------------------------
It would be more natural to partition a corner off the shell and reuse two of
its perimeter walls. That does not work yet, and the reason is worth knowing
before you try it.

A perimeter wall's innermost surface is not its face -- it is its plinth, which
stands ``PLINTH_PROUD`` past the face on *both* sides. So the first solid a
partition meets is ``derived.perimeter_inner_face_inset`` = 0.23 m in from the
bay line, and 0.23 is not a whole number of ``GRID_XY`` units. A module-length
partition on the grid therefore cannot finish flush against a perimeter wall: it
either stops at 0.20 and drives its bottom ``PLINTH_HEIGHT`` through the plinth
-- about 0.001 m3 of ``TSR_LAYOUT_INTERSECTION``, small enough to read as noise
and real enough to z-fight -- or it stops a grid step short and leaves a slot.

That was found by building the corner-room version first and reading the four
errors it produced. It is a missing junction piece, not a missing partition, and
it is on the M3 list. Until then a room built entirely from interior pieces has
no such junction anywhere, which is what this file does.

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

#: The room, as a rectangle of whole modules. Three modules on the long side is
#: the minimum that can be entered: a corner consumes one module of each side it
#: turns, so a two-module side is all corner and has nowhere to put a door. That
#: is the consequence recorded in docs/decisions/0006, restated for partitions.
#: Placed so the corridor around it is wider than the perimeter plinth on every
#: side -- see the module docstring for why that clearance is not optional.
ROOM = dict(x0=2.0, y0=2.0, mods_x=3, mods_y=2)


def build(catalog):
    b = Builder(catalog, name="Room Inside a Building")

    x0, y0 = ROOM["x0"], ROOM["y0"]
    x1 = x0 + ROOM["mods_x"] * BAY                  # 14.0
    y1 = y0 + ROOM["mods_y"] * BAY                  # 10.0

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
    b.ground(A + "wall.straight.4m", 2 * BAY, 0.0, yaw=0.0, on=floors[(2, 0)])
    window = b.ground(A + "wall.window.4m", 3 * BAY, SPAN_Y, yaw=180.0,
                      on=floors[(2, 2)])
    b.ground(A + "wall.straight.4m", 2 * BAY, SPAN_Y, yaw=180.0, on=floors[(1, 2)])
    b.ground(A + "wall.straight.4m", 0.2, BAY, yaw=90.0, on=floors[(0, 1)])
    b.ground(A + "wall.straight.4m", SPAN_X - 0.2, 2 * BAY, yaw=270.0,
             on=floors[(3, 1)])

    b.mate(A + "door.leaf.1m2", "hinge", entrance, "jamb_neg_y")
    b.mate(A + "window.leaf.1m8", "mount", window, "jamb_neg_y")

    # The threshold. The floor is 0.50 m above the terrain outside, which is
    # twice what the reference character can step up -- proven, not assumed, by
    # the stoop's own usability check.
    b.place(A + "stair.stoop.1m2", (5.4, -0.60, 0.0), yaw=0.0)

    # ---------------------------------------------------------- the room
    # Four L corners turn the four corners of the room without overlapping, for
    # the same reason the perimeter uses them. Each corner consumes one module
    # of each side it turns:
    #
    #     south  x 2..6  (SW leg)   x 6..10  DOORWAY   x 10..14 (SE leg)
    #     north  x 2..6  (NW leg)   x 6..10  wall      x 10..14 (NE leg)
    #     west   y 2..6  (SW leg)   y 6..10  (NW leg)
    #     east   y 2..6  (SE leg)   y 6..10  (NE leg)
    #
    # The two-module sides are entirely corner, which is why the door has to go
    # in a three-module side. Every seam lands on a module boundary.
    b.ground(A + "wall.interior.corner.4m", x0, y0, yaw=0.0, on=slab(x0, y0))
    b.ground(A + "wall.interior.corner.4m", x1, y0, yaw=90.0, on=slab(x1 - 1, y0))
    b.ground(A + "wall.interior.corner.4m", x1, y1, yaw=180.0, on=slab(x1 - 1, y1 - 1))
    b.ground(A + "wall.interior.corner.4m", x0, y1, yaw=270.0, on=slab(x0, y1 - 1))

    # The one opening. Without it the five pieces above are a sealed box, which
    # is precisely the state this milestone existed to get out of.
    b.ground(A + "wall.interior.doorway.4m", x0 + BAY, y0, yaw=0.0,
             on=slab(x0 + BAY, y0))
    # ...and the module opposite it, closing the north side.
    b.ground(A + "wall.interior.4m", x1 - BAY, y1, yaw=180.0,
             on=slab(x1 - BAY - 1, y1 - 1))

    # No leaf is hung in the interior doorway. The front door has one because a
    # house is entered through a door that shuts; a shut leaf here would turn
    # the claim below into a statement about the leaf rather than about the
    # room, which is not what is being demonstrated.

    # ------------------------------------------------------------ fitting
    # Props here are pivoted at their centre, not at a corner, and the workbench
    # carries a 0.70 m working clearance on its -Y face. Both are in the
    # catalog; placing one 0.9 m from a wall because a wall is 4 m long is how
    # you get TSR_LAYOUT_BURIED from something that looked fine in plan.
    b.ground(A + "prop.workbench", 5.0, 9.0, yaw=0.0, on=slab(5.0, 9.0))
    b.ground(A + "prop.crate.small", 11.5, 8.5, yaw=12.0, on=slab(11.5, 8.5))
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
        "A 16 x 12 m shell with a free-standing 12 x 8 m room inside it: four "
        "interior corners and one interior wall close it, one interior doorway "
        "opens it, and a corridor runs all the way around. The room is the "
        "first thing in this kit that is both closed and enterable."
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
         "from": [8.0, 1.0, ground], "to": [8.0, 6.0, ground], "must": True},
        {"label": "back out of the room to the entrance",
         "from": [12.0, 8.0, ground], "to": [2.0, 1.0, ground], "must": True},
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
