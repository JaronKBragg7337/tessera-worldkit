"""Survivor safe house — the repaired constrained-agent benchmark layout.

SPDX-License-Identifier: 0BSD

This started as a script written by DeepSeek from a phone chat, with no
checkout, no Python, no engine and no ability to run anything. The original is
preserved verbatim at ``benchmarks/constrained_agent/deepseek_safehouse_v1.py``.
This file is the repaired version, and the repair log is in
``benchmarks/constrained_agent/README.md``.

Two of the four requested features are built and validated here. The other two
are *not*, and saying so is the point of the exercise:

* built    — one guarded entrance, with a working door leaf
* built    — a storage alcove partitioned off the south-east bay
* built    — a clear spawn area at the centre
* NOT BUILT — "two storeys with interior access". shell_v1 has no stair, no
  ladder, no beam and no floor piece with an opening, so a second storey can
  only be supported around a bay perimeter and cannot be reached from inside.
  Faking it with stacked crates, as the original did, produces geometry the
  validator accepts and a player cannot climb. It waits for ROADMAP M3.
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
BAYS = 3
SPAN = BAY * BAYS


def build(catalog):
    b = Builder(catalog, name="Survivor Safe House")

    # ------------------------------------------------------------- ground
    pads = {(gx, gy): b.ground(A + "foundation.pad.4m", gx * BAY, gy * BAY)
            for gx in range(BAYS) for gy in range(BAYS)}
    floors = {k: b.ground(A + "floor.slab.4m", k[0] * BAY, k[1] * BAY, on=pad)
              for k, pad in pads.items()}

    # ---------------------------------------------------------- perimeter
    corners = {
        "sw": b.ground(A + "wall.corner.4m", 0.0, 0.0, yaw=0.0, on=floors[(0, 0)]),
        "se": b.ground(A + "wall.corner.4m", SPAN, 0.0, yaw=90.0, on=floors[(2, 0)]),
        "ne": b.ground(A + "wall.corner.4m", SPAN, SPAN, yaw=180.0, on=floors[(2, 2)]),
        "nw": b.ground(A + "wall.corner.4m", 0.0, SPAN, yaw=270.0, on=floors[(0, 2)]),
    }

    # the one guarded entrance, in the south wall
    entrance = b.ground(A + "wall.doorway.4m", BAY, 0.0, yaw=0.0, on=floors[(1, 0)])
    window = b.ground(A + "wall.window.4m", 2 * BAY, SPAN, yaw=180.0, on=floors[(1, 2)])
    b.ground(A + "wall.straight.4m", 0.2, BAY, yaw=90.0, on=floors[(0, 1)])
    b.ground(A + "wall.straight.4m", SPAN - 0.2, 2 * BAY, yaw=270.0, on=floors[(2, 1)])

    b.mate(A + "door.leaf.1m2", "hinge", entrance, "jamb_neg_y")
    b.mate(A + "window.leaf.1m8", "mount", window, "jamb_neg_y")

    # ------------------------------------------------------ storage alcove
    # A single partition across the north edge of the south-east bay. It stops
    # 0.2 m short of the east wall rather than running to it: the original ran a
    # partition into the perimeter and the validator reported 1.7572 m3 of
    # shared volume, which is one entire wall -- an exact duplicate.
    #
    # Deliberately an alcove, open to the west, rather than a sealed room. The
    # L corner piece exists so a rectangular *perimeter* closes without overlap;
    # it carries no opening, so using two of them to box in an interior room
    # would produce a room with no way in. A door needs the interior-corner
    # pieces scheduled for M3.
    b.ground(A + "wall.straight.4m", SPAN - 0.4, BAY, yaw=180.0, on=floors[(2, 0)])

    # ---------------------------------------------------------- guard post
    # Inside the entrance and clear of the door swing. The original put it at
    # x = BAY + 0.5, inside the swing volume, which raised a clearance warning.
    b.ground(A + "prop.workbench", 7.6, 1.4, yaw=180.0, on=floors[(1, 0)])
    b.ground(A + "prop.crate.small", 9.2, 1.0, yaw=18.0, on=floors[(2, 0)])
    b.ground(A + "prop.crate.small", 10.4, 1.2, yaw=-24.0, on=floors[(2, 0)])

    # ------------------------------------------------------- spawn area
    # Bay (1,1) is left completely empty. The original ringed it with four
    # crates to "mark" it, one of which clashed with a workbench. Until the M4
    # intent layer can test a character capsule against occupancy, an empty bay
    # is an honest spawn area and a decorated one is a guess.

    # ---------------------------------------------------------------- roof
    south = [b.ground(A + "roof.panel.4m", i * BAY, 0.0, yaw=0.0,
                      on=corners["sw"] if i == 0 else entrance,
                      surface="top_x" if i == 0 else "top")
             for i in range(BAYS)]
    for i in range(BAYS):
        b.ground(A + "roof.panel.4m", (i + 1) * BAY, SPAN, yaw=180.0,
                 on=window if i == 1 else corners["ne"],
                 surface="top" if i == 1 else "top_x")
    for panel in south:
        b.mate(A + "roof.ridge.4m", "seat", panel, "ridge_cap")

    b.discovered_connections = b.autoconnect()
    return b


def main():
    catalog = load_catalog(os.path.join(ROOT, "build", "catalog.json"))
    b = build(catalog)
    layout = b.to_layout(
        "Single-storey survivor safe house: one guarded entrance with a hung "
        "door, a storage alcove in the south-east bay, an empty central spawn "
        "bay, and a gable roof. Repaired from a constrained-agent draft."
    )
    layout["discovered_connections"] = b.discovered_connections
    out = os.path.join(HERE, "layout.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(layout, fh, indent=2)
    print("wrote %s" % out)
    print("  instances                %d" % layout["instance_count"])
    print("  solved from the contract %d" % layout["placement_method"]["solved_from_contract"])
    print("  seams discovered         %d" % b.discovered_connections)
    return layout


if __name__ == "__main__":
    main()
