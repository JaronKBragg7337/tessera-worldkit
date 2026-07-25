"""Units, axes and coordinate conventions for Tessera.

SPDX-License-Identifier: 0BSD

Tessera has exactly one canonical space. Everything in a catalog, a layout or a
report is expressed in it, and every engine adapter converts at the boundary.

Canonical space
---------------
* Handedness : right-handed
* Up axis    : +Z
* Forward    : +Y
* Right      : +X
* Linear unit: metre
* Angle unit : degree (layouts), radians never appear in serialized data
* Rotation   : intrinsic Z-Y-X Euler applied as yaw(Z) -> pitch(Y) -> roll(X)

Why this one: it matches Blender and glTF-after-conversion, it is right-handed
so cross products behave, and +Z up means "grounded" is always ``min z``. Engine
conversions are pure data and live in ``ENGINE_SPACES`` so an adapter can never
invent its own.
"""
from __future__ import annotations

from dataclasses import dataclass

CANONICAL_SPACE = "tessera.space/1"

UP = (0.0, 0.0, 1.0)
FORWARD = (0.0, 1.0, 0.0)
RIGHT = (1.0, 0.0, 0.0)
GROUND_AXIS = 2  # index into (x, y, z) that "grounded" is measured on

LINEAR_UNIT = "metre"
ANGLE_UNIT = "degree"

#: Coordinates are snapped to this lattice before any comparison. 1 micrometre
#: is far below any meaningful modelling tolerance and far above float64 noise,
#: so CSG results are exactly reproducible across machines and Python versions.
QUANTUM = 1e-6

#: Distance under which two surfaces are considered touching rather than
#: separated or overlapping. 0.5 mm.
CONTACT_EPSILON = 5e-4


def q(value: float) -> float:
    """Snap a scalar to the canonical lattice.

    Determinism matters more than precision here: two runs of the same build on
    different hardware must produce byte-identical catalogs, so every coordinate
    that enters the kernel passes through this function.
    """
    return round(float(value) / QUANTUM) * QUANTUM


def qv(vec) -> tuple:
    return tuple(q(v) for v in vec)


@dataclass(frozen=True)
class EngineSpace:
    """How a target engine differs from canonical space.

    ``linear_scale`` converts a canonical metre into the engine's linear unit.
    ``axis_map`` says which canonical axis feeds each engine axis, with a sign.
    ``handedness`` is informational but drives the winding-order flip.
    """

    engine: str
    linear_unit: str
    linear_scale: float
    up_axis: str
    forward_axis: str
    handedness: str
    axis_map: tuple  # ((src_index, sign), ...) for engine (x, y, z)
    flip_winding: bool
    notes: str = ""

    def convert_point(self, p):
        return tuple(
            p[src] * sign * self.linear_scale for (src, sign) in self.axis_map
        )

    def convert_direction(self, d):
        return tuple(d[src] * sign for (src, sign) in self.axis_map)


ENGINE_SPACES = {
    # Blender is canonical: right-handed, Z-up, metres. Nothing to do.
    "blender": EngineSpace(
        engine="blender",
        linear_unit="metre",
        linear_scale=1.0,
        up_axis="+Z",
        forward_axis="+Y",
        handedness="right",
        axis_map=((0, 1), (1, 1), (2, 1)),
        flip_winding=False,
        notes="Identity. Blender is the canonical space.",
    ),
    # Unreal is Z-up but LEFT-handed with +X forward and +Y right, and works in
    # centimetres. The classic failure is importing at scale 1.0 and getting a
    # 4 m wall that is 4 cm tall, or mirroring the kit by ignoring handedness.
    "unreal": EngineSpace(
        engine="unreal",
        linear_unit="centimetre",
        linear_scale=100.0,
        up_axis="+Z",
        forward_axis="+X",
        handedness="left",
        axis_map=((1, 1), (0, 1), (2, 1)),
        flip_winding=True,
        notes=(
            "Canonical +Y forward becomes Unreal +X forward. Handedness flips "
            "via the X/Y swap, so no extra mirror is needed; winding is "
            "reversed to keep normals outward."
        ),
    ),
    # Unity is Y-up, left-handed, +Z forward, metres.
    "unity": EngineSpace(
        engine="unity",
        linear_unit="metre",
        linear_scale=1.0,
        up_axis="+Y",
        forward_axis="+Z",
        handedness="left",
        axis_map=((0, 1), (2, 1), (1, 1)),
        flip_winding=True,
        notes="Canonical Z-up becomes Unity Y-up; canonical +Y forward becomes +Z.",
    ),
    # glTF / three.js: Y-up, right-handed, -Z forward, metres.
    "three": EngineSpace(
        engine="three",
        linear_unit="metre",
        linear_scale=1.0,
        up_axis="+Y",
        forward_axis="-Z",
        handedness="right",
        axis_map=((0, 1), (2, 1), (1, -1)),
        flip_winding=False,
        notes=(
            "glTF convention. Canonical +Y forward maps to -Z, which keeps the "
            "space right-handed, so winding is unchanged."
        ),
    ),
}
