"""Instance transforms.

SPDX-License-Identifier: 0BSD

Rotation is ZYX-intrinsic Euler in degrees, because that is what every layout
file and every engine inspector shows a human, and because quaternions in a
hand-edited JSON file are a reliable source of silent error.

Modular pieces declare ``allowed_rotations`` in 90-degree steps. That is not a
stylistic restriction -- at 90-degree steps an axis-aligned box stays axis
aligned under rotation, so occupancy, collision and aperture tests stay *exact*.
Off-axis rotation falls back to a conservative bounding box and the validator
says so rather than quietly losing precision.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .units import q


def _rot_matrix(rz, ry, rx):
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    return (
        (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
        (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
        (-sy,     cy * sx,                cy * cx),
    )


@dataclass
class Transform:
    position: tuple = (0.0, 0.0, 0.0)
    #: (yaw about Z, pitch about Y, roll about X), degrees
    rotation: tuple = (0.0, 0.0, 0.0)
    scale: float = 1.0
    matrix: tuple = field(init=False, repr=False)

    def __post_init__(self):
        self.matrix = _rot_matrix(*self.rotation)

    # --------------------------------------------------------------- queries
    def is_axis_aligned(self) -> bool:
        return all(abs((r % 90.0)) < 1e-6 or abs((r % 90.0) - 90.0) < 1e-6
                   for r in self.rotation)

    def is_uniform(self) -> bool:
        return True  # scale is a scalar by construction

    # ------------------------------------------------------------- operations
    def point(self, p):
        m = self.matrix
        s = self.scale
        x, y, z = p[0] * s, p[1] * s, p[2] * s
        return (
            q(m[0][0] * x + m[0][1] * y + m[0][2] * z + self.position[0]),
            q(m[1][0] * x + m[1][1] * y + m[1][2] * z + self.position[1]),
            q(m[2][0] * x + m[2][1] * y + m[2][2] * z + self.position[2]),
        )

    def direction(self, d):
        m = self.matrix
        out = (
            m[0][0] * d[0] + m[0][1] * d[1] + m[0][2] * d[2],
            m[1][0] * d[0] + m[1][1] * d[1] + m[1][2] * d[2],
            m[2][0] * d[0] + m[2][1] * d[1] + m[2][2] * d[2],
        )
        n = math.sqrt(sum(c * c for c in out)) or 1.0
        return tuple(round(c / n, 9) + 0.0 for c in out)

    def box(self, b):
        """Transform an axis-aligned box.

        Exact when the rotation is axis aligned; otherwise the returned box is
        the conservative AABB of the rotated corners. Callers that care read
        :meth:`is_axis_aligned` and downgrade their claim accordingly.
        """
        corners = [
            (b[0] if i & 1 else b[3],
             b[1] if i & 2 else b[4],
             b[2] if i & 4 else b[5])
            for i in range(8)
        ]
        pts = [self.point(c) for c in corners]
        return (
            min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts),
        )

    def boxes(self, boxes):
        return [self.box(b) for b in boxes]

    def to_dict(self):
        return {"position": list(self.position),
                "rotation_degrees": list(self.rotation),
                "scale": self.scale}

    @classmethod
    def from_dict(cls, d):
        return cls(
            position=tuple(d.get("position", (0, 0, 0))),
            rotation=tuple(d.get("rotation_degrees", (0, 0, 0))),
            scale=float(d.get("scale", 1.0)),
        )
