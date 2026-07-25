"""UV generation.

SPDX-License-Identifier: 0BSD

Two channels, both derived, both with a property a test can assert.

UV0 -- world-space planar projection at a fixed metres-per-repeat. This is
ModKit's best late-stage discovery, carried forward: if every asset is unwrapped
into its own 0-1 square, a tiling material appears at a different scale on a
wall than on a crate and the kit stops reading as a kit. Fixing texel density in
*world* space means one material looks identical everywhere. UVs run outside 0-1
on anything larger than the tile, which is correct for tiling and trim-sheet
workflows.

UV1 -- a packed, non-overlapping unwrap for lightmaps and AO bakes. Charts are
coplanar face groups, scaled by true world area so texel density is uniform
there too, then shelf-packed. Unreal can generate its own at import; this exists
so Unity, Godot and three.js get a usable channel without doing the work.
"""
from __future__ import annotations

import math

TILE_METRES = 2.0
LIGHTMAP_MARGIN = 0.01


def _basis(normal):
    """Orthonormal (u, v) basis for a plane with the given normal."""
    n = normal
    ref = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = (n[1] * ref[2] - n[2] * ref[1],
         n[2] * ref[0] - n[0] * ref[2],
         n[0] * ref[1] - n[1] * ref[0])
    ln = math.sqrt(sum(c * c for c in u)) or 1.0
    u = tuple(c / ln for c in u)
    v = (n[1] * u[2] - n[2] * u[1],
         n[2] * u[0] - n[0] * u[2],
         n[0] * u[1] - n[1] * u[0])
    return u, v


def planar_uv0(position, normal, tile_metres=TILE_METRES):
    """Dominant-axis planar projection at a fixed world scale."""
    ax = max(range(3), key=lambda i: abs(normal[i]))
    if ax == 0:
        u, v = position[1], position[2]
    elif ax == 1:
        u, v = position[0], position[2]
    else:
        u, v = position[0], position[1]
    return (u / tile_metres, v / tile_metres)


def lightmap_uv1(mesh, margin=LIGHTMAP_MARGIN):
    """Non-overlapping packed UVs, one chart per coplanar face group.

    Returns ``{triangle_index: [(u, v), (u, v), (u, v)]}``.
    """
    charts = {}
    for ti, (tri, n) in enumerate(zip(mesh.triangles, mesh.tri_normal)):
        p0 = mesh.positions[tri[0]]
        d = round(n[0] * p0[0] + n[1] * p0[1] + n[2] * p0[2], 4)
        key = (round(n[0], 3), round(n[1], 3), round(n[2], 3), d)
        charts.setdefault(key, []).append(ti)

    boxes = []
    for key, tris in charts.items():
        n = key[:3]
        bu, bv = _basis(n)
        pts = {}
        for ti in tris:
            for vi in mesh.triangles[ti]:
                p = mesh.positions[vi]
                pts[vi] = (p[0] * bu[0] + p[1] * bu[1] + p[2] * bu[2],
                           p[0] * bv[0] + p[1] * bv[1] + p[2] * bv[2])
        us = [c[0] for c in pts.values()]
        vs = [c[1] for c in pts.values()]
        boxes.append({
            "key": key, "tris": tris, "pts": pts,
            "u0": min(us), "v0": min(vs),
            "w": max(us) - min(us), "h": max(vs) - min(vs),
        })

    # scale everything by one global factor so texel density stays uniform
    total_area = sum((b["w"] + margin) * (b["h"] + margin) for b in boxes) or 1.0
    scale = math.sqrt(0.82 / total_area)
    for b in boxes:
        b["sw"] = b["w"] * scale + margin
        b["sh"] = b["h"] * scale + margin

    boxes.sort(key=lambda b: -b["sh"])
    x = y = shelf_h = 0.0
    for b in boxes:
        if x + b["sw"] > 1.0:
            x = 0.0
            y += shelf_h
            shelf_h = 0.0
        b["px"], b["py"] = x, y
        x += b["sw"]
        shelf_h = max(shelf_h, b["sh"])
    used_height = y + shelf_h
    squeeze = min(1.0, 1.0 / used_height) if used_height > 1.0 else 1.0

    out = {}
    for b in boxes:
        for ti in b["tris"]:
            uvs = []
            for vi in mesh.triangles[ti]:
                pu, pv = b["pts"][vi]
                uu = (b["px"] + (pu - b["u0"]) * scale + margin / 2) * squeeze
                vv = (b["py"] + (pv - b["v0"]) * scale + margin / 2) * squeeze
                uvs.append((uu, vv))
            out[ti] = uvs
    return out
