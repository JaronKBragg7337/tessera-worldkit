"""Layout-level rules: is this arrangement of assets physically sane?

SPDX-License-Identifier: 0BSD

This is the module that pays for the whole repository. It answers, without
rendering anything, the questions an agent currently answers by taking a
screenshot and guessing:

* is anything floating, sunk, or unsupported?
* is anything intersecting anything else?
* did the pieces actually connect, or just end up near each other?
* is a connector facing the wrong way, or rolled 90 degrees?
* is a doorway blocked?
* is a clearance volume occupied?
* is anything off the grid, illegally rotated, or illegally scaled?

Every failure carries the delta needed to fix it, so the correction loop is
apply-and-revalidate rather than render-and-squint.
"""
from __future__ import annotations

import math

from ..boxset import boxes_overlap, box_volume, overlap_box
from ..contract import LAYOUT_SCHEMA_ID, compatible
from ..transform import Transform
from ..units import CANONICAL_SPACE, CONTACT_EPSILON, q
from .diagnostics import Collector

#: Below this shared volume a clash is a modelling sliver, not a real overlap.
CLASH_VOLUME_EPSILON = 1e-6
#: Fraction of a footprint that must rest on something to count as supported.
SUPPORT_COVERAGE = 0.02


def _xy_overlap_area(a, b):
    dx = min(a[3], b[3]) - max(a[0], b[0])
    dy = min(a[4], b[4]) - max(a[1], b[1])
    return max(0.0, dx) * max(0.0, dy)


class Instance:
    """A placed asset with everything already transformed into world space."""

    def __init__(self, spec, record):
        self.id = spec.get("id") or spec.get("name")
        self.asset_id = spec["asset"]
        self.spec = spec
        self.record = record
        self.transform = Transform.from_dict(spec)
        t = self.transform
        self.occupancy = t.boxes([tuple(b) for b in record["occupancy"]["boxes"]])
        self.clearance = t.boxes([tuple(b) for b in record["clearance"]["boxes"]])
        self.connectors = {}
        for c in record["connectors"]:
            self.connectors[c["id"]] = {
                "id": c["id"], "kind": c["kind"],
                "position": t.point(c["position"]),
                "normal": t.direction(c["normal"]),
                "tangent": t.direction(c["tangent"]),
                "mating_mode": c.get("mating_mode", "point"),
                "extent_half": c.get("extent_half"),
                "tolerance": c.get("tolerance", {}),
                "scale_class": c.get("scale_class", "standard"),
                "compatible_kinds": c.get("compatible_kinds", []),
                "required": c.get("required", False),
            }
        self.apertures = []
        for ap in record.get("apertures", []):
            b = ap["bounds"]
            self.apertures.append({
                **ap,
                "world": t.box((b["min"][0], b["min"][1], b["min"][2],
                                b["max"][0], b["max"][1], b["max"][2])),
            })
        self.connections = spec.get("connections", [])

    @property
    def bounds(self):
        bs = self.occupancy
        return (min(b[0] for b in bs), min(b[1] for b in bs), min(b[2] for b in bs),
                max(b[3] for b in bs), max(b[4] for b in bs), max(b[5] for b in bs))

    def base_z(self):
        return min(b[2] for b in self.occupancy)

    def base_footprint(self):
        bz = self.base_z()
        return [(b[0], b[1], 0, b[3], b[4], 0) for b in self.occupancy
                if abs(b[2] - bz) <= CONTACT_EPSILON]


def validate_layout(layout: dict, catalog: dict,
                    collector: Collector | None = None) -> Collector:
    c = collector or Collector()

    # ------------------------------------------------------------- 1 schema
    c.check("layout.schema")
    if layout.get("schema") != LAYOUT_SCHEMA_ID:
        c.error(code="TSR_LAYOUT_SCHEMA_MISMATCH", rule="layout.schema",
                what="Layout declares an unknown schema.", where={},
                expected=LAYOUT_SCHEMA_ID, actual=layout.get("schema"),
                fix="regenerate the layout")
    c.check("layout.space")
    if layout.get("space", {}).get("convention") not in (None, CANONICAL_SPACE):
        c.error(code="TSR_LAYOUT_SPACE_MISMATCH", rule="layout.space",
                what="Layout is not in canonical Tessera space.", where={},
                expected=CANONICAL_SPACE,
                actual=layout.get("space", {}).get("convention"),
                why="Placing metre assets into a centimetre layout is a 100x scale bug.",
                fix="convert the layout")

    c.check("layout.catalog_pinned")
    declared = (layout.get("catalog") or {}).get("fingerprint")
    actual = catalog.get("fingerprint")
    if declared and actual and declared != actual:
        c.error(code="TSR_LAYOUT_CATALOG_MISMATCH", rule="layout.catalog_pinned",
                what="Layout was composed against a different catalog.",
                where={"declared": declared[:12], "loaded": actual[:12]},
                expected=declared, actual=actual,
                why=("Every coordinate in this layout was solved from asset "
                     "dimensions that may since have changed. Validating it "
                     "against a different catalog would report success on a "
                     "scene that no longer fits together -- the exact failure "
                     "mode of composing on one device and executing on another."),
                fix=("rebuild the layout against the loaded catalog, or load the "
                     "catalog with fingerprint %s" % declared[:12]))
    elif not declared:
        c.warn(code="TSR_LAYOUT_CATALOG_UNPINNED", rule="layout.catalog_pinned",
               what="Layout does not say which catalog it was composed against.",
               where={}, expected="catalog.fingerprint", actual=None,
               why=("Without a pin, a later catalog change silently invalidates "
                    "this layout instead of failing loudly."),
               fix="regenerate the layout with a current Tessera version")

    index = {a["id"]: a for a in catalog.get("assets", [])}

    # -------------------------------------------------------- 2 resolvable
    c.check("layout.asset_known")
    c.check("layout.instance_ids_unique")
    instances, seen = [], set()
    for spec in layout.get("instances", []):
        iid = spec.get("id") or spec.get("name")
        if iid in seen:
            c.error(code="TSR_LAYOUT_DUPLICATE_INSTANCE", rule="layout.instance_ids_unique",
                    what="Two instances share an id.", where={"instance": iid},
                    expected="unique instance ids", actual=iid,
                    why="Connections are addressed by id, so duplicates are ambiguous.",
                    fix="rename one instance")
        seen.add(iid)
        rec = index.get(spec.get("asset"))
        if rec is None:
            c.error(code="TSR_LAYOUT_UNKNOWN_ASSET", rule="layout.asset_known",
                    what="Instance references an asset that is not in the catalog.",
                    where={"instance": iid, "asset": spec.get("asset")},
                    expected="an id present in catalog.assets", actual=spec.get("asset"),
                    why="Nothing else about this instance can be checked.",
                    fix="use `tessera catalog --ids` to list valid asset ids")
            continue
        instances.append(Instance(spec, rec))

    by_id = {i.id: i for i in instances}

    # --------------------------------------------------- 3 legal transforms
    c.check("layout.grid")
    c.check("layout.rotation_allowed")
    c.check("layout.scale_allowed")
    for inst in instances:
        place = inst.record["placement"]
        grid = place.get("grid", {})
        w = {"instance": inst.id, "asset": inst.asset_id,
             "position": list(inst.transform.position)}

        gx = grid.get("snap_xy")
        gz = grid.get("snap_z")
        if gx:
            for axis in (0, 1):
                v = inst.transform.position[axis]
                off = abs(v - round(v / gx) * gx)
                if off > 1e-6:
                    c.error(code="TSR_LAYOUT_OFF_GRID", rule="layout.grid",
                            what="Instance is off the translation grid.",
                            where=dict(w, axis="xy"[axis]),
                            expected="multiple of %g m" % gx, actual=v,
                            why=("Modular pieces only seam correctly on the grid "
                                 "they were authored on; off-grid placement leaves "
                                 "visible cracks and breaks connector mating."),
                            fix="snap to the nearest grid position",
                            fix_transform={"translate": [
                                q(round(v / gx) * gx - v) if axis == 0 else 0.0,
                                q(round(v / gx) * gx - v) if axis == 1 else 0.0,
                                0.0]})
        if gz:
            v = inst.transform.position[2]
            if abs(v - round(v / gz) * gz) > 1e-6:
                c.warn(code="TSR_LAYOUT_OFF_GRID_Z", rule="layout.grid",
                       what="Instance height is off the vertical grid.", where=w,
                       expected="multiple of %g m" % gz, actual=v,
                       fix="snap Z to the grid",
                       fix_transform={"translate": [0, 0, q(round(v / gz) * gz - v)]})

        allowed = place.get("allowed_rotations")
        yaw = inst.transform.rotation[0] % 360.0
        pitch, roll = inst.transform.rotation[1], inst.transform.rotation[2]
        if not place.get("allow_pitch_roll", False) and (
                abs(pitch) > 1e-6 or abs(roll) > 1e-6):
            c.error(code="TSR_LAYOUT_ILLEGAL_ROTATION", rule="layout.rotation_allowed",
                    what="Instance is pitched or rolled off the ground plane.",
                    where=w, expected="pitch = 0, roll = 0", actual=[pitch, roll],
                    why=("Ground-plane assets have no defined support behaviour "
                         "when tipped, and their occupancy stops being exact."),
                    fix="zero the pitch and roll",
                    fix_transform={"set_rotation": [yaw, 0.0, 0.0]})
        if allowed:
            if not any(abs(yaw - a) < 1e-6 for a in allowed):
                c.error(code="TSR_LAYOUT_ILLEGAL_ROTATION", rule="layout.rotation_allowed",
                        what="Instance uses a yaw the asset does not allow.", where=w,
                        expected=allowed, actual=yaw,
                        why=("This asset is only authored to seam at these yaws; "
                             "any other angle puts its connectors off the grid."),
                        fix="use the nearest allowed yaw",
                        fix_transform={"set_rotation": [
                            min(allowed, key=lambda a: abs(a - yaw)), pitch, roll]})

        scaling = place.get("allowed_scaling", {})
        s = inst.transform.scale
        lo, hi = scaling.get("min", 1.0), scaling.get("max", 1.0)
        if s < lo - 1e-9 or s > hi + 1e-9:
            c.error(code="TSR_LAYOUT_ILLEGAL_SCALE", rule="layout.scale_allowed",
                    what="Instance is scaled outside the asset's allowed range.",
                    where=w, expected="%g .. %g" % (lo, hi), actual=s,
                    why=(scaling.get("rationale")
                         or "Scaling a modular piece breaks its grid and connectors."),
                    fix="reset the scale to 1.0",
                    fix_transform={"set_scale": 1.0})

    # ------------------------------------------------------ 4 intersections
    c.check("layout.intersection")
    buried_pairs = set()
    clashes = []
    for i in range(len(instances)):
        for j in range(i + 1, len(instances)):
            a, b = instances[i], instances[j]
            if not boxes_overlap(a.bounds, b.bounds, gap=CONTACT_EPSILON):
                continue
            shared = 0.0
            worst = None
            for ba in a.occupancy:
                for bb in b.occupancy:
                    ov = overlap_box(ba, bb)
                    if ov and box_volume(ov) > CLASH_VOLUME_EPSILON:
                        v = box_volume(ov)
                        shared += v
                        if worst is None or v > worst[0]:
                            worst = (v, ov)
            if shared > CLASH_VOLUME_EPSILON:
                clashes.append((a, b, shared, worst))

    # ------------------------------------------------------------ 5 support
    c.check("layout.support")
    c.check("layout.grounded")
    for inst in instances:
        support = inst.record["placement"].get("support", {})
        if not support.get("requires_support"):
            continue
        w = {"instance": inst.id, "asset": inst.asset_id,
             "position": list(inst.transform.position)}

        if support.get("may_float"):
            # carried by a connection rather than by a surface
            if not inst.connections:
                c.warn(code="TSR_LAYOUT_UNATTACHED", rule="layout.support",
                       what="Instance is carried by a connection but declares none.",
                       where=w, expected="at least one connection to %s"
                                         % (support.get("rests_on") or "a host"),
                       actual="no connections declared",
                       why=("A hung leaf or a ridge cap has no ground contact, so "
                            "the only evidence it is attached is the connection."),
                       fix="declare the connection in the layout")
            continue

        datum_conn = support.get("datum_connector")
        if datum_conn and datum_conn in inst.connectors:
            cd = inst.connectors[datum_conn]
            datum_z = cd["position"][2]
            eh = cd.get("extent_half") or [0.05, 0.05]
            px, py = cd["position"][0], cd["position"][1]
            # axis-aligned extent in world XY (valid at 90-degree yaws)
            yaw = inst.transform.rotation[0] % 180.0
            ex, ey = (eh[0], eh[1]) if abs(yaw) < 1e-6 or abs(yaw - 180) < 1e-6 else (eh[1], eh[0])
            footprint = [(px - ex, py - ey, 0, px + ex, py + ey, 0)]
            datum_label = "bearing connector %r" % datum_conn
        else:
            datum_z = inst.base_z()
            footprint = inst.base_footprint()
            datum_label = "lowest occupied plane"

        fp_area = sum((f[3] - f[0]) * (f[4] - f[1]) for f in footprint) or 1e-9

        candidates = []
        rests_on = support.get("rests_on") or []
        if "terrain" in rests_on:
            candidates.append(("terrain", 0.0, fp_area))
        for other in instances:
            if other is inst:
                continue
            for ob in other.occupancy:
                # A support candidate has to *start* below the datum. Without
                # this test every instance in the building reports as buried
                # under the roof, because the roof overlaps it in plan and its
                # top is higher. Overlapping in plan is not the same as being
                # underneath.
                if ob[2] > datum_z + CONTACT_EPSILON:
                    continue
                area = sum(_xy_overlap_area(f, ob) for f in footprint)
                if area / fp_area >= SUPPORT_COVERAGE:
                    candidates.append((other.id, ob[5], area))

        if not candidates:
            c.error(code="TSR_LAYOUT_UNSUPPORTED", rule="layout.support",
                    what="Nothing is underneath this instance.", where=w,
                    expected="a surface of kind %s beneath the %s"
                             % (rests_on or "any", datum_label),
                    actual="no overlapping geometry below",
                    why=("This asset declares that it requires support; placing it "
                         "with nothing beneath means it hangs in mid-air."),
                    fix="place a supporting asset beneath it, or move it onto one")
            continue

        below = [x for x in candidates if x[1] <= datum_z + CONTACT_EPSILON]
        above = [x for x in candidates if x[1] > datum_z + CONTACT_EPSILON]

        if above:
            # Reached only when something whose base is below us has a top above
            # us -- i.e. we are genuinely embedded in it.
            worst = max(above, key=lambda x: x[1])
            delta = q(worst[1] - datum_z)
            c.error(code="TSR_LAYOUT_BURIED", rule="layout.grounded",
                    what="Instance is sunk into the surface it should rest on.",
                    where=dict(w, support=worst[0]),
                    expected="%s at z = %.4f" % (datum_label, worst[1]),
                    actual=round(datum_z, 4),
                    why=("Its %s lies %.4f m below the top of %s, so the two solids "
                         "interpenetrate." % (datum_label, delta, worst[0])),
                    fix="raise by %.4f m" % delta,
                    fix_transform={"translate": [0.0, 0.0, delta]})
            buried_pairs.add(frozenset((inst.id, worst[0])))
            continue

        best = max(below, key=lambda x: x[1])
        gap = q(datum_z - best[1])
        if gap > CONTACT_EPSILON:
            c.error(code="TSR_LAYOUT_FLOATING", rule="layout.grounded",
                    what="Instance floats above its support.",
                    where=dict(w, support=best[0]),
                    expected="%s at z = %.4f (top of %s)" % (datum_label, best[1], best[0]),
                    actual=round(datum_z, 4),
                    why=("A %.4f m gap between the asset and the highest surface "
                         "beneath it. This is the single most common placement "
                         "error and it is invisible from directly above."
                         % gap),
                    fix="lower by %.4f m" % gap,
                    fix_transform={"translate": [0.0, 0.0, -gap]})

    for (a, b, shared, worst) in clashes:
        if frozenset((a.id, b.id)) in buried_pairs:
            continue
        c.error(code="TSR_LAYOUT_INTERSECTION", rule="layout.intersection",
                what="Two instances occupy the same space.",
                where={"instance": a.id, "asset": a.asset_id,
                       "other_instance": b.id, "other_asset": b.asset_id,
                       "position": list(a.transform.position)},
                expected="0 m3 shared volume",
                actual=round(shared, 6),
                why=("Overlapping solids z-fight, break physics and mean at least "
                     "one piece is on the wrong grid cell. The largest overlapping "
                     "region is %s." % (tuple(round(v, 3) for v in worst[1]),)),
                fix=("move one instance by one grid step, or use the corner variant "
                     "that is authored not to overlap at junctions"))

    # --------------------------------------------------------- 6 connectors
    c.check("layout.connector.kind")
    c.check("layout.connector.direction")
    c.check("layout.connector.roll")
    c.check("layout.connector.gap")
    c.check("layout.connector.scale_class")
    connection_stats = {"declared": 0, "verified": 0}
    for inst in instances:
        for link in inst.connections:
            connection_stats["declared"] += 1
            src_id = link.get("from")
            tgt = link.get("to", {})
            other = by_id.get(tgt.get("instance"))
            w = {"instance": inst.id, "asset": inst.asset_id, "connector": src_id,
                 "other_instance": tgt.get("instance"),
                 "other_connector": tgt.get("connector")}
            src = inst.connectors.get(src_id)
            if src is None:
                c.error(code="TSR_LAYOUT_UNKNOWN_CONNECTOR", rule="layout.connector.kind",
                        what="Connection references a connector the asset does not have.",
                        where=w, expected=sorted(inst.connectors), actual=src_id,
                        fix="use one of the asset's declared connector ids")
                continue
            if other is None:
                c.error(code="TSR_LAYOUT_UNKNOWN_CONNECTOR", rule="layout.connector.kind",
                        what="Connection targets an instance that does not exist.",
                        where=w, expected="an instance id in this layout",
                        actual=tgt.get("instance"),
                        fix="fix the target instance id")
                continue
            dst = other.connectors.get(tgt.get("connector"))
            if dst is None:
                c.error(code="TSR_LAYOUT_UNKNOWN_CONNECTOR", rule="layout.connector.kind",
                        what="Connection references a connector the target does not have.",
                        where=w, expected=sorted(other.connectors),
                        actual=tgt.get("connector"),
                        fix="use one of the target's declared connector ids")
                continue

            ok = True
            if not compatible(src["kind"], dst["kind"]):
                ok = False
                c.error(code="TSR_LAYOUT_CONNECTOR_MISMATCH", rule="layout.connector.kind",
                        what="Connected connectors are of incompatible kinds.", where=w,
                        expected="%s accepts %s" % (src["kind"], src["compatible_kinds"]),
                        actual=dst["kind"],
                        why=("Kind compatibility encodes what physically joins to "
                             "what. A wall base does not attach to a roof ridge."),
                        fix="connect to a %s instead" % (src["compatible_kinds"] or "compatible kind"))

            if src["scale_class"] != dst["scale_class"]:
                ok = False
                c.error(code="TSR_LAYOUT_SCALE_CLASS_MISMATCH",
                        rule="layout.connector.scale_class",
                        what="Connected connectors belong to different scale classes.",
                        where=w, expected=src["scale_class"], actual=dst["scale_class"],
                        why=("Scale classes are separate module standards. Mating "
                             "across them produces a join that is geometrically "
                             "close but dimensionally wrong."),
                        fix="use assets from the same scale class")

            tol = src.get("tolerance") or {}
            ang_tol = float(tol.get("angle_degrees", 1.0))
            roll_tol = float(tol.get("roll_degrees", 1.0))
            pos_tol = float(tol.get("position_metres", 0.001))

            dot = sum(a_ * b_ for a_, b_ in zip(src["normal"], dst["normal"]))
            angle = math.degrees(math.acos(max(-1.0, min(1.0, -dot))))
            if angle > ang_tol:
                ok = False
                c.error(code="TSR_LAYOUT_CONNECTOR_DIRECTION",
                        rule="layout.connector.direction",
                        what="Connected connectors do not face each other.", where=w,
                        expected="normals opposed within %.2f degrees" % ang_tol,
                        actual="%.3f degrees off" % angle,
                        why=("Two connectors at the same point facing the same way "
                             "means one piece is rotated 180 degrees from where it "
                             "belongs. Position alone cannot detect this."),
                        fix="rotate the connected instance by %.0f degrees about Z"
                            % (180.0 if angle > 90 else angle),
                        fix_transform={"rotate_z_by": 180.0 if angle > 90 else round(angle, 3)})

            tdot = sum(a_ * b_ for a_, b_ in zip(src["tangent"], dst["tangent"]))
            roll = math.degrees(math.acos(max(-1.0, min(1.0, abs(tdot)))))
            if roll > roll_tol:
                ok = False
                c.error(code="TSR_LAYOUT_CONNECTOR_ROLL", rule="layout.connector.roll",
                        what="Connected connectors are rolled relative to each other.",
                        where=w, expected="tangents aligned within %.2f degrees" % roll_tol,
                        actual="%.3f degrees of roll" % roll,
                        why=("The pieces meet face to face but one is spun about the "
                             "join axis, so trim, panel lines and openings do not "
                             "line up."),
                        fix="rotate the connected instance about the mating axis")

            gap_vec = [dst["position"][k] - src["position"][k] for k in range(3)]
            if src["mating_mode"] == "surface" or dst["mating_mode"] == "surface":
                n = src["normal"]
                along = abs(sum(gap_vec[k] * n[k] for k in range(3)))
                if along > max(pos_tol, CONTACT_EPSILON):
                    ok = False
                    c.error(code="TSR_LAYOUT_CONNECTOR_GAP", rule="layout.connector.gap",
                            what="Mated surfaces are not coplanar.", where=w,
                            expected="<= %.4f m along the surface normal" % pos_tol,
                            actual=round(along, 5),
                            why="The two faces are meant to be flush against each other.",
                            fix="move by %.4f m along the mating normal" % along,
                            fix_transform={"translate": [round(-n[k] * along * (1 if sum(gap_vec[j]*n[j] for j in range(3)) < 0 else -1), 6) for k in range(3)]})
            else:
                dist = math.sqrt(sum(v * v for v in gap_vec))
                if dist > pos_tol:
                    ok = False
                    c.error(code="TSR_LAYOUT_CONNECTOR_GAP", rule="layout.connector.gap",
                            what="Connected connectors are not at the same point.",
                            where=w, expected="<= %.4f m apart" % pos_tol,
                            actual=round(dist, 5),
                            why=("A declared seam with a measurable gap is a visible "
                                 "crack in the assembled build."),
                            fix="translate by the gap vector",
                            fix_transform={"translate": [round(v, 6) for v in gap_vec]})
            if ok:
                connection_stats["verified"] += 1

    # ------------------------------------------------- 7 apertures/clearance
    c.check("layout.aperture_clear")
    for inst in instances:
        exempt = set()
        for link in inst.connections:
            exempt.add(link.get("to", {}).get("instance"))
        for other in instances:
            for link in other.connections:
                if link.get("to", {}).get("instance") == inst.id:
                    exempt.add(other.id)
        for ap in inst.apertures:
            if not ap.get("traversable"):
                continue
            for other in instances:
                if other is inst:
                    continue
                blocked = 0.0
                for ob in other.occupancy:
                    ov = overlap_box(ob, ap["world"])
                    if ov:
                        blocked += box_volume(ov)
                if blocked <= CLASH_VOLUME_EPSILON:
                    continue
                w = {"instance": inst.id, "asset": inst.asset_id,
                     "aperture": ap["id"], "other_instance": other.id,
                     "other_asset": other.asset_id}
                if other.id in exempt:
                    c.info(code="TSR_LAYOUT_APERTURE_OCCUPIED_BY_LEAF",
                           rule="layout.aperture_clear",
                           what="Aperture is filled by its own leaf.", where=w,
                           expected="informational",
                           actual="%.4f m3 of the opening is occupied" % blocked,
                           why=("The blocking instance is connected to this wall, so "
                                "it is the door or window that belongs in the hole. "
                                "The opening is closed but not obstructed."),
                           fix="none needed; open the leaf if the route must be passable")
                else:
                    c.error(code="TSR_LAYOUT_APERTURE_BLOCKED",
                            rule="layout.aperture_clear",
                            what="A traversable opening is blocked by another asset.",
                            where=w,
                            expected="the %s aperture clear of all geometry" % ap["kind"],
                            actual="%.4f m3 obstructed by %s" % (blocked, other.asset_id),
                            why=("The mesh has a doorway and the collision preserves "
                                 "it, but something has been placed in the route, so "
                                 "the player still cannot get through."),
                            fix="move %s out of the opening" % other.id)

    c.check("layout.clearance")
    for inst in instances:
        if not inst.clearance:
            continue
        exempt = {l.get("to", {}).get("instance") for l in inst.connections}
        for other in instances:
            for l in other.connections:
                if l.get("to", {}).get("instance") == inst.id:
                    exempt.add(other.id)
        for other in instances:
            if other is inst or other.id in exempt:
                continue
            occupied = 0.0
            for cb in inst.clearance:
                for ob in other.occupancy:
                    ov = overlap_box(cb, ob)
                    if ov:
                        occupied += box_volume(ov)
            if occupied > 1e-4:
                c.warn(code="TSR_LAYOUT_CLEARANCE_VIOLATED", rule="layout.clearance",
                       what="A required clearance volume is occupied.",
                       where={"instance": inst.id, "asset": inst.asset_id,
                              "other_instance": other.id},
                       expected="clearance volumes empty",
                       actual="%.4f m3 occupied by %s" % (occupied, other.id),
                       why=("Clearance is the space the asset needs to function -- "
                            "a door swing, a walk-up, a maintenance gap. Geometry "
                            "here does not clash, but the asset stops working."),
                       fix="move %s clear of the volume" % other.id)

    c.connection_stats = connection_stats
    return c
