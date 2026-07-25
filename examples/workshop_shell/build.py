"""Assemble the Workshop Shell entirely from catalog metadata.

SPDX-License-Identifier: 0BSD

Read this file for the claim the repository makes. The only hard-coded height in
it is the terrain at zero. Every other Z, and every transform that joins two
pieces, is solved from the placement contract by ``tessera.assemble.Builder``.
Every seam is then *discovered* by ``autoconnect`` rather than hand-listed, so
the layout records what actually mated rather than what the author hoped mated.

No render. No screenshot. No trial and error.

Run:  python examples/workshop_shell/build.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))

from tessera.assemble import Builder  # noqa: E402
from tessera.catalog import load_catalog  # noqa: E402

A = "tsr:shell/"
BAY = 4.0
BAYS = 3                     # 3 x 3 bays -> a 12 x 12 m building
SPAN = BAY * BAYS


def build(catalog):
    b = Builder(catalog, name="Workshop Shell")

    # ------------------------------------------------------ 1 ground plane
    pads = {}
    for gx in range(BAYS):
        for gy in range(BAYS):
            pads[(gx, gy)] = b.ground(A + "foundation.pad.4m", gx * BAY, gy * BAY)

    # --------------------------------------------------- 2 floor on the pads
    floors = {key: b.ground(A + "floor.slab.4m", key[0] * BAY, key[1] * BAY, on=pad)
              for key, pad in pads.items()}

    # ------------------------------------------------------- 3 perimeter
    # Four L corners close eight of the twelve bay edges. The corner is an L
    # rather than a post precisely so a rectangular perimeter closes with zero
    # overlapping geometry -- see docs/decisions/0006-corner-piece-is-an-L.md.
    corners = {
        "sw": b.ground(A + "wall.corner.4m", 0.0, 0.0, yaw=0.0, on=floors[(0, 0)]),
        "se": b.ground(A + "wall.corner.4m", SPAN, 0.0, yaw=90.0, on=floors[(2, 0)]),
        "ne": b.ground(A + "wall.corner.4m", SPAN, SPAN, yaw=180.0, on=floors[(2, 2)]),
        "nw": b.ground(A + "wall.corner.4m", 0.0, SPAN, yaw=270.0, on=floors[(0, 2)]),
    }

    # the four middle segments
    doorway = b.ground(A + "wall.doorway.4m", BAY, 0.0, yaw=0.0, on=floors[(1, 0)])
    window = b.ground(A + "wall.window.4m", 2 * BAY, SPAN, yaw=180.0, on=floors[(1, 2)])
    b.ground(A + "wall.straight.4m", 0.2, BAY, yaw=90.0, on=floors[(0, 1)])
    b.ground(A + "wall.straight.4m", SPAN - 0.2, 2 * BAY, yaw=270.0, on=floors[(2, 1)])

    # ------------------------------------------------- 4 leaves in the holes
    b.mate(A + "door.leaf.1m2", "hinge", doorway, "jamb_neg_y")
    b.mate(A + "window.leaf.1m8", "mount", window, "jamb_neg_y")

    # -------------------------------------------------------------- 5 roof
    # A single gable: three panels per slope, meeting at y = ROOF_RUN.
    south = [b.ground(A + "roof.panel.4m", i * BAY, 0.0, yaw=0.0,
                      on=corners["sw"] if i == 0 else doorway,
                      surface="top_x" if i == 0 else "top")
             for i in range(BAYS)]
    north = [b.ground(A + "roof.panel.4m", (i + 1) * BAY, SPAN, yaw=180.0,
                      on=window if i == 1 else corners["ne"],
                      surface="top" if i == 1 else "top_x")
             for i in range(BAYS)]
    for panel in south:
        b.mate(A + "roof.ridge.4m", "seat", panel, "ridge_cap")

    # --------------------------------------------------------------- 6 props
    b.ground(A + "prop.workbench", 9.4, 9.1, yaw=180.0, on=floors[(2, 2)])
    b.ground(A + "prop.crate.small", 1.4, 9.6, yaw=12.0, on=floors[(0, 2)])
    crate = b.ground(A + "prop.crate.small", 2.15, 9.55, yaw=-8.0, on=floors[(0, 2)])
    b.ground(A + "prop.crate.small", 2.15, 9.55, yaw=37.0, on=crate, surface="top")

    # ------------------------------------------------ 7 discover every seam
    b.discovered_connections = b.autoconnect()
    return b


def main():
    catalog = load_catalog(os.path.join(ROOT, "build", "catalog.json"))
    b = build(catalog)
    layout = b.to_layout(
        "A sealed 12 x 12 m workshop shell: nine foundation pads, nine floor "
        "slabs, four L corners, a walkable doorway, a glazed window, two plain "
        "walls, a six-panel gable roof with ridge caps, and interior props. "
        "Every transform solved from the placement contract."
    )
    layout["discovered_connections"] = b.discovered_connections
    out = os.path.join(HERE, "layout.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(layout, fh, indent=2)
    print("wrote %s" % out)
    print("  instances                %d" % layout["instance_count"])
    print("  solved from the contract %d" % layout["placement_method"]["solved_from_contract"])
    print("  placed by hand           %d" % layout["placement_method"]["explicit"])
    print("  seams discovered         %d" % b.discovered_connections)
    return layout


if __name__ == "__main__":
    main()
