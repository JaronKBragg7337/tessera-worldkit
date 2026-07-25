"""A context-budgeted digest of a catalog.

SPDX-License-Identifier: 0BSD

The full catalog is around 33,000 tokens for twelve assets, and it grows
linearly. That is fine for a desktop agent with a filesystem and unusable for an
assistant running inside a phone app, where the whole conversation may have less
budget than one kit.

But most of that weight is not needed to *place* anything. Occupancy boxes,
collision hulls, provenance, licence, material and LOD tables, engine import
settings and mesh statistics all matter to a builder or an importer and matter
not at all to something deciding where a wall goes. Stripping them, hoisting the
parts that are identical across every asset (space, tolerances, the
compatibility table) into a header, and packing connectors into positional
arrays gets the same placement power into roughly a twentieth of the budget.

The claim that this is *sufficient* is not an opinion. :func:`expand` turns a
brief back into the minimal catalog shape the placement solver consumes, and a
test assembles the entire Workshop Shell from a brief alone and validates the
result against the full catalog. If the digest ever drops something placement
needs, that test fails.

Everything omitted is recoverable: the brief carries the catalog's fingerprint
and path, so a consumer that later needs collision hulls knows exactly which
catalog to ask for and can prove it is the right one.
"""
from __future__ import annotations

import json

from .contract import CONNECTOR_COMPATIBILITY, MatingTolerance

BRIEF_SCHEMA = "tessera.brief/1"

#: Connectors are packed positionally. Spelling the key names out twelve times
#: per asset costs more than the values do.
CONNECTOR_FIELDS = ["id", "kind", "mode", "pos", "normal", "tangent",
                    "extent", "tolerance_override"]

APERTURE_FIELDS = ["id", "kind", "axis", "clear_w", "clear_h", "traversable",
                   "admits_character"]

DEFAULT_TOLERANCE = MatingTolerance()


def _short(asset_id: str) -> str:
    return asset_id.split("/")[-1]


def _round(values, places=4):
    return [round(float(v), places) + 0.0 for v in values]


def _connector(c) -> list:
    tol = c.get("tolerance") or {}
    override = None
    if (abs(tol.get("position_metres", DEFAULT_TOLERANCE.position_metres)
            - DEFAULT_TOLERANCE.position_metres) > 1e-12
            or abs(tol.get("angle_degrees", DEFAULT_TOLERANCE.angle_degrees)
                   - DEFAULT_TOLERANCE.angle_degrees) > 1e-12
            or abs(tol.get("roll_degrees", DEFAULT_TOLERANCE.roll_degrees)
                   - DEFAULT_TOLERANCE.roll_degrees) > 1e-12):
        override = [tol.get("position_metres"), tol.get("angle_degrees"),
                    tol.get("roll_degrees")]
    return [
        c["id"],
        c["kind"],
        "s" if c.get("mating_mode") == "surface" else "p",
        _round(c["position"]),
        _round(c["normal"], 6),
        _round(c["tangent"], 6),
        _round(c["extent_half"], 4) if c.get("extent_half") else None,
        override,
    ]


def _aperture(a) -> list:
    return [
        a["id"], a["kind"], a["traversal_axis"],
        round(a["clear_width"], 4), round(a["clear_height"], 4),
        bool(a["traversable"]),
        bool(a.get("fits_capsule", {}).get("admits_reference_character", False)),
    ]


def build_brief(catalog, include_notes=False) -> dict:
    """Compress a catalog to what an agent needs in order to place things."""
    assets = []
    for a in catalog["assets"]:
        place = a["placement"]
        support = place.get("support", {}) or {}
        scaling = place.get("allowed_scaling", {}) or {}

        entry = {
            "id": _short(a["id"]),
            "role": a["semantic_role"],
            "size": _round(a["dimensions"]["size"], 4),
            # The number that stops things floating. Kept even when zero,
            # because an absent field invites an assumption.
            "base": round(a["pivot"]["base_offset_z"], 6),
            "grid": place["grid"]["policy"],
            "yaw": place["allowed_rotations"],
            "scale": [scaling.get("min", 1.0), scaling.get("max", 1.0)],
            "c": [_connector(c) for c in a["connectors"]],
        }
        if support.get("requires_support"):
            entry["on"] = support.get("rests_on", [])
            if support.get("may_float"):
                entry["carried_by_connection"] = True
            if support.get("datum_connector"):
                entry["datum"] = support["datum_connector"]
        if a["apertures"]:
            entry["ap"] = [_aperture(x) for x in a["apertures"]]
        if a["clearance"]["boxes"]:
            entry["clear"] = [_round(b) for b in a["clearance"]["boxes"]]
        if include_notes and a.get("notes"):
            entry["note"] = a["notes"]
        assets.append(entry)

    return {
        "schema": BRIEF_SCHEMA,
        "kit": "%s@%s" % (catalog["kit"]["id"], catalog["kit"]["version"]),
        # Asset ids are shortened per entry to save budget; this restores them.
        # The namespace is not always the kit id, so it is carried rather than
        # reconstructed -- guessing it would silently produce ids that resolve
        # against nothing.
        "id_prefix": catalog["assets"][0]["id"].rsplit("/", 1)[0] + "/",
        "fingerprint": catalog["fingerprint"],
        "contract_version": catalog["contract_version"],
        "full_catalog": "build/catalog.json",

        "how_to_place": [
            "Space is right-handed, Z up, +Y forward, metres.",
            "rotation is [yaw about Z, pitch about Y, roll about X] in degrees, ZYX-intrinsic.",
            "To ground an asset: world_z = supporting_surface_z + asset.base",
            "If an asset has 'datum', ground that connector's plane instead of the asset's lowest point.",
            "Two connectors mate when: kinds are in 'mates', points coincide within tolerance,"
            " normals are opposed, and tangents are aligned.",
            "grid=module means snap x and y to grid.xy and z to grid.z; module_xy means x and y only;"
            " mated and free are not position-constrained.",
            "yaw=null means any rotation is allowed. Never pitch or roll a modular piece.",
            "A character can step up 'character.step_up' in one go and no more. A floor"
            " higher than that above the ground outside needs a stoop, or the doorway is"
            " unreachable however wide it is.",
            "Declare routes in layout.reachability and the validator will prove or refute"
            " them: [{'label':..,'from':[x,y,z],'to':[x,y,z],'must':true}].",
            "Send the finished layout to `tessera validate --layout` and apply every fix_transform.",
        ],

        "grid": {
            "module": catalog["config"]["MODULE"],
            "xy": catalog["config"]["GRID_XY"],
            "z": catalog["config"]["GRID_Z"],
        },
        "stack": {
            "terrain": 0.0,
            "foundation_top": catalog["derived"]["foundation_top_z"],
            "floor_top": catalog["derived"]["floor_top_z"],
            "wall_top": catalog["derived"]["wall_top_z"],
            "second_floor_top": catalog["derived"]["second_floor_top_z"],
            "ridge": catalog["derived"]["ridge_z"],
        },
        "storey": {
            "height": catalog["derived"]["storey_height"],
            "stair_steps": catalog["derived"]["stair_steps"],
            "stair_run": catalog["derived"]["stair_run"],
            "stair_angle_degrees": catalog["derived"]["stair_angle_degrees"],
        },
        "character": {
            "radius": catalog["config"]["CHARACTER_RADIUS"],
            "height": catalog["config"]["CHARACTER_HEIGHT"],
            "step_up": catalog["config"]["CHARACTER_STEP_UP"],
        },
        "mates": {k: list(v) for k, v in sorted(CONNECTOR_COMPATIBILITY.items())},
        "tolerance": {
            "position_metres": DEFAULT_TOLERANCE.position_metres,
            "angle_degrees": DEFAULT_TOLERANCE.angle_degrees,
            "roll_degrees": DEFAULT_TOLERANCE.roll_degrees,
        },
        "legend": {
            "c": CONNECTOR_FIELDS,
            "mode": {"p": "point mate: the two points must coincide",
                     "s": "surface mate: the planes must be coplanar and the "
                          "smaller extent contained in the larger"},
            "ap": APERTURE_FIELDS,
            "clear": "[min_x,min_y,min_z,max_x,max_y,max_z] volumes that must stay empty",
            "omitted": ("occupancy, collision hulls, materials, LODs, geometry "
                        "statistics, engine import settings, provenance and "
                        "licence. None is needed to place an asset. Fetch "
                        "full_catalog when you need them; the fingerprint "
                        "proves you have the matching one."),
        },
        "asset_count": len(assets),
        "assets": assets,
    }


def expand(brief) -> dict:
    """Rebuild the minimal catalog shape the placement solver consumes.

    This is what makes "the brief is sufficient" testable rather than asserted:
    a solver fed the expansion of a brief must produce a layout that validates
    against the *full* catalog it was derived from.
    """
    assets = []
    for a in brief["assets"]:
        connectors = []
        for c in a["c"]:
            record = dict(zip(CONNECTOR_FIELDS, c))
            tol = record.get("tolerance_override")
            connectors.append({
                "id": record["id"],
                "kind": record["kind"],
                "position": record["pos"],
                "normal": record["normal"],
                "tangent": record["tangent"],
                "mating_mode": "surface" if record["mode"] == "s" else "point",
                "extent_half": record.get("extent"),
                "scale_class": "standard",
                "compatible_kinds": brief["mates"].get(record["kind"], []),
                "tolerance": {
                    "position_metres": tol[0] if tol else brief["tolerance"]["position_metres"],
                    "angle_degrees": tol[1] if tol else brief["tolerance"]["angle_degrees"],
                    "roll_degrees": tol[2] if tol else brief["tolerance"]["roll_degrees"],
                },
                "required": False,
            })
        support = {"requires_support": "on" in a}
        if "on" in a:
            support["rests_on"] = a["on"]
            support["may_float"] = bool(a.get("carried_by_connection"))
            if a.get("datum"):
                support["datum_connector"] = a["datum"]
        assets.append({
            "id": brief["id_prefix"] + a["id"],
            "semantic_role": a["role"],
            "dimensions": {
                "size": a["size"],
                # base is the offset from the lowest point to the origin, so the
                # lowest point sits at -base in local space
                "bounds": {"min": [0.0, 0.0, -a["base"]], "max": a["size"]},
            },
            "pivot": {"base_offset_z": a["base"]},
            "placement": {
                "grid": {"policy": a["grid"]},
                "allowed_rotations": a["yaw"],
                "support": support,
            },
            "connectors": connectors,
            "apertures": [],
        })
    return {
        "schema": "tessera.catalog/1",
        "contract_version": brief["contract_version"],
        "kit": {"id": brief["kit"].split("@")[0], "version": brief["kit"].split("@")[1]},
        "fingerprint": brief["fingerprint"],
        "derived_from_brief": True,
        "assets": assets,
    }


def render_text(brief) -> str:
    """A line-oriented rendering. Cheaper again in tokens than JSON."""
    out = []
    add = out.append
    add("TESSERA BRIEF %s  fingerprint %s  contract %s"
        % (brief["kit"], brief["fingerprint"][:12], brief["contract_version"]))
    add("SPACE right-handed, Z up, +Y forward, metres; rotation [yaw,pitch,roll] degrees ZYX")
    add("GROUND world_z = support_top + base   (or the 'datum' connector's plane when present)")
    add("GRID module %.2f  snap_xy %.2f  snap_z %.2f"
        % (brief["grid"]["module"], brief["grid"]["xy"], brief["grid"]["z"]))
    add("STACK " + "  ".join("%s=%.2f" % (k, v) for k, v in brief["stack"].items()))
    add("CHARACTER radius %.2f height %.2f step_up %.2f"
        % (brief["character"]["radius"], brief["character"]["height"],
           brief["character"]["step_up"]))
    add("STOREY height %.2f  stair %d steps over %.2f m at %.1f degrees"
        % (brief["storey"]["height"], brief["storey"]["stair_steps"],
           brief["storey"]["stair_run"], brief["storey"]["stair_angle_degrees"]))
    add("TOLERANCE pos %.3fm  angle %.1fdeg  roll %.1fdeg"
        % (brief["tolerance"]["position_metres"], brief["tolerance"]["angle_degrees"],
           brief["tolerance"]["roll_degrees"]))
    add("")
    add("MATES")
    for kind, partners in brief["mates"].items():
        add("  %-16s <- %s" % (kind, ", ".join(partners)))
    add("")
    add("ASSETS  (connector: id kind mode pos normal tangent extent)")
    for a in brief["assets"]:
        yaw = "any" if a["yaw"] is None else ",".join("%g" % y for y in a["yaw"])
        line = ("  %s  %s  %.2fx%.2fx%.2f  base=%g  grid=%s  yaw=%s"
                % (a["id"], a["role"], *a["size"], a["base"], a["grid"], yaw))
        if a["scale"] != [1.0, 1.0]:
            line += "  scale=%g..%g" % tuple(a["scale"])
        add(line)
        if "on" in a:
            extra = "    rests_on %s" % ", ".join(a["on"])
            if a.get("datum"):
                extra += "  datum=%s" % a["datum"]
            if a.get("carried_by_connection"):
                extra += "  (carried by a connection, not by ground contact)"
            add(extra)
        for c in a["c"]:
            cid, kind, mode, pos, normal, tangent, extent, _ = c
            add("    %-12s %-15s %s (%.2f,%.2f,%.2f) n(%g,%g,%g) t(%g,%g,%g)%s"
                % (cid, kind, mode, *pos, *normal, *tangent,
                   ("  ext %.2fx%.2f" % tuple(extent)) if extent else ""))
        for ap in a.get("ap", []):
            add("    aperture %s %s along %s  clear %.2f x %.2f  %s"
                % (ap[0], ap[1], ap[2], ap[3], ap[4],
                   "walkable" if ap[5] and ap[6] else
                   ("traversable but too small" if ap[5] else "not a route")))
    add("")
    add("OMITTED " + brief["legend"]["omitted"])
    return "\n".join(out)


def write_brief(brief, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(brief, fh, separators=(",", ":"), sort_keys=False)
    return path
