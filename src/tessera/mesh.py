"""Surface extraction and mesh assembly.

SPDX-License-Identifier: 0BSD

Turning a :class:`~tessera.boxset.BoxSet` into a renderable surface is a purely
combinatorial problem once the boxes are disjoint.

For every axis-aligned plane in the solid, collect the rectangles of box faces
that sit on it. Boxes whose *minimum* lies on the plane put material on the
positive side; boxes whose *maximum* lies on it put material on the negative
side. A piece of that plane is a visible surface exactly when it has material on
one side and not the other -- a 2D rectangle-set difference. Regions with
material on both sides are internal and are dropped, which is what welds abutting
boxes into one watertight shell without any solver.

The rectangles are then greedy-merged to keep triangle counts low, and a
T-junction repair pass inserts the vertices that greedy merging would otherwise
leave dangling on a neighbouring edge, so the shell is genuinely closed rather
than merely appearing closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .boxset import BoxSet
from .units import QUANTUM, q

AXIS_NAMES = ("x", "y", "z")
#: For each axis, the two in-plane axes (u, v) in an order that makes
#: (u, v, axis) a right-handed frame.
PLANE_AXES = {0: (1, 2), 1: (2, 0), 2: (0, 1)}


# --------------------------------------------------------------------- 2D ops
def _grid_cells(rects_a, rects_b):
    """Cell decomposition of the union of two rectangle sets."""
    us = sorted({r[0] for r in rects_a + rects_b} | {r[2] for r in rects_a + rects_b})
    vs = sorted({r[1] for r in rects_a + rects_b} | {r[3] for r in rects_a + rects_b})
    return us, vs


def _mark(rects, us, vs):
    grid = [[False] * (len(vs) - 1) for _ in range(len(us) - 1)]
    for (u0, v0, u1, v1) in rects:
        for i in range(len(us) - 1):
            if us[i] < u0 - QUANTUM / 2 or us[i + 1] > u1 + QUANTUM / 2:
                continue
            for j in range(len(vs) - 1):
                if vs[j] < v0 - QUANTUM / 2 or vs[j + 1] > v1 + QUANTUM / 2:
                    continue
                grid[i][j] = True
    return grid


def rect_difference(rects_a, rects_b):
    """Rectangles covering ``union(A) - union(B)``, greedy-merged.

    Exact: both inputs are decomposed onto their shared coordinate lattice, so
    no sliver is lost and no region is double-counted.
    """
    if not rects_a:
        return []
    us, vs = _grid_cells(rects_a, rects_b)
    if len(us) < 2 or len(vs) < 2:
        return []
    a = _mark(rects_a, us, vs)
    b = _mark(rects_b, us, vs) if rects_b else [[False] * (len(vs) - 1) for _ in range(len(us) - 1)]
    keep = [[a[i][j] and not b[i][j] for j in range(len(vs) - 1)]
            for i in range(len(us) - 1)]
    return _greedy_merge(keep, us, vs)


def _greedy_merge(keep, us, vs):
    """Standard greedy meshing: grow right, then grow down."""
    ni, nj = len(us) - 1, len(vs) - 1
    used = [[False] * nj for _ in range(ni)]
    out = []
    for i in range(ni):
        for j in range(nj):
            if not keep[i][j] or used[i][j]:
                continue
            # grow along v
            j1 = j
            while j1 + 1 < nj and keep[i][j1 + 1] and not used[i][j1 + 1]:
                j1 += 1
            # grow along u while the whole span is free
            i1 = i
            while i1 + 1 < ni and all(
                keep[i1 + 1][jj] and not used[i1 + 1][jj] for jj in range(j, j1 + 1)
            ):
                i1 += 1
            for ii in range(i, i1 + 1):
                for jj in range(j, j1 + 1):
                    used[ii][jj] = True
            out.append((us[i], vs[j], us[i1 + 1], vs[j1 + 1]))
    return out


# ------------------------------------------------------------------ mesh type
@dataclass
class Mesh:
    """Flat-shaded, material-tagged triangle mesh in canonical space."""

    positions: list = field(default_factory=list)   # [(x, y, z), ...]
    triangles: list = field(default_factory=list)   # [(i0, i1, i2), ...]
    tri_material: list = field(default_factory=list)  # material slot name per tri
    tri_normal: list = field(default_factory=list)   # flat normal per tri

    _index: dict = field(default_factory=dict, repr=False)

    def vertex(self, p) -> int:
        key = (q(p[0]), q(p[1]), q(p[2]))
        idx = self._index.get(key)
        if idx is None:
            idx = len(self.positions)
            self.positions.append(key)
            self._index[key] = idx
        return idx

    def add_polygon(self, points, material, normal):
        """Triangulate a convex polygon without producing degenerate triangles.

        A rectangle carrying T-junction split points has collinear vertices on
        its edges. Fanning from a corner would emit zero-area triangles across
        those collinear runs and silently drop the split edges, reopening the
        shell. Fanning from the centroid instead keeps every boundary edge used
        exactly once and every triangle non-degenerate. Plain quads skip the
        extra vertex and split on a diagonal, which is the common case.
        """
        idx = [self.vertex(p) for p in points]
        clean = [idx[0]]
        for i in idx[1:]:
            if i != clean[-1]:
                clean.append(i)
        if len(clean) > 2 and clean[0] == clean[-1]:
            clean.pop()
        if len(clean) < 3:
            return

        def emit(a, b, c):
            pa, pb, pc = self.positions[a], self.positions[b], self.positions[c]
            u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
            v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
            cr = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                  u[0] * v[1] - u[1] * v[0])
            if (cr[0] ** 2 + cr[1] ** 2 + cr[2] ** 2) < (QUANTUM ** 2):
                return
            self.triangles.append((a, b, c))
            self.tri_material.append(material)
            self.tri_normal.append(normal)

        if len(clean) == 3:
            emit(clean[0], clean[1], clean[2])
            return
        if len(clean) == 4:
            emit(clean[0], clean[1], clean[2])
            emit(clean[0], clean[2], clean[3])
            return

        cx = sum(self.positions[i][0] for i in clean) / len(clean)
        cy = sum(self.positions[i][1] for i in clean) / len(clean)
        cz = sum(self.positions[i][2] for i in clean) / len(clean)
        centre = self.vertex((cx, cy, cz))
        for k in range(len(clean)):
            emit(centre, clean[k], clean[(k + 1) % len(clean)])

    # ------------------------------------------------------------- properties
    @property
    def triangle_count(self) -> int:
        return len(self.triangles)

    @property
    def vertex_count(self) -> int:
        return len(self.positions)

    def materials(self):
        seen = []
        for m in self.tri_material:
            if m not in seen:
                seen.append(m)
        return seen

    def bounds(self):
        xs = [p[0] for p in self.positions]
        ys = [p[1] for p in self.positions]
        zs = [p[2] for p in self.positions]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    def surface_area(self) -> float:
        total = 0.0
        for (a, b, c) in self.triangles:
            pa, pb, pc = self.positions[a], self.positions[b], self.positions[c]
            u = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
            v = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
            cr = (u[1] * v[2] - u[2] * v[1],
                  u[2] * v[0] - u[0] * v[2],
                  u[0] * v[1] - u[1] * v[0])
            total += 0.5 * (cr[0] ** 2 + cr[1] ** 2 + cr[2] ** 2) ** 0.5
        return total

    # --------------------------------------------------------------- topology
    def edge_manifold_report(self):
        """Every edge of a closed manifold surface is used by exactly 2 faces.

        Returns ``(non_manifold_edges, boundary_edges)``. A watertight shell has
        zero of both. This is the mesh-health property the validator asserts, so
        a generator change that punches a hole in a wall fails the build rather
        than shipping.
        """
        from collections import Counter
        counter = Counter()
        for (a, b, c) in self.triangles:
            for e in ((a, b), (b, c), (c, a)):
                counter[tuple(sorted(e))] += 1
        boundary = [e for e, n in counter.items() if n == 1]
        nonman = [e for e, n in counter.items() if n > 2]
        return nonman, boundary

    def is_watertight(self) -> bool:
        nonman, boundary = self.edge_manifold_report()
        return not nonman and not boundary

    def signed_volume(self) -> float:
        """Divergence-theorem volume. Positive means outward-facing winding."""
        total = 0.0
        for (a, b, c) in self.triangles:
            pa, pb, pc = self.positions[a], self.positions[b], self.positions[c]
            total += (
                pa[0] * (pb[1] * pc[2] - pb[2] * pc[1])
                - pa[1] * (pb[0] * pc[2] - pb[2] * pc[0])
                + pa[2] * (pb[0] * pc[1] - pb[1] * pc[0])
            ) / 6.0
        return total


# ------------------------------------------------------- boxset -> surface
def surface_from_boxset(solid: BoxSet, material="default") -> Mesh:
    """Extract the visible boundary of a disjoint box set."""
    mesh = Mesh()
    faces = []  # (axis, coord, rect, sign)

    for axis in range(3):
        u, v = PLANE_AXES[axis]
        planes = {}
        for b in solid.boxes:
            rect = (b[u], b[v], b[u + 3], b[v + 3])
            planes.setdefault(b[axis], {"pos": [], "neg": []})["pos"].append(rect)
            planes.setdefault(b[axis + 3], {"pos": [], "neg": []})["neg"].append(rect)

        for coord, sides in planes.items():
            # material on the +axis side of this plane
            plus = sides["pos"]
            # material on the -axis side of this plane
            minus = sides["neg"]
            for rect in rect_difference(minus, plus):
                faces.append((axis, coord, rect, +1))
            for rect in rect_difference(plus, minus):
                faces.append((axis, coord, rect, -1))

    _emit_faces(mesh, faces, material)
    return mesh


def _emit_faces(mesh: Mesh, faces, material):
    """Emit rectangles as polygons, repairing T-junctions on the way.

    Greedy merging leaves long edges abutting short ones, and two faces on
    *perpendicular* planes share an edge that must be split identically on both
    or the shell is only visually closed. So the break set is global per axis,
    not per plane: every rectangle edge is subdivided at every coordinate that
    any face uses on that axis. The cost is a handful of extra triangles; the
    gain is a genuinely two-manifold shell that every engine, physics cooker and
    lightmapper agrees is watertight.
    """
    breaks = {0: set(), 1: set(), 2: set()}
    for (axis, coord, rect, sign) in faces:
        u_ax, v_ax = PLANE_AXES[axis]
        breaks[u_ax].update((rect[0], rect[2]))
        breaks[v_ax].update((rect[1], rect[3]))
        breaks[axis].add(coord)

    sorted_breaks = {k: sorted(v) for k, v in breaks.items()}

    for (axis, coord, rect, sign) in faces:
        u_ax, v_ax = PLANE_AXES[axis]
        u0, v0, u1, v1 = rect
        us = [x for x in sorted_breaks[u_ax] if u0 <= x <= u1]
        vs = [x for x in sorted_breaks[v_ax] if v0 <= x <= v1]
        if us[0] > u0:
            us.insert(0, u0)
        if us[-1] < u1:
            us.append(u1)
        if vs[0] > v0:
            vs.insert(0, v0)
        if vs[-1] < v1:
            vs.append(v1)

        # walk the rectangle boundary counter-clockwise in (u, v) space, which
        # is outward-facing for sign +1 because (u, v, axis) is right-handed
        ring_uv = []
        ring_uv += [(x, v0) for x in us[:-1]]
        ring_uv += [(u1, y) for y in vs[:-1]]
        ring_uv += [(x, v1) for x in reversed(us[1:])]
        ring_uv += [(u0, y) for y in reversed(vs[1:])]

        normal = [0.0, 0.0, 0.0]
        normal[axis] = float(sign)
        if sign < 0:
            ring_uv = list(reversed(ring_uv))

        pts = []
        for (uu, vv) in ring_uv:
            p = [0.0, 0.0, 0.0]
            p[axis] = coord
            p[u_ax] = uu
            p[v_ax] = vv
            pts.append(tuple(p))
        mesh.add_polygon(pts, material, tuple(normal))


# ------------------------------------------------------------------- prisms
def _ear_clip(poly):
    """Triangulate a simple CCW polygon given as 2D points. Indices returned."""
    n = len(poly)
    idx = list(range(n))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if cross(a, b, c) <= 0:
                continue
            bad = False
            for m in idx:
                if m in (i0, i1, i2):
                    continue
                p = poly[m]
                if (cross(a, b, p) >= 0 and cross(b, c, p) >= 0
                        and cross(c, a, p) >= 0):
                    bad = True
                    break
            if bad:
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


def extrude_profile(profile, axis: int, a0: float, a1: float,
                    material="default", mesh: Mesh | None = None) -> Mesh:
    """Extrude a closed 2D profile along ``axis`` from ``a0`` to ``a1``.

    ``profile`` is a list of (u, v) points in the plane's right-handed
    (u, v) frame, wound counter-clockwise. This covers everything the box
    kernel cannot express exactly -- pitched roofs, ridge caps, chamfers --
    while still producing a closed shell.
    """
    mesh = mesh or Mesh()
    u_ax, v_ax = PLANE_AXES[axis]
    a0, a1 = q(min(a0, a1)), q(max(a0, a1))

    def point(uv, a):
        p = [0.0, 0.0, 0.0]
        p[axis] = a
        p[u_ax] = q(uv[0])
        p[v_ax] = q(uv[1])
        return tuple(p)

    # ensure CCW
    area = 0.0
    for i in range(len(profile)):
        x0, y0 = profile[i]
        x1, y1 = profile[(i + 1) % len(profile)]
        area += x0 * y1 - x1 * y0
    if area < 0:
        profile = list(reversed(profile))

    n = [0.0, 0.0, 0.0]
    n[axis] = 1.0
    neg = [0.0, 0.0, 0.0]
    neg[axis] = -1.0

    for (i0, i1, i2) in _ear_clip(profile):
        mesh.add_polygon([point(profile[i0], a1), point(profile[i1], a1),
                          point(profile[i2], a1)], material, tuple(n))
        mesh.add_polygon([point(profile[i2], a0), point(profile[i1], a0),
                          point(profile[i0], a0)], material, tuple(neg))

    for i in range(len(profile)):
        p0 = profile[i]
        p1 = profile[(i + 1) % len(profile)]
        du, dv = p1[0] - p0[0], p1[1] - p0[1]
        length = (du * du + dv * dv) ** 0.5 or 1.0
        sn = [0.0, 0.0, 0.0]
        sn[u_ax] = dv / length
        sn[v_ax] = -du / length
        mesh.add_polygon(
            [point(p0, a0), point(p1, a0), point(p1, a1), point(p0, a1)],
            material, tuple(sn),
        )
    return mesh
