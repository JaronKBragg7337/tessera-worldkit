"""The Tessera placement contract.

SPDX-License-Identifier: 0BSD

This module is the whole product. Everything else in the repository exists to
generate it, validate it, or consume it.

The contract answers, in machine-readable form, every question an agent
otherwise has to answer by rendering a picture and squinting:

* How big is this thing, really?           -> ``dimensions``
* Where is its origin, and why there?      -> ``pivot``
* Which way is it facing?                  -> ``axes``
* Where does it touch the ground?          -> ``dimensions.grounded_bounds``
* What may I do to it?                     -> ``placement``
* How does it attach to other things?      -> ``connectors``
* What space does it actually fill?        -> ``occupancy``
* What space must stay empty around it?    -> ``clearance``
* Can a character walk through it?         -> ``apertures``
* Will collision seal the doorway?         -> ``collision``
* Where did it come from, legally?         -> ``provenance`` / ``license``
* Has any of this been checked?            -> ``validation``

Design rules, learned from the two source repositories:

1. **Derived, never asserted.** Every number here is measured from the solid at
   build time. World Printer Lab already did this for bounds; ModKit documented
   pivots in prose and they drifted. Prose drifts, measurements do not.
2. **Refuse rather than approximate.** A field that cannot be measured is
   absent and the asset's ``validation.status`` says so. There is no
   "probably 4 metres".
3. **Every tolerance is explicit.** "Nearly opposite" was a magic ``-0.965``
   buried in a snapping function; here it is ``mating_tolerance.angle_degrees``
   and it travels with the connector.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SCHEMA_ID = "tessera.asset/1"
CATALOG_SCHEMA_ID = "tessera.catalog/1"
LAYOUT_SCHEMA_ID = "tessera.layout/1"
REPORT_SCHEMA_ID = "tessera.report/1"

CONTRACT_VERSION = "1.0.0"


# --------------------------------------------------------------- vocabularies
#: Semantic role drives what a validator expects of an asset. A ``wall`` must
#: stand on something; a ``roof`` must be supported at wall height; a ``prop``
#: may sit anywhere it is grounded.
SEMANTIC_ROLES = (
    "foundation", "floor", "wall", "wall_opening", "corner", "door", "window",
    "roof", "roof_trim", "column", "beam", "stair", "railing", "prop",
    "ground", "road", "fixture", "character", "vehicle_part",
)

CATEGORIES = ("structure", "opening", "roof", "prop", "ground", "traversal")

#: Connector kinds. Two connectors mate only when their kinds are mutually
#: listed as compatible AND their scale classes match AND their normals oppose
#: within tolerance. Kind alone is never enough -- that was the bug that let
#: World Printer Lab snap a roof panel to a wheel hub.
CONNECTOR_KINDS = (
    "wall_edge",      # vertical seam between wall pieces
    "wall_base",      # bottom of a wall, mates with floor_top / foundation_top
    "wall_top",       # top of a wall, mates with roof_bearing
    "floor_edge",     # horizontal seam between floor slabs
    "floor_top",      # walkable surface
    "foundation_top",
    "roof_bearing",   # underside of a roof panel where it rests on a wall top
    "roof_ridge",     # apex seam between two roof panels
    "roof_edge",      # lateral seam between roof panels
    "opening_jamb",   # inside face of a door/window aperture
    "leaf_hinge",     # door/window leaf attachment
    "prop_base",
)

#: Explicit, symmetric compatibility table. Anything not listed does not mate.
CONNECTOR_COMPATIBILITY = {
    "wall_edge": ("wall_edge",),
    "wall_base": ("floor_top", "foundation_top"),
    "floor_top": ("wall_base", "prop_base"),
    "foundation_top": ("wall_base", "floor_edge", "prop_base"),
    "wall_top": ("roof_bearing",),
    "roof_bearing": ("wall_top",),
    "floor_edge": ("floor_edge", "foundation_top"),
    "roof_ridge": ("roof_ridge",),
    "roof_edge": ("roof_edge",),
    "opening_jamb": ("leaf_hinge",),
    "leaf_hinge": ("opening_jamb",),
    "prop_base": ("floor_top", "foundation_top"),
}


def compatible(kind_a: str, kind_b: str) -> bool:
    return kind_b in CONNECTOR_COMPATIBILITY.get(kind_a, ())


#: Scale classes are standards, not multipliers you may improvise. Two assets in
#: different classes never mate. Carried forward from World Printer Lab, which
#: got this right.
SCALE_CLASSES = {
    "mini": 0.5,
    "standard": 1.0,
    "mega": 2.0,
}


# ------------------------------------------------------------------ fragments
@dataclass
class Vec3:
    x: float
    y: float
    z: float

    @classmethod
    def of(cls, t):
        return cls(float(t[0]), float(t[1]), float(t[2]))

    def as_tuple(self):
        return (self.x, self.y, self.z)


@dataclass
class Bounds:
    """Axis-aligned bounds in the asset's own local space."""

    min: list
    max: list

    @classmethod
    def of(cls, b):
        return cls(min=[b[0], b[1], b[2]], max=[b[3], b[4], b[5]])

    def size(self):
        return [self.max[i] - self.min[i] for i in range(3)]


@dataclass
class MatingTolerance:
    """How far off a connection may be and still count as connected.

    ``position_metres`` is the maximum gap between two mated connector points.
    ``angle_degrees`` is the maximum deviation from perfectly opposed normals.
    ``roll_degrees`` is the maximum deviation between mated tangents, which is
    what stops a piece mating correctly but rotated 90 degrees about its own
    normal -- a failure mode neither source repository could detect.
    """

    position_metres: float = 0.001
    angle_degrees: float = 1.0
    roll_degrees: float = 1.0


@dataclass
class Connector:
    """A named attachment site with a full local frame.

    ``normal`` points *out* of the asset along the direction another piece
    approaches from. ``tangent`` fixes roll, so a mate is a complete rigid
    transform rather than a position plus an ambiguous spin.
    """

    id: str
    kind: str
    position: list           # local metres
    normal: list             # unit, points outward
    tangent: list            # unit, orthogonal to normal, fixes roll
    #: ``point``   -- the two connector points must coincide (seams, ridges).
    #: ``surface`` -- the two connector *planes* must coincide and the smaller
    #:               extent must lie inside the larger (a wall standing on a
    #:               floor). Neither source repository modelled this, which is
    #:               why "wall base mates floor top" had to be expressed as a
    #:               brittle point coincidence or not at all.
    mating_mode: str = "point"
    #: Half-extent in the (tangent, binormal) frame. Required for ``surface``.
    extent_half: list | None = None
    role: str = "generic"
    scale_class: str = "standard"
    compatible_kinds: list = field(default_factory=list)
    incompatible_kinds: list = field(default_factory=list)
    tolerance: MatingTolerance = field(default_factory=MatingTolerance)
    required: bool = False
    notes: str = ""

    def binormal(self):
        n, t = self.normal, self.tangent
        return [n[1] * t[2] - n[2] * t[1],
                n[2] * t[0] - n[0] * t[2],
                n[0] * t[1] - n[1] * t[0]]


@dataclass
class ApertureRecord:
    """A traversable or see-through hole, with the clear size that matters."""

    id: str
    kind: str
    bounds: Bounds
    traversal_axis: str          # "x" | "y" | "z"
    clear_width: float
    clear_height: float
    traversable: bool
    fits_capsule: dict = field(default_factory=dict)  # radius/height it admits


@dataclass
class MaterialSlot:
    slot: int
    name: str
    role: str
    base_color: list = field(default_factory=lambda: [0.7, 0.7, 0.7, 1.0])
    metallic: float = 0.0
    roughness: float = 0.8


@dataclass
class LodRecord:
    level: int
    triangles: int
    screen_size: float
    file: str | None = None
    generated_by: str = "none"


@dataclass
class Provenance:
    """Where every byte came from, and under what rights.

    Kept per asset rather than per repository because "the repo is CC0" is not
    an auditable statement -- "this mesh was generated by this script at this
    commit from no external input" is.
    """

    generator: str
    generator_version: str
    created_utc: str
    authored_by: str
    origin: str                      # "original-generated" | "original-authored" | "third-party"
    source_inputs: list = field(default_factory=list)
    generated_files: list = field(default_factory=list)
    derived_from: list = field(default_factory=list)
    third_party_review: str = "none-required"
    notes: str = ""


@dataclass
class LicenseRecord:
    code_spdx: str = "0BSD"
    assets_spdx: str = "CC0-1.0"
    applies_to: str = "assets"
    attribution_required: bool = False
    commercial_use: bool = True
    redistribution: bool = True


@dataclass
class ValidationRecord:
    status: str = "unvalidated"      # passed | failed | unvalidated
    validator_version: str = ""
    checked_utc: str = ""
    checks_passed: list = field(default_factory=list)
    checks_failed: list = field(default_factory=list)
    coverage: dict = field(default_factory=dict)


def to_jsonable(obj):
    """dataclass -> plain JSON types, dropping nothing."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, float):
        # keep catalogs byte-stable across platforms
        return round(obj, 6) + 0.0
    return obj
