"""Assemble a two-story survivor safe house from catalog metadata.
SPDX-License-Identifier: 0BSD

Features:
- Two stories with interior access
- One guarded entrance at ground level
- Storage room on ground floor
- Clear spawn area at center of ground floor
- Guard post at entrance
- Living quarters on second floor
"""
from __future__ import annotations
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tessera.assemble import Builder
from tessera.catalog import load_catalog

A = "tsr:shell/"
BAY = 4.0
BAYS = 3  # 3 x 3 bays -> 12 x 12 m footprint
SPAN = BAY * BAYS


def build(catalog):
    b = Builder(catalog, name="Survivor Safe House")

    pads = {}
    for gx in range(BAYS):
        for gy in range(BAYS):
            pads[(gx, gy)] = b.ground(A + "foundation.pad.4m", gx * BAY, gy * BAY)

    floors = {
        key: b.ground(A + "floor.slab.4m", key[0] * BAY, key[1] * BAY, on=pad)
        for key, pad in pads.items()
    }

    corners = {
        "sw": b.ground(A + "wall.corner.4m", 0.0, 0.0, yaw=0.0, on=floors[(0, 0)]),
        "se": b.ground(A + "wall.corner.4m", SPAN, 0.0, yaw=90.0, on=floors[(2, 0)]),
        "ne": b.ground(A + "wall.corner.4m", SPAN, SPAN, yaw=180.0, on=floors[(2, 2)]),
        "nw": b.ground(A + "wall.corner.4m", 0.0, SPAN, yaw=270.0, on=floors[(0, 2)]),
    }

    entrance = b.ground(A + "wall.doorway.4m", BAY, 0.0, yaw=0.0, on=floors[(1, 0)])
    b.ground(A + "wall.straight.4m", SPAN, BAY, yaw=90.0, on=floors[(2, 1)])
    window_north = b.ground(A + "wall.window.4m", BAY, SPAN, yaw=180.0, on=floors[(1, 2)])
    b.ground(A + "wall.straight.4m", 0.0, BAY, yaw=270.0, on=floors[(0, 1)])

    b.mate(A + "door.leaf.1m2", "hinge", entrance, "jamb_neg_y")

    guard_post = b.ground(
        A + "prop.workbench", BAY + 0.5, 1.2, yaw=180.0, on=floors[(1, 0)],
    )

    storage_wall_1 = b.ground(
        A + "wall.straight.4m", SPAN, BAY, yaw=90.0, on=floors[(2, 1)],
    )
    storage_doorway = b.ground(
        A + "wall.doorway.4m", SPAN - 0.5, BAY + 0.5, yaw=0.0, on=floors[(2, 1)],
    )

    spawn_area_center = (BAY, BAY)
    b.ground(A + "prop.crate.small", BAY - 0.8, BAY - 0.8, yaw=0.0, on=floors[(1, 1)])
    b.ground(A + "prop.crate.small", BAY + 0.8, BAY - 0.8, yaw=45.0, on=floors[(1, 1)])
    b.ground(A + "prop.crate.small", BAY - 0.8, BAY + 0.8, yaw=90.0, on=floors[(1, 1)])
    b.ground(A + "prop.crate.small", BAY + 0.8, BAY + 0.8, yaw=135.0, on=floors[(1, 1)])

    stair_base = b.ground(A + "prop.crate.small", 0.8, SPAN - 0.8, yaw=0.0, on=floors[(0, 2)])
    stair_mid = b.ground(A + "prop.crate.small", 0.8, SPAN - 0.8, yaw=0.0, on=stair_base, surface="top")
    stair_top = b.ground(A + "prop.crate.small", 0.8, SPAN - 0.8, yaw=0.0, on=stair_mid, surface="top")

    second_floor_slabs = {}
    second_floor_slabs[(1, 0)] = b.ground(
        A + "floor.slab.4m", BAY, 0.0, on=entrance, surface="top",
    )
    second_floor_slabs[(2, 1)] = b.ground(
        A + "floor.slab.4m", SPAN, BAY, on=storage_wall_1, surface="top",
    )
    second_floor_slabs[(1, 2)] = b.ground(
        A + "floor.slab.4m", BAY, SPAN, on=window_north, surface="top",
    )
    west_wall = b.ground(
        A + "wall.straight.4m", 0.0, BAY, yaw=270.0, on=floors[(0, 1)],
    )
    second_floor_slabs[(0, 1)] = b.ground(
        A + "floor.slab.4m", 0.0, BAY, on=west_wall, surface="top",
    )

    second_corners = {
        "sw": b.ground(A + "wall.corner.4m", 0.0, 0.0, yaw=0.0,
                       on=second_floor_slabs.get((0, 0), floors[(0, 0)])),
        "se": b.ground(A + "wall.corner.4m", SPAN, 0.0, yaw=90.0,
                       on=second_floor_slabs.get((2, 0), floors[(2, 0)])),
        "ne": b.ground(A + "wall.corner.4m", SPAN, SPAN, yaw=180.0,
                       on=second_floor_slabs.get((2, 2), floors[(2, 2)])),
        "nw": b.ground(A + "wall.corner.4m", 0.0, SPAN, yaw=270.0,
                       on=second_floor_slabs.get((0, 2), floors[(0, 2)])),
    }

    b.ground(A + "wall.straight.4m", BAY, 0.0, yaw=0.0,
             on=second_floor_slabs.get((1, 0), floors[(1, 0)]))
    b.ground(A + "wall.straight.4m", SPAN, BAY, yaw=90.0,
             on=second_floor_slabs.get((2, 1), floors[(2, 1)]))
    b.ground(A + "wall.straight.4m", BAY, SPAN, yaw=180.0,
             on=second_floor_slabs.get((1, 2), floors[(1, 2)]))
    b.ground(A + "wall.straight.4m", 0.0, BAY, yaw=270.0,
             on=second_floor_slabs.get((0, 1), floors[(0, 1)]))

    second_window = b.ground(
        A + "wall.window.4m", BAY * 2, SPAN, yaw=180.0,
        on=second_floor_slabs.get((1, 2), floors[(1, 2)]),
    )
    b.mate(A + "window.leaf.1m8", "mount", second_window, "jamb_neg_y")

    south_roof = [
        b.ground(A + "roof.panel.4m", i * BAY, 0.0, yaw=0.0,
                 on=second_corners["sw"] if i == 0 else second_floor_slabs.get((1, 0), floors[(1, 0)]),
                 surface="top_x" if i == 0 else "top")
        for i in range(BAYS)
    ]
    north_roof = [
        b.ground(A + "roof.panel.4m", (i + 1) * BAY, SPAN, yaw=180.0,
                 on=second_corners["ne"] if i == 1 else second_corners["nw"],
                 surface="top" if i == 1 else "top_x")
        for i in range(BAYS)
    ]

    for panel in south_roof:
        b.mate(A + "roof.ridge.4m", "seat", panel, "ridge_cap")

    b.ground(A + "prop.workbench", BAY + 1.0, BAY + 1.0, yaw=0.0,
             on=second_floor_slabs.get((1, 1), floors[(1, 1)]))
    b.ground(A + "prop.crate.small", BAY + 1.5, BAY + 1.8, yaw=30.0,
             on=second_floor_slabs.get((1, 1), floors[(1, 1)]))

    b.discovered_connections = b.autoconnect()
    return b


def main():
    catalog = load_catalog(os.path.join(ROOT, "build", "catalog.json"))
    b = build(catalog)
    layout = b.to_layout(
        "Two-story survivor safe house: guarded entrance at south wall, "
        "storage room in southeast corner, clear spawn area at center, "
        "living quarters on second floor."
    )
    layout["discovered_connections"] = b.discovered_connections
    out = os.path.join(HERE, "layout.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(layout, fh, indent=2)
    print("wrote %s" % out)
    print(" instances %d" % layout["instance_count"])
    print(" seams discovered %d" % b.discovered_connections)


if __name__ == "__main__":
    main()
