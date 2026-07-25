"""Assemble structures from metadata alone.

SPDX-License-Identifier: 0BSD

This module is the proof of the whole thesis. Nothing here looks at a mesh, a
render or a screenshot. Every transform is *solved* from the placement contract:

* :meth:`Builder.ground` reads the host's supporting-surface connector and the
  guest's support datum, and computes Z. There is no ``z = 0.5`` anywhere.
* :meth:`Builder.mate` reads two connectors, picks the yaw that makes their
  normals oppose, and solves the translation that makes their points coincide.

If the contract is right, the assembly is right the first time. If the contract
is wrong, the validator says exactly which field is wrong. Either way nobody
renders anything to find out.
"""
from __future__ import annotations

import math

from .contract import LAYOUT_SCHEMA_ID, compatible
from .transform import Transform
from .units import ANGLE_UNIT, CANONICAL_SPACE, LINEAR_UNIT, q


class AssemblyError(RuntimeError):
    pass


class Builder:
    """Places assets by solving the contract, and records what it connected."""

    def __init__(self, catalog, name="untitled"):
        self.catalog = catalog
        self.index = {a["id"]: a for a in catalog["assets"]}
        self.name = name
        self.instances = []
        self._counts = {}
        #: every placement decision, for the metrics report
        self.log = []

    # ------------------------------------------------------------- internals
    def _record(self, asset_id):
        rec = self.index.get(asset_id)
        if rec is None:
            raise AssemblyError(
                "asset %r is not in the catalog; known ids: %s"
                % (asset_id, ", ".join(sorted(self.index)[:6]) + " ...")
            )
        return rec

    def _next_id(self, asset_id):
        short = asset_id.split("/")[-1].replace(".", "_")
        n = self._counts.get(short, 0) + 1
        self._counts[short] = n
        return "%s_%02d" % (short, n)

    def _connector(self, instance, cid):
        rec = self._record(instance["asset"])
        for c in rec["connectors"]:
            if c["id"] == cid:
                return c
        raise AssemblyError(
            "instance %r (%s) has no connector %r; it has: %s"
            % (instance["id"], instance["asset"], cid,
               ", ".join(c["id"] for c in rec["connectors"]))
        )

    def world_connector(self, instance, cid):
        c = self._connector(instance, cid)
        t = Transform.from_dict(instance)
        return {
            "id": cid, "kind": c["kind"],
            "position": t.point(c["position"]),
            "normal": t.direction(c["normal"]),
            "tangent": t.direction(c["tangent"]),
            "extent_half": c.get("extent_half"),
            "mating_mode": c.get("mating_mode", "point"),
        }

    def _add(self, asset_id, position, yaw, instance_id=None, connections=None,
             note=""):
        inst = {
            "id": instance_id or self._next_id(asset_id),
            "asset": asset_id,
            "position": [q(v) for v in position],
            "rotation_degrees": [float(yaw), 0.0, 0.0],
            "scale": 1.0,
        }
        if connections:
            inst["connections"] = connections
        self.instances.append(inst)
        self.log.append({"instance": inst["id"], "method": note or "explicit",
                         "solved": note != "explicit"})
        return inst

    # ------------------------------------------------------------------ API
    def place(self, asset_id, position, yaw=0.0, instance_id=None):
        """Explicit placement. Used only for the very first asset on terrain."""
        self._record(asset_id)
        return self._add(asset_id, position, yaw, instance_id, note="explicit")

    def ground(self, asset_id, x, y, yaw=0.0, on=None, surface=None,
               instance_id=None):
        """Place on a supporting surface, solving Z from the contract.

        ``on`` is the host instance; ``surface`` is the id of its supporting
        connector. When ``on`` is None the asset is placed on terrain at z=0.
        """
        rec = self._record(asset_id)
        support = rec["placement"].get("support", {})
        datum_id = support.get("datum_connector")
        if datum_id:
            datum_local_z = self._local_connector(rec, datum_id)["position"][2]
        else:
            datum_local_z = rec["dimensions"]["bounds"]["min"][2]

        if on is None:
            surface_z = 0.0
            method = "grounded on terrain"
        else:
            host_rec = self._record(on["asset"])
            if surface is None:
                surface = self._auto_surface(host_rec, rec)
            wc = self.world_connector(on, surface)
            if wc["mating_mode"] != "surface":
                raise AssemblyError(
                    "connector %r on %s is a %s connector, not a surface; "
                    "use mate() for point connectors"
                    % (surface, on["asset"], wc["mating_mode"])
                )
            surface_z = wc["position"][2]
            method = "solved z from %s.%s" % (on["id"], surface)

        z = q(surface_z - datum_local_z)
        return self._add(asset_id, (x, y, z), yaw, instance_id, note=method)

    def _auto_surface(self, host_rec, guest_rec):
        wanted = set(guest_rec["placement"].get("support", {}).get("rests_on", []))
        for c in host_rec["connectors"]:
            if c["kind"] in wanted and c.get("mating_mode") == "surface":
                return c["id"]
        raise AssemblyError(
            "%s needs to rest on one of %s but %s offers none of those as a "
            "surface connector" % (guest_rec["id"], sorted(wanted), host_rec["id"])
        )

    @staticmethod
    def _local_connector(rec, cid):
        for c in rec["connectors"]:
            if c["id"] == cid:
                return c
        raise AssemblyError("asset %s has no connector %r" % (rec["id"], cid))

    def mate(self, asset_id, connector_id, host, host_connector,
             yaw=None, instance_id=None, extra_connections=None):
        """Place an asset so its connector mates a host connector.

        Solves both the yaw (from the allowed set, by requiring opposed normals)
        and the translation (by requiring coincident points). Raises rather than
        guessing when no allowed yaw satisfies the constraint -- a refusal an
        agent can act on beats a placement it has to check.
        """
        rec = self._record(asset_id)
        guest = self._local_connector(rec, connector_id)
        hw = self.world_connector(host, host_connector)

        if not compatible(guest["kind"], hw["kind"]):
            raise AssemblyError(
                "cannot mate %s.%s (%s) to %s.%s (%s): %s accepts only %s"
                % (asset_id, connector_id, guest["kind"], host["id"],
                   host_connector, hw["kind"], guest["kind"],
                   guest.get("compatible_kinds"))
            )

        target_normal = [-v for v in hw["normal"]]
        candidates = ([float(yaw)] if yaw is not None
                      else rec["placement"]["allowed_rotations"])
        chosen = None
        for candidate in candidates:
            t = Transform(position=(0, 0, 0), rotation=(candidate, 0.0, 0.0))
            n = t.direction(guest["normal"])
            if sum(a * b for a, b in zip(n, target_normal)) > 0.999:
                chosen = candidate
                break
        if chosen is None:
            raise AssemblyError(
                "no allowed yaw in %s makes %s.%s face %s; the host connector "
                "normal is %s. Either the asset is the wrong variant for this "
                "junction or the host is rotated wrongly."
                % (candidates, asset_id, connector_id, target_normal, hw["normal"])
            )

        rot = Transform(position=(0, 0, 0), rotation=(chosen, 0.0, 0.0))
        local = rot.point(guest["position"])
        position = tuple(q(hw["position"][i] - local[i]) for i in range(3))

        connections = [{"from": connector_id,
                        "to": {"instance": host["id"], "connector": host_connector}}]
        connections.extend(extra_connections or [])
        return self._add(asset_id, position, chosen, instance_id,
                         connections=connections,
                         note="solved from %s.%s" % (host["id"], host_connector))

    def autoconnect(self, position_tolerance=0.002, angle_tolerance=1.0):
        """Discover and declare every real connector mate in the scene.

        Two connectors mate when their kinds are compatible, their scale classes
        agree, their world points coincide within tolerance and their normals
        oppose. Discovering these instead of hand-listing them means the layout
        records what actually joined rather than what the author believed
        joined -- and the count is a hard metric for how well the contract
        describes the kit.

        Returns the number of connections added.
        """
        import itertools

        world = []
        for inst in self.instances:
            rec = self._record(inst["asset"])
            t = Transform.from_dict(inst)
            for cdef in rec["connectors"]:
                world.append((inst, cdef["id"], cdef["kind"],
                              cdef.get("scale_class", "standard"),
                              cdef.get("mating_mode", "point"),
                              t.point(cdef["position"]),
                              t.direction(cdef["normal"])))

        cos_limit = math.cos(math.radians(angle_tolerance))
        existing = set()
        for inst in self.instances:
            for link in inst.get("connections", []):
                existing.add((inst["id"], link["from"],
                              link["to"]["instance"], link["to"]["connector"]))

        added = 0
        for a_, b_ in itertools.combinations(world, 2):
            (ia, ida, ka, sa, ma, pa, na) = a_
            (ib, idb, kb, sb, mb, pb, nb) = b_
            if ia is ib or ma != "point" or mb != "point":
                continue
            if sa != sb or not compatible(ka, kb):
                continue
            dist = math.sqrt(sum((pa[i] - pb[i]) ** 2 for i in range(3)))
            if dist > position_tolerance:
                continue
            if -sum(na[i] * nb[i] for i in range(3)) < cos_limit:
                continue
            if (ia["id"], ida, ib["id"], idb) in existing or \
               (ib["id"], idb, ia["id"], ida) in existing:
                continue
            self.connect(ia, ida, ib, idb)
            existing.add((ia["id"], ida, ib["id"], idb))
            added += 1
        return added

    def connect(self, instance, connector_id, host, host_connector):
        """Declare a connection between two already-placed instances."""
        instance.setdefault("connections", []).append(
            {"from": connector_id,
             "to": {"instance": host["id"], "connector": host_connector}})
        return instance

    # ---------------------------------------------------------------- output
    def to_layout(self, description=""):
        bounds = self._bounds()
        return {
            "schema": LAYOUT_SCHEMA_ID,
            "name": self.name,
            "description": description,
            "generator": "tessera.assemble.Builder",
            "catalog": {"kit": self.catalog["kit"],
                        "contract_version": self.catalog["contract_version"]},
            "space": {"convention": CANONICAL_SPACE,
                      "linear_unit": LINEAR_UNIT,
                      "angle_unit": ANGLE_UNIT},
            "bounds": bounds,
            "instance_count": len(self.instances),
            "assets_used": sorted({i["asset"] for i in self.instances}),
            "placement_method": {
                "explicit": sum(1 for e in self.log if not e["solved"]),
                "solved_from_contract": sum(1 for e in self.log if e["solved"]),
            },
            "instances": self.instances,
        }

    def _bounds(self):
        lo = [float("inf")] * 3
        hi = [float("-inf")] * 3
        for inst in self.instances:
            rec = self._record(inst["asset"])
            t = Transform.from_dict(inst)
            for b in rec["occupancy"]["boxes"]:
                wb = t.box(tuple(b))
                for i in range(3):
                    lo[i] = min(lo[i], wb[i])
                    hi[i] = max(hi[i], wb[i + 3])
        return {"min": [q(v) for v in lo], "max": [q(v) for v in hi]}
