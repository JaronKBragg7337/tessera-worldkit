"""Asset-level rules: is this catalog entry internally coherent?

SPDX-License-Identifier: 0BSD

These run at build time. An asset that fails here never reaches a layout, which
is the cheapest possible place to catch a bad pivot or a connector pointing into
the middle of a wall.
"""
from __future__ import annotations

import math

from ..boxset import BoxSet, boxes_overlap
from ..contract import (
    CATEGORIES, CONNECTOR_COMPATIBILITY, CONNECTOR_KINDS, SCALE_CLASSES,
    SCHEMA_ID, SEMANTIC_ROLES,
)
from ..units import CANONICAL_SPACE, CONTACT_EPSILON, LINEAR_UNIT
from .diagnostics import Collector

VALIDATOR_VERSION = "1.0.0"

REQUIRED_TOP_LEVEL = (
    "schema", "id", "name", "category", "semantic_role", "space", "dimensions",
    "pivot", "axes", "placement", "connectors", "occupancy", "collision",
    "materials", "geometry", "provenance", "license", "validation",
)

#: Roles whose origin must sit on the asset's own base. Getting this wrong is
#: the single most common cause of a floating or buried object, so it is a hard
#: rule rather than a documented convention.
BASE_PIVOT_ROLES = {
    "foundation", "floor", "wall", "wall_opening", "corner", "column",
    "stair", "prop", "ground", "road",
}


def validate_asset(record: dict, collector: Collector | None = None) -> Collector:
    c = collector or Collector()
    aid = record.get("id", "<unknown>")
    where = {"asset": aid}

    # ---------------------------------------------------------- 1 structure
    c.check("asset.schema.required_fields")
    for key in REQUIRED_TOP_LEVEL:
        if key not in record:
            c.error(code="TSR_ASSET_MISSING_FIELD", rule="asset.schema.required_fields",
                    what="Catalog entry is missing a required field.",
                    where=dict(where, field=key),
                    why=("Consumers index this field unconditionally; its absence "
                         "makes the entry unusable rather than merely incomplete."),
                    expected="field %r present" % key, actual="absent",
                    fix="regenerate the catalog with `tessera build`")

    c.check("asset.schema.version")
    if record.get("schema") != SCHEMA_ID:
        c.error(code="TSR_ASSET_SCHEMA_MISMATCH", rule="asset.schema.version",
                what="Catalog entry declares a schema this validator does not implement.",
                where=where, expected=SCHEMA_ID, actual=record.get("schema"),
                why="Silently reading an unknown schema is how stale fields get trusted.",
                fix="regenerate with a matching Tessera version")

    c.check("asset.vocabulary")
    if record.get("category") not in CATEGORIES:
        c.error(code="TSR_ASSET_UNKNOWN_CATEGORY", rule="asset.vocabulary",
                what="Unknown asset category.", where=where,
                expected=list(CATEGORIES), actual=record.get("category"),
                why="Category drives which placement rules apply.",
                fix="use one of the declared categories")
    if record.get("semantic_role") not in SEMANTIC_ROLES:
        c.error(code="TSR_ASSET_UNKNOWN_ROLE", rule="asset.vocabulary",
                what="Unknown semantic role.", where=where,
                expected=list(SEMANTIC_ROLES), actual=record.get("semantic_role"),
                why="Role decides what the asset is allowed to rest on.",
                fix="use one of the declared roles")

    # ------------------------------------------------------------- 2 units
    c.check("asset.space.canonical")
    space = record.get("space", {})
    if space.get("convention") != CANONICAL_SPACE:
        c.error(code="TSR_ASSET_SPACE_MISMATCH", rule="asset.space.canonical",
                what="Asset is not expressed in canonical Tessera space.", where=where,
                expected=CANONICAL_SPACE, actual=space.get("convention"),
                why=("Mixed coordinate systems in one catalog is the failure that "
                     "produces mirrored buildings and sideways roofs."),
                fix="convert the asset before cataloguing it")
    if space.get("linear_unit") != LINEAR_UNIT:
        c.error(code="TSR_ASSET_UNIT_MISMATCH", rule="asset.space.canonical",
                what="Asset is not authored in metres.", where=where,
                expected=LINEAR_UNIT, actual=space.get("linear_unit"),
                why="A centimetre catalog mixed into a metre catalog is a 100x scale bug.",
                fix="rescale to metres")

    # ------------------------------------------------------- 3 mesh health
    geom = record.get("geometry", {})
    c.check("asset.mesh.watertight")
    if not geom.get("watertight"):
        c.error(code="TSR_ASSET_NOT_WATERTIGHT", rule="asset.mesh.watertight",
                what="Mesh is not a closed manifold shell.", where=where,
                expected="0 boundary edges, 0 non-manifold edges",
                actual="%s boundary, %s non-manifold"
                       % (geom.get("boundary_edges"), geom.get("non_manifold_edges")),
                why=("Open shells break physics cooking, boolean operations and "
                     "any renderer that culls backfaces."),
                fix="inspect the generator; a subtract box probably reaches a face exactly")
    c.check("asset.mesh.winding")
    if not geom.get("outward_winding"):
        c.error(code="TSR_ASSET_INVERTED_WINDING", rule="asset.mesh.winding",
                what="Mesh normals point inward.", where=where,
                expected="signed volume > 0", actual=geom.get("signed_volume"),
                why="Inward normals render as an invisible or black object.",
                fix="reverse the triangle winding")

    # ------------------------------------------------------------ 4 pivot
    dims = record.get("dimensions", {})
    pivot = record.get("pivot", {})
    role = record.get("semantic_role")
    c.check("asset.pivot.on_base")
    if role in BASE_PIVOT_ROLES:
        base_offset = pivot.get("base_offset_z")
        if base_offset is None or abs(base_offset) > CONTACT_EPSILON:
            c.error(code="TSR_ASSET_PIVOT_OFF_BASE", rule="asset.pivot.on_base",
                    what="Origin does not sit on the asset's own base.", where=where,
                    expected="base_offset_z == 0 for role %r" % role,
                    actual=base_offset,
                    why=("A %s is placed by putting its origin on a supporting "
                         "surface. If the origin is not on the base, every "
                         "placement floats or sinks by exactly this amount."
                         % role),
                    fix="translate the generated solid so its minimum Z is 0",
                    fix_transform={"translate": [0, 0, -(base_offset or 0)]})

    c.check("asset.dimensions.consistent")
    b = dims.get("bounds", {})
    size = dims.get("size", [])
    if b and len(size) == 3:
        for i, axis in enumerate("xyz"):
            want = round(b["max"][i] - b["min"][i], 6)
            if abs(want - size[i]) > 1e-6:
                c.error(code="TSR_ASSET_DIMENSION_MISMATCH",
                        rule="asset.dimensions.consistent",
                        what="Declared size disagrees with declared bounds.",
                        where=dict(where, axis=axis), expected=want, actual=size[i],
                        why="Two fields describing the same measurement must agree.",
                        fix="regenerate the catalog")

    # ------------------------------------------------------- 5 connectors
    c.check("asset.connector.frame")
    c.check("asset.connector.kind")
    c.check("asset.connector.on_surface")
    occ = BoxSet(boxes=[tuple(x) for x in record.get("occupancy", {}).get("boxes", [])])
    # An approximate occupancy set legitimately falls short of the real solid, so
    # containment tests widen by the amount the approximation declares.
    surface_tol = 0.02 + float(record.get("occupancy", {}).get(
        "approximation_tolerance", 0.0))
    # A connector may also sit inside one of the asset's OWN apertures -- that is
    # exactly where a door jamb belongs. Empty space in a hole the asset itself
    # cut is not "detached from the solid".
    own_apertures = []
    for _ap in record.get("apertures", []):
        _b = _ap["bounds"]
        own_apertures.append((_b["min"][0], _b["min"][1], _b["min"][2],
                              _b["max"][0], _b["max"][1], _b["max"][2]))
    seen_ids = set()
    for conn in record.get("connectors", []):
        cid = conn.get("id")
        cwhere = dict(where, connector=cid)
        if cid in seen_ids:
            c.error(code="TSR_ASSET_DUPLICATE_CONNECTOR", rule="asset.connector.kind",
                    what="Two connectors share an id.", where=cwhere,
                    expected="unique ids", actual=cid,
                    why="Mates are recorded by id; duplicates make a layout ambiguous.",
                    fix="rename one of them")
        seen_ids.add(cid)

        if conn.get("kind") not in CONNECTOR_KINDS:
            c.error(code="TSR_ASSET_UNKNOWN_CONNECTOR_KIND", rule="asset.connector.kind",
                    what="Connector uses a kind outside the declared vocabulary.",
                    where=cwhere, expected=list(CONNECTOR_KINDS), actual=conn.get("kind"),
                    why="An unknown kind can never be matched, so the connector is dead weight.",
                    fix="use a declared kind or extend the vocabulary in contract.py")
        elif not conn.get("compatible_kinds"):
            c.warn(code="TSR_ASSET_CONNECTOR_ORPHANED", rule="asset.connector.kind",
                   what="Connector has no compatible kinds and can never mate.",
                   where=cwhere, expected="at least one compatible kind", actual=[],
                   why="A connector that cannot mate adds noise to every search.",
                   fix="declare compatibility in CONNECTOR_COMPATIBILITY")

        n = conn.get("normal") or [0, 0, 0]
        t = conn.get("tangent") or [0, 0, 0]
        nlen = math.sqrt(sum(v * v for v in n))
        tlen = math.sqrt(sum(v * v for v in t))
        if abs(nlen - 1.0) > 1e-4:
            c.error(code="TSR_ASSET_CONNECTOR_NORMAL_NOT_UNIT",
                    rule="asset.connector.frame",
                    what="Connector normal is not a unit vector.", where=cwhere,
                    expected=1.0, actual=round(nlen, 6),
                    why="Mating compares normals by dot product; a non-unit normal skews the angle test.",
                    fix="normalise the vector")
        if abs(tlen - 1.0) > 1e-4:
            c.error(code="TSR_ASSET_CONNECTOR_TANGENT_NOT_UNIT",
                    rule="asset.connector.frame",
                    what="Connector tangent is not a unit vector.", where=cwhere,
                    expected=1.0, actual=round(tlen, 6),
                    why="The tangent fixes roll; a non-unit tangent breaks the roll test.",
                    fix="normalise the vector")
        dot = sum(a * b_ for a, b_ in zip(n, t))
        if abs(dot) > 1e-4:
            c.error(code="TSR_ASSET_CONNECTOR_FRAME_SKEWED",
                    rule="asset.connector.frame",
                    what="Connector tangent is not perpendicular to its normal.",
                    where=cwhere, expected=0.0, actual=round(dot, 6),
                    why=("normal, tangent and their cross product must form an "
                         "orthonormal frame or a mate is not a rigid transform."),
                    fix="orthogonalise the tangent against the normal")

        if conn.get("mating_mode") == "surface" and not conn.get("extent_half"):
            c.error(code="TSR_ASSET_CONNECTOR_NO_EXTENT", rule="asset.connector.frame",
                    what="Surface connector has no extent.", where=cwhere,
                    expected="extent_half = [half_u, half_v]", actual=None,
                    why="A surface mate is checked by containment, which needs an extent.",
                    fix="declare extent_half on the connector")

        if occ.boxes:
            p = conn.get("position")
            if conn.get("mating_mode") == "surface" and conn.get("extent_half"):
                # A surface connector marks a *plane region*, and its centre may
                # legitimately sit over a hole -- the centre of a doorway wall's
                # base is in the door opening, the centre of a workbench's
                # footprint is between its legs. Test the extent, not the point.
                eh = conn["extent_half"]
                n = conn.get("normal") or [0, 0, 1]
                axis = max(range(3), key=lambda i: abs(n[i]))
                others = [i for i in range(3) if i != axis]
                probe = [0.0] * 6
                probe[axis] = p[axis] - surface_tol
                probe[axis + 3] = p[axis] + surface_tol
                for k, i in enumerate(others):
                    half = eh[k] if k < len(eh) else 0.05
                    probe[i] = p[i] - half
                    probe[i + 3] = p[i] + half
                near = any(boxes_overlap(tuple(probe), bx) for bx in occ.boxes)
            else:
                near = any(
                    all(bx[i] - surface_tol <= p[i] <= bx[i + 3] + surface_tol
                        for i in range(3))
                    for bx in occ.boxes
                )
            if not near and own_apertures:
                near = any(
                    all(ab[i] - 0.001 <= p[i] <= ab[i + 3] + 0.001 for i in range(3))
                    for ab in own_apertures
                )
            if not near:
                c.error(code="TSR_ASSET_CONNECTOR_OFF_SURFACE",
                        rule="asset.connector.on_surface",
                        what="Connector sits in empty space, detached from the solid.",
                        where=dict(cwhere, position=p),
                        expected=("the connector footprint to touch the solid"
                                  if conn.get("mating_mode") == "surface"
                                  else "within %.0f mm of the occupancy volume "
                                       "or inside one of this asset's apertures"
                                       % (surface_tol * 1000)),
                        actual="misses all %d occupancy boxes" % len(occ.boxes),
                        why=("A connector that is not on the asset will mate the "
                             "neighbour into thin air."),
                        fix="move the connector onto a face of the solid")

    # ------------------------------------------------------- 6 occupancy
    c.check("asset.occupancy.disjoint")
    boxes = [tuple(x) for x in record.get("occupancy", {}).get("boxes", [])]
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes_overlap(boxes[i], boxes[j], gap=1e-7):
                c.error(code="TSR_ASSET_OCCUPANCY_OVERLAP",
                        rule="asset.occupancy.disjoint",
                        what="Occupancy boxes overlap each other.", where=where,
                        expected="pairwise disjoint", actual="boxes %d and %d overlap" % (i, j),
                        why="Overlapping boxes double-count volume and break exact clash tests.",
                        fix="rebuild the solid through BoxSet.add rather than appending boxes")
                break

    # -------------------------------------------- 7 collision vs apertures
    c.check("asset.collision.present")
    coll = record.get("collision", {})
    if not coll.get("hulls"):
        c.error(code="TSR_ASSET_MISSING_COLLISION", rule="asset.collision.present",
                what="Asset ships no collision geometry.", where=where,
                expected=">= 1 convex hull", actual=0,
                why=("Without authored collision the engine generates a convex hull, "
                     "which seals doorways, arches and stairs."),
                fix="derive collision from the occupancy box set")

    c.check("asset.collision.preserves_apertures")
    hulls = [tuple(h) for h in coll.get("hulls", [])]
    for ap in record.get("apertures", []):
        if not ap.get("traversable"):
            continue
        ab = ap["bounds"]
        abox = (ab["min"][0], ab["min"][1], ab["min"][2],
                ab["max"][0], ab["max"][1], ab["max"][2])
        for h in hulls:
            if boxes_overlap(h, abox, gap=CONTACT_EPSILON):
                c.error(code="TSR_ASSET_COLLISION_SEALS_APERTURE",
                        rule="asset.collision.preserves_apertures",
                        what="Collision geometry blocks a traversable aperture.",
                        where=dict(where, aperture=ap["id"]),
                        expected="no collision hull inside the %s aperture" % ap["kind"],
                        actual="hull %s intersects the aperture" % (tuple(round(v, 3) for v in h),),
                        why=("This is the classic modular-kit trap: the mesh has a "
                             "doorway but the collision does not, so the player "
                             "walks into an invisible wall."),
                        fix="derive hulls from the carved occupancy set, not the silhouette")
                break

    c.check("asset.aperture.admits_character")
    for ap in record.get("apertures", []):
        if not ap.get("traversable"):
            continue
        fits = ap.get("fits_capsule", {})
        if not fits.get("admits_reference_character", True):
            ref = fits.get("reference_character", {})
            c.error(code="TSR_ASSET_APERTURE_TOO_SMALL",
                    rule="asset.aperture.admits_character",
                    what="Aperture is marked traversable but the reference character does not fit.",
                    where=dict(where, aperture=ap["id"]),
                    expected="clear %.2f x %.2f m" % (ref.get("radius", 0) * 2,
                                                      ref.get("height", 0)),
                    actual="clear %.2f x %.2f m" % (ap["clear_width"], ap["clear_height"]),
                    why="A doorway nobody can walk through is a wall with a decoration.",
                    fix="widen the opening or mark the aperture non-traversable")

    # ------------------------------------------------ 8 provenance/licence
    c.check("asset.provenance.complete")
    prov = record.get("provenance", {})
    for key in ("generator", "created_utc", "authored_by", "origin"):
        if not prov.get(key):
            c.error(code="TSR_ASSET_MISSING_PROVENANCE", rule="asset.provenance.complete",
                    what="Provenance record is incomplete.",
                    where=dict(where, field=key),
                    expected="provenance.%s set" % key, actual=prov.get(key),
                    why=("A redistribution promise that cannot be audited per asset "
                         "is not a promise."),
                    fix="fill the field in the part definition")
    if prov.get("origin") == "third-party" and prov.get("third_party_review") in (None, "", "none-required"):
        c.error(code="TSR_ASSET_UNREVIEWED_THIRD_PARTY", rule="asset.provenance.complete",
                what="Third-party input has no licence review.", where=where,
                expected="a completed third_party_review", actual=prov.get("third_party_review"),
                why="Uncertain material must be quarantined, not shipped.",
                fix="review and record, or remove the input")

    c.check("asset.license.present")
    lic = record.get("license", {})
    if not lic.get("assets_spdx") or not lic.get("code_spdx"):
        c.error(code="TSR_ASSET_MISSING_LICENSE", rule="asset.license.present",
                what="Asset carries no licence identifiers.", where=where,
                expected="SPDX identifiers for code and assets", actual=lic,
                fix="add the licence record")

    c.check("asset.placement.rotation_declared")
    place = record.get("placement", {})
    if "allowed_rotations" not in place:
        c.error(code="TSR_ASSET_NO_ROTATION_POLICY",
                rule="asset.placement.rotation_declared",
                what="Asset does not say which rotations are legal.", where=where,
                expected="a list of yaws, or null for unrestricted",
                actual="field absent",
                why="An agent that cannot read the rotation policy has to guess it.",
                fix="declare allowed_rotations in the placement policy")

    c.check("asset.scale_class")
    if record.get("scale_class") not in SCALE_CLASSES:
        c.error(code="TSR_ASSET_UNKNOWN_SCALE_CLASS", rule="asset.scale_class",
                what="Unknown scale class.", where=where,
                expected=list(SCALE_CLASSES), actual=record.get("scale_class"),
                why="Scale classes are standards; an unknown one can never mate safely.",
                fix="use a declared scale class")

    return c
