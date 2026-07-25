"""Wavefront OBJ + MTL. SPDX-License-Identifier: 0BSD

Kept because it is the one format every tool on earth can open, including a
text editor, which makes it the debugging format of last resort.
"""
from __future__ import annotations

import os


def write_obj(path, mesh, materials, name="asset"):
    mtl_path = os.path.splitext(path)[0] + ".mtl"
    with open(mtl_path, "w", encoding="utf-8", newline="\n") as fh:
        for m in materials:
            fh.write("newmtl %s\n" % m.name)
            fh.write("Kd %.4f %.4f %.4f\n" % tuple(m.base_color[:3]))
            fh.write("d %.4f\n" % m.base_color[3])
            fh.write("Ns %.2f\n\n" % max(1.0, (1.0 - m.roughness) * 400))
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Tessera %s\n" % name)
        fh.write("mtllib %s\n" % os.path.basename(mtl_path))
        fh.write("o %s\n" % name)
        for p in mesh.positions:
            fh.write("v %.6f %.6f %.6f\n" % p)
        normals = {}
        for n in mesh.tri_normal:
            if n not in normals:
                normals[n] = len(normals) + 1
                fh.write("vn %.6f %.6f %.6f\n" % n)
        current = None
        order = sorted(range(len(mesh.triangles)),
                       key=lambda i: mesh.tri_material[i])
        for ti in order:
            mat = mesh.tri_material[ti]
            if mat != current:
                fh.write("usemtl %s\n" % mat)
                current = mat
            a, b, c = mesh.triangles[ti]
            ni = normals[mesh.tri_normal[ti]]
            fh.write("f %d//%d %d//%d %d//%d\n"
                     % (a + 1, ni, b + 1, ni, c + 1, ni))
    return path
