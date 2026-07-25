"""Exact CSG on sets of axis-aligned boxes.

SPDX-License-Identifier: 0BSD

Why this kernel exists
----------------------
Both source repositories built architectural geometry as boolean unions and
differences of axis-aligned boxes. ModKit did it with Blender's EXACT boolean
solver, which meant the whole asset pipeline could only run inside Blender, was
slow, and could not be tested in CI.

An axis-aligned box difference has an exact, trivial closed form: the remainder
of ``a - b`` is at most six axis-aligned boxes. So a solid built only from
axis-aligned parts can be represented as a *set of pairwise-disjoint boxes*,
and every boolean is exact integer-lattice arithmetic with no mesh repair, no
solver, and no dependency.

That buys three things the source repos did not have:

1. The pipeline runs anywhere, including CI and an agent's sandbox.
2. ``occupancy`` is not an approximation of the mesh -- it *is* the solid. So
   "do these two placed assets intersect" is an exact test, not an AABB guess.
3. Every box removed by :meth:`BoxSet.subtract` is recorded as an *aperture*.
   That is what makes "is this doorway still walkable after collision is
   applied" an executable check rather than a warning in a README.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator

from .units import QUANTUM, q

Box = tuple  # (x0, y0, z0, x1, y1, z1), normalized and quantized


def box(p0, p1) -> Box:
    """Build a normalized, quantized box from two opposite corners."""
    lo = tuple(q(min(a, b)) for a, b in zip(p0, p1))
    hi = tuple(q(max(a, b)) for a, b in zip(p0, p1))
    for i in range(3):
        if hi[i] - lo[i] <= QUANTUM / 2:
            raise ValueError(
                "degenerate box: extent %g on axis %s is at or below the "
                "lattice quantum %g" % (hi[i] - lo[i], "xyz"[i], QUANTUM)
            )
    return (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])


def box_size(b: Box) -> tuple:
    return (b[3] - b[0], b[4] - b[1], b[5] - b[2])


def box_centre(b: Box) -> tuple:
    return ((b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2)


def box_volume(b: Box) -> float:
    sx, sy, sz = box_size(b)
    return sx * sy * sz


def boxes_overlap(a: Box, b: Box, gap: float = 0.0) -> bool:
    """True when the two boxes share interior volume.

    ``gap`` shrinks the test on every axis, so a positive ``gap`` ignores
    contact and slivers thinner than it.
    """
    for i in range(3):
        if a[i] >= b[i + 3] - gap or b[i] >= a[i + 3] - gap:
            return False
    return True


def overlap_box(a: Box, b: Box):
    """The shared region of two boxes, or None when they only touch."""
    lo = tuple(max(a[i], b[i]) for i in range(3))
    hi = tuple(min(a[i + 3], b[i + 3]) for i in range(3))
    if any(hi[i] - lo[i] <= QUANTUM / 2 for i in range(3)):
        return None
    return (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])


def split_box(target: Box, cutter: Box) -> list:
    """``target - cutter`` as up to six pairwise-disjoint boxes.

    The split is done axis by axis: first the two X slabs entirely outside the
    cutter, then within the shared X band the two Y slabs, then within the
    shared X and Y band the two Z slabs. Every emitted piece is disjoint from
    every other by construction, which is what keeps a :class:`BoxSet` a true
    partition rather than an overlapping soup.
    """
    if not boxes_overlap(target, cutter):
        return [target]
    ax0, ay0, az0, ax1, ay1, az1 = target
    bx0, by0, bz0, bx1, by1, bz1 = cutter

    out = []
    mx0, mx1 = max(ax0, bx0), min(ax1, bx1)
    if ax0 < mx0:
        out.append((ax0, ay0, az0, mx0, ay1, az1))
    if mx1 < ax1:
        out.append((mx1, ay0, az0, ax1, ay1, az1))

    my0, my1 = max(ay0, by0), min(ay1, by1)
    if ay0 < my0:
        out.append((mx0, ay0, az0, mx1, my0, az1))
    if my1 < ay1:
        out.append((mx0, my1, az0, mx1, ay1, az1))

    mz0, mz1 = max(az0, bz0), min(az1, bz1)
    if az0 < mz0:
        out.append((mx0, my0, az0, mx1, my1, mz0))
    if mz1 < az1:
        out.append((mx0, my0, mz1, mx1, my1, az1))

    return [b for b in out if all(b[i + 3] - b[i] > QUANTUM / 2 for i in range(3))]


@dataclass
class Aperture:
    """A hole that was deliberately cut through a solid.

    This is the single most useful thing the kernel records. An agent placing a
    doorway wall needs to know not just that the wall has a hole, but exactly
    where the hole is, which way you walk through it, and how big a character
    fits. Because apertures are captured at the moment of the cut, they can
    never drift out of sync with the geometry the way a hand-authored socket
    list does.
    """

    id: str
    kind: str  # door | window | hatch | vent | passage
    region: Box
    axis: int  # traversal axis index: 0=X, 1=Y, 2=Z
    traversable: bool = True

    def size(self):
        return box_size(self.region)

    def centre(self):
        return box_centre(self.region)


@dataclass
class BoxSet:
    """A solid held as pairwise-disjoint axis-aligned boxes."""

    boxes: list = field(default_factory=list)
    apertures: list = field(default_factory=list)

    # ------------------------------------------------------------ construction
    @classmethod
    def from_box(cls, p0, p1) -> "BoxSet":
        return cls(boxes=[box(p0, p1)])

    def copy(self) -> "BoxSet":
        return BoxSet(boxes=list(self.boxes), apertures=list(self.apertures))

    # ------------------------------------------------------------- operations
    def add(self, p0, p1) -> "BoxSet":
        """Union a box in, keeping the set disjoint."""
        b = box(p0, p1)
        kept = []
        for existing in self.boxes:
            kept.extend(split_box(existing, b))
        kept.append(b)
        self.boxes = kept
        return self

    def union(self, other: "BoxSet") -> "BoxSet":
        for b in other.boxes:
            self.add(b[:3], b[3:])
        self.apertures.extend(other.apertures)
        return self

    def subtract(self, p0, p1, aperture: Aperture | None = None) -> "BoxSet":
        """Difference a box out, optionally recording it as an aperture."""
        b = box(p0, p1)
        kept = []
        for existing in self.boxes:
            kept.extend(split_box(existing, b))
        self.boxes = kept
        if aperture is not None:
            self.apertures.append(aperture)
        return self

    def carve_aperture(self, ident: str, kind: str, p0, p1, axis: int,
                       traversable: bool = True) -> "BoxSet":
        """Cut a hole and remember it. Prefer this over :meth:`subtract`."""
        region = box(p0, p1)
        return self.subtract(
            region[:3], region[3:],
            Aperture(id=ident, kind=kind, region=region, axis=axis,
                     traversable=traversable),
        )

    def translate(self, offset) -> "BoxSet":
        dx, dy, dz = offset
        self.boxes = [
            (q(b[0] + dx), q(b[1] + dy), q(b[2] + dz),
             q(b[3] + dx), q(b[4] + dy), q(b[5] + dz))
            for b in self.boxes
        ]
        for ap in self.apertures:
            r = ap.region
            ap.region = (q(r[0] + dx), q(r[1] + dy), q(r[2] + dz),
                         q(r[3] + dx), q(r[4] + dy), q(r[5] + dz))
        return self

    # --------------------------------------------------------------- queries
    def is_empty(self) -> bool:
        return not self.boxes

    def bounds(self) -> Box:
        if not self.boxes:
            raise ValueError("empty solid has no bounds")
        lo = [min(b[i] for b in self.boxes) for i in range(3)]
        hi = [max(b[i + 3] for b in self.boxes) for i in range(3)]
        return (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])

    def volume(self) -> float:
        return sum(box_volume(b) for b in self.boxes)

    def intersects(self, other: "BoxSet", gap: float = 0.0) -> bool:
        for a in self.boxes:
            for b in other.boxes:
                if boxes_overlap(a, b, gap):
                    return True
        return False

    def intersection_volume(self, other: "BoxSet", gap: float = 0.0) -> float:
        """Exact shared volume. Used to distinguish a sliver from a real clash."""
        total = 0.0
        for a in self.boxes:
            for b in other.boxes:
                if not boxes_overlap(a, b, gap):
                    continue
                ov = overlap_box(a, b)
                if ov:
                    total += box_volume(ov)
        return total

    def contains_point(self, p) -> bool:
        for b in self.boxes:
            if all(b[i] <= p[i] <= b[i + 3] for i in range(3)):
                return True
        return False

    def is_disjoint(self) -> bool:
        """Invariant check: no two boxes in this set may share interior volume."""
        n = len(self.boxes)
        for i in range(n):
            for j in range(i + 1, n):
                if boxes_overlap(self.boxes[i], self.boxes[j]):
                    return False
        return True

    def __iter__(self) -> Iterator[Box]:
        return iter(self.boxes)

    def __len__(self) -> int:
        return len(self.boxes)


def boxset_from_boxes(boxes: Iterable[Box]) -> BoxSet:
    s = BoxSet()
    for b in boxes:
        s.add(b[:3], b[3:])
    return s
