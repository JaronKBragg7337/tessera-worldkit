"""Deliberately broken layouts, each paired with the code it must produce.

SPDX-License-Identifier: 0BSD

A validator that has never been shown a failure is a validator nobody has
tested. Each entry here perturbs the known-good Workshop Shell in exactly one
way and names the diagnostic that must fire. If a rule stops working, the test
that consumes this file fails.
"""
from __future__ import annotations

import copy


def _find(layout, prefix):
    for inst in layout["instances"]:
        if inst["asset"].endswith(prefix):
            return inst
    raise KeyError(prefix)


def _strip_links(inst):
    inst.pop("connections", None)
    return inst


def floating(layout):
    """A wall lifted off the floor by 37 cm."""
    out = copy.deepcopy(layout)
    _strip_links(_find(out, "wall.straight.4m"))["position"][2] += 0.37
    return out


def buried(layout):
    """A wall sunk 12 cm into the floor."""
    out = copy.deepcopy(layout)
    _strip_links(_find(out, "wall.doorway.4m"))["position"][2] -= 0.12
    return out


def unsupported(layout):
    """A crate hovering in the middle of nothing."""
    out = copy.deepcopy(layout)
    inst = _strip_links(_find(out, "prop.workbench"))
    inst["position"] = [40.0, 40.0, 2.0]
    return out


def intersection(layout):
    """A crate shoved into the middle of the workbench.

    Chosen over moving a wall so the case isolates one rule: the crate is still
    correctly grounded on the floor, so nothing but the clash check should fire.
    """
    out = copy.deepcopy(layout)
    bench = _find(out, "prop.workbench")
    crate = _strip_links(_find(out, "prop.crate.small"))
    crate["position"] = list(bench["position"])
    crate["rotation_degrees"] = [0.0, 0.0, 0.0]
    return out


def off_grid(layout):
    """A wall nudged 7 cm off the translation lattice."""
    out = copy.deepcopy(layout)
    _strip_links(_find(out, "wall.window.4m"))["position"][0] += 0.07
    return out


def illegal_rotation(layout):
    """A modular wall spun to 45 degrees."""
    out = copy.deepcopy(layout)
    _strip_links(_find(out, "wall.straight.4m"))["rotation_degrees"][0] = 45.0
    return out


def illegal_scale(layout):
    """A modular wall scaled 1.7x."""
    out = copy.deepcopy(layout)
    _strip_links(_find(out, "wall.straight.4m"))["scale"] = 1.7
    return out


def connector_direction(layout):
    """A mated wall flipped 180 degrees: still touching, now facing the wrong way."""
    out = copy.deepcopy(layout)
    inst = _find(out, "wall.doorway.4m")
    inst["rotation_degrees"][0] = (inst["rotation_degrees"][0] + 180.0) % 360.0
    return out


def connector_gap(layout):
    """A declared seam pulled 4 cm apart -- a visible crack."""
    out = copy.deepcopy(layout)
    for inst in out["instances"]:
        if inst.get("connections") and inst["asset"].endswith("roof.ridge.4m"):
            inst["position"][0] += 0.04
            return out
    raise AssertionError("no connected ridge cap in the layout")


def aperture_blocked(layout):
    """A crate parked in the doorway."""
    out = copy.deepcopy(layout)
    wall = _find(out, "wall.doorway.4m")
    crate = _strip_links(_find(out, "prop.crate.small"))
    crate["position"] = [wall["position"][0] + 2.0, wall["position"][1] + 0.1, 0.5]
    crate["rotation_degrees"] = [0.0, 0.0, 0.0]
    return out


def unknown_asset(layout):
    """A reference to something that is not in the catalog."""
    out = copy.deepcopy(layout)
    out["instances"][0]["asset"] = "tsr:shell/wall.imaginary.4m"
    return out


def duplicate_instance(layout):
    """Two instances sharing an id."""
    out = copy.deepcopy(layout)
    out["instances"][1]["id"] = out["instances"][0]["id"]
    return out


def bad_schema(layout):
    out = copy.deepcopy(layout)
    out["schema"] = "someone.elses.format/9"
    return out


def unknown_connector(layout):
    out = copy.deepcopy(layout)
    for inst in out["instances"]:
        if inst.get("connections"):
            inst["connections"][0]["from"] = "not_a_connector"
            return out
    raise AssertionError("no connections in the layout")


def pitched_over(layout):
    """A wall tipped 20 degrees off the ground plane."""
    out = copy.deepcopy(layout)
    _strip_links(_find(out, "wall.straight.4m"))["rotation_degrees"][1] = 20.0
    return out


#: case name -> (builder, the code that must appear)
CASES = {
    "floating": (floating, "TSR_LAYOUT_FLOATING"),
    "buried": (buried, "TSR_LAYOUT_BURIED"),
    "unsupported": (unsupported, "TSR_LAYOUT_UNSUPPORTED"),
    "intersection": (intersection, "TSR_LAYOUT_INTERSECTION"),
    "off_grid": (off_grid, "TSR_LAYOUT_OFF_GRID"),
    "illegal_rotation": (illegal_rotation, "TSR_LAYOUT_ILLEGAL_ROTATION"),
    "illegal_scale": (illegal_scale, "TSR_LAYOUT_ILLEGAL_SCALE"),
    "connector_direction": (connector_direction, "TSR_LAYOUT_CONNECTOR_DIRECTION"),
    "connector_gap": (connector_gap, "TSR_LAYOUT_CONNECTOR_GAP"),
    "aperture_blocked": (aperture_blocked, "TSR_LAYOUT_APERTURE_BLOCKED"),
    "unknown_asset": (unknown_asset, "TSR_LAYOUT_UNKNOWN_ASSET"),
    "duplicate_instance": (duplicate_instance, "TSR_LAYOUT_DUPLICATE_INSTANCE"),
    "bad_schema": (bad_schema, "TSR_LAYOUT_SCHEMA_MISMATCH"),
    "unknown_connector": (unknown_connector, "TSR_LAYOUT_UNKNOWN_CONNECTOR"),
    "pitched_over": (pitched_over, "TSR_LAYOUT_ILLEGAL_ROTATION"),
}


#: catalog mutations, each paired with the asset-rule code it must trigger
def asset_not_watertight(asset):
    asset["geometry"]["watertight"] = False
    asset["geometry"]["boundary_edges"] = 6
    return asset


def asset_inverted(asset):
    asset["geometry"]["outward_winding"] = False
    return asset


def asset_pivot_off_base(asset):
    asset["pivot"]["base_offset_z"] = 0.2
    return asset


def asset_collision_seals_aperture(asset):
    ap = asset["apertures"][0]["bounds"]
    asset["collision"]["hulls"].append([
        ap["min"][0] + 0.1, ap["min"][1], ap["min"][2] + 0.1,
        ap["max"][0] - 0.1, ap["max"][1], ap["max"][2] - 0.1,
    ])
    return asset


def asset_missing_collision(asset):
    asset["collision"]["hulls"] = []
    return asset


def asset_bad_units(asset):
    asset["space"]["linear_unit"] = "centimetre"
    return asset


def asset_missing_provenance(asset):
    asset["provenance"]["authored_by"] = ""
    return asset


def asset_missing_license(asset):
    asset["license"]["assets_spdx"] = ""
    return asset


def asset_connector_not_unit(asset):
    asset["connectors"][0]["normal"] = [0.0, 0.0, 2.0]
    return asset


def asset_connector_skewed(asset):
    asset["connectors"][0]["normal"] = [0.0, 0.0, 1.0]
    asset["connectors"][0]["tangent"] = [0.0, 0.0, 1.0]
    return asset


def asset_aperture_too_small(asset):
    asset["apertures"][0]["fits_capsule"]["admits_reference_character"] = False
    return asset


def asset_unknown_kind(asset):
    asset["connectors"][0]["kind"] = "wormhole"
    return asset


ASSET_CASES = {
    "not_watertight": (asset_not_watertight, "TSR_ASSET_NOT_WATERTIGHT", None),
    "inverted_winding": (asset_inverted, "TSR_ASSET_INVERTED_WINDING", None),
    "pivot_off_base": (asset_pivot_off_base, "TSR_ASSET_PIVOT_OFF_BASE", "wall.straight.4m"),
    "collision_seals_aperture": (asset_collision_seals_aperture,
                                 "TSR_ASSET_COLLISION_SEALS_APERTURE", "wall.doorway.4m"),
    "missing_collision": (asset_missing_collision, "TSR_ASSET_MISSING_COLLISION", None),
    "bad_units": (asset_bad_units, "TSR_ASSET_UNIT_MISMATCH", None),
    "missing_provenance": (asset_missing_provenance, "TSR_ASSET_MISSING_PROVENANCE", None),
    "missing_license": (asset_missing_license, "TSR_ASSET_MISSING_LICENSE", None),
    "connector_not_unit": (asset_connector_not_unit,
                           "TSR_ASSET_CONNECTOR_NORMAL_NOT_UNIT", None),
    "connector_skewed": (asset_connector_skewed, "TSR_ASSET_CONNECTOR_FRAME_SKEWED", None),
    "aperture_too_small": (asset_aperture_too_small,
                           "TSR_ASSET_APERTURE_TOO_SMALL", "wall.doorway.4m"),
    "unknown_connector_kind": (asset_unknown_kind,
                               "TSR_ASSET_UNKNOWN_CONNECTOR_KIND", None),
}
