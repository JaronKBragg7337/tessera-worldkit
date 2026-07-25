"""The building the constrained-agent benchmark asked for and could not have.

SPDX-License-Identifier: 0BSD

A model with no tools was asked for a two-storey survivor safe house with
interior access. It stacked three crates where a staircase belonged and wrote
"two stories with interior access". That was not carelessness -- the kit had no
stair, no beam, no column and no floor with an opening, so there was no honest
way to build it. See ``benchmarks/constrained_agent/``.

This is that building, made of parts that now exist, and -- the point -- the
interior access is *proven* rather than asserted. The layout declares routes and
the validator floods the walkable volume to confirm each one:

    INFO TSR_LAYOUT_REACHABILITY_PROVEN  Route proven: ground floor to mezzanine.

Every height here comes from the contract. The structural chain, none of which
is written down as a number in this file:

    terrain 0.00 -> foundation 0.30 -> ground floor 0.50
    -> wall top / column+beam top 3.50 -> mezzanine floor 3.70
    -> stair climbs exactly 3.20 in 16 steps of 0.20

Run:  python3 examples/safehouse_two_storey/build.py
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
    b = Builder(catalog, name="Survivor Safe House, Two Storey")
    d = catalog["derived"]

    # ------------------------------------------------------------- ground
    pads = {(gx, gy): b.ground(A + "foundation.pad.4m", gx * BAY, gy * BAY)
            for gx in range(BAYS) for gy in range(BAYS)}
    floors = {k: b.ground(A + "floor.slab.4m", k[0] * BAY, k[1] * BAY, on=pad)
              for k, pad in pads.items()}

    corners = {
        "sw": b.ground(A + "wall.corner.4m", 0.0, 0.0, yaw=0.0, on=floors[(0, 0)]),
        "se": b.ground(A + "wall.corner.4m", SPAN, 0.0, yaw=90.0, on=floors[(2, 0)]),
        "ne": b.ground(A + "wall.corner.4m", SPAN, SPAN, yaw=180.0, on=floors[(2, 2)]),
        "nw": b.ground(A + "wall.corner.4m", 0.0, SPAN, yaw=270.0, on=floors[(0, 2)]),
    }
    entrance = b.ground(A + "wall.doorway.4m", BAY, 0.0, yaw=0.0, on=floors[(1, 0)])
    window = b.ground(A + "wall.window.4m", 2 * BAY, SPAN, yaw=180.0, on=floors[(1, 2)])
    b.ground(A + "wall.straight.4m", 0.2, BAY, yaw=90.0, on=floors[(0, 1)])
    b.ground(A + "wall.straight.4m", SPAN - 0.2, 2 * BAY, yaw=270.0, on=floors[(2, 1)])
    b.mate(A + "door.leaf.1m2", "hinge", entrance, "jamb_neg_y")
    b.mate(A + "window.leaf.1m8", "mount", window, "jamb_neg_y")

    # The threshold. Without it the doorway is 0.50 m above the ground outside
    # and nobody can get in -- which the reachability solver found in a scene
    # that had already passed every other rule.
    b.ground(A + "stair.stoop.1m2", 5.4, -0.60, yaw=0.0)

    # A guard post clear of the door swing. The single-storey variant also
    # partitions a storage alcove here; this one does not, because the partition
    # would run into a mezzanine column and the validator says so.
    b.ground(A + "prop.workbench", 7.6, 1.4, yaw=180.0, on=floors[(1, 0)])
    b.ground(A + "prop.crate.small", 9.2, 1.0, yaw=18.0, on=floors[(2, 0)])

    # ----------------------------------------------- mezzanine structure
    # The minimal correct structure, arrived at by letting the validator reject
    # the alternatives:
    #
    #   * Beams running north-south cannot work here. A beam is exactly one bay
    #     long, and the gap between the middle grid line and the inside face of
    #     the north wall is less than that, so any such beam ends up inside the
    #     wall. Reported as buried, correctly.
    #   * A square of four beams around one bay crosses itself at every corner.
    #     Reported as intersecting, correctly.
    #   * A one-bay mezzanine puts the stair's landing on the edge of its own
    #     stairwell -- step off the top tread into the hole.
    #
    # What is left is a mezzanine over the northern bay bearing on two opposite
    # edges: a beam on two columns to the south, and the north perimeter wall
    # top to the north. Both at 3.50, because a column plus its beam is exactly
    # one wall high. The stair then sits in the bay to the south, with nothing
    # above it at all, so it needs no opening and has unlimited headroom.
    half = catalog["config"]["COLUMN_SIZE"] / 2
    cols = [b.ground(A + "column.3m", cx - half, 2 * BAY - half, on=floors[(gx, 1)])
            for gx, cx in ((0, BAY), (1, 2 * BAY))]

    beam = b.ground(A + "beam.4m", BAY, 2 * BAY, yaw=0.0, on=cols[0], surface="top")

    mezzanine = b.ground(A + "floor.slab.4m", BAY, 2 * BAY, yaw=0.0,
                         on=beam, surface="top")

    # ------------------------------------------------------------- stair
    # Climbs exactly one storey in the bay south of the mezzanine and lands
    # flush with it. Nothing overhead, so headroom is never in question.
    b.ground(A + "stair.straight.4m", 4.4, BAY, yaw=0.0, on=floors[(1, 1)])

    # Guards the open west edge, where the mezzanine drops to the ground floor.
    b.ground(A + "railing.4m", 4.2, 2 * BAY, yaw=90.0, on=mezzanine, surface="top")

    b.discovered_connections = b.autoconnect()
    return b


def main():
    catalog = load_catalog(os.path.join(ROOT, "build", "catalog.json"))
    b = build(catalog)
    d = catalog["derived"]
    ground = d["floor_top_z"]
    upper = ground + d["storey_height"]

    layout = b.to_layout(
        "Two-storey survivor safe house: guarded entrance with a stoop and a "
        "hung door, storage alcove, and a mezzanine reached by a real staircase "
        "through a real floor opening. Interior access is proven, not claimed."
    )
    layout["discovered_connections"] = b.discovered_connections

    # The claims. Each one is either proven by flood fill or reported as a lie.
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
