"""Pure-Python glTF 2.0 binary writer.

SPDX-License-Identifier: 0BSD

No dependency, no Blender, no CLI tool. glTF is JSON plus a byte buffer, so
writing it directly is about two hundred lines and removes the single largest
constraint the source pack had: its exporter could only run inside Blender, so
the asset pipeline could not run in CI or in an agent's sandbox.

Output is flat-shaded (one normal per triangle, vertices split per face), which
matches how the kit is authored -- the shading comes from geometry, not maps.
"""
from __future__ import annotations

import json
import struct

from ..units import ENGINE_SPACES
from .uv import lightmap_uv1, planar_uv0

GLTF_FLOAT = 5126
GLTF_UINT = 5125
ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963


def _pad(data: bytes, alignment=4, fill=b"\x00") -> bytes:
    over = len(data) % alignment
    return data if over == 0 else data + fill * (alignment - over)


def build_gltf(mesh, materials, name="asset", space="three"):
    """Return ``(gltf_dict, binary_blob)`` for a single-node scene."""
    conv = ENGINE_SPACES[space]
    uv1 = lightmap_uv1(mesh)

    by_material = {}
    for ti, (tri, mat) in enumerate(zip(mesh.triangles, mesh.tri_material)):
        by_material.setdefault(mat, []).append(ti)

    mat_names = [m.name for m in materials]
    buffer = bytearray()
    views, accessors, primitives = [], [], []

    def add_view(data, target):
        nonlocal buffer
        offset = len(buffer)
        buffer += data
        buffer += b"\x00" * ((4 - len(buffer) % 4) % 4)
        views.append({"buffer": 0, "byteOffset": offset,
                      "byteLength": len(data), "target": target})
        return len(views) - 1

    def add_accessor(view, ctype, count, atype, mn=None, mx=None):
        acc = {"bufferView": view, "componentType": ctype,
               "count": count, "type": atype}
        if mn is not None:
            acc["min"], acc["max"] = mn, mx
        accessors.append(acc)
        return len(accessors) - 1

    for mat_name, tri_indices in by_material.items():
        pos, nor, t0, t1, idx = [], [], [], [], []
        for ti in tri_indices:
            tri = mesh.triangles[ti]
            n = mesh.tri_normal[ti]
            cn = conv.convert_direction(n)
            order = (0, 2, 1) if conv.flip_winding else (0, 1, 2)
            base = len(pos)
            for k in order:
                vi = tri[k]
                p = mesh.positions[vi]
                pos.append(conv.convert_point(p))
                nor.append(cn)
                t0.append(planar_uv0(p, n))
                uu, vv = uv1[ti][k]
                t1.append((uu, vv))
            idx.extend((base, base + 1, base + 2))

        pv = add_view(struct.pack("<%df" % (len(pos) * 3),
                                  *[c for p in pos for c in p]), ARRAY_BUFFER)
        nv = add_view(struct.pack("<%df" % (len(nor) * 3),
                                  *[c for p in nor for c in p]), ARRAY_BUFFER)
        t0v = add_view(struct.pack("<%df" % (len(t0) * 2),
                                   *[c for p in t0 for c in p]), ARRAY_BUFFER)
        t1v = add_view(struct.pack("<%df" % (len(t1) * 2),
                                   *[c for p in t1 for c in p]), ARRAY_BUFFER)
        iv = add_view(struct.pack("<%dI" % len(idx), *idx), ELEMENT_ARRAY_BUFFER)

        mn = [min(p[i] for p in pos) for i in range(3)]
        mx = [max(p[i] for p in pos) for i in range(3)]
        primitives.append({
            "attributes": {
                "POSITION": add_accessor(pv, GLTF_FLOAT, len(pos), "VEC3", mn, mx),
                "NORMAL": add_accessor(nv, GLTF_FLOAT, len(nor), "VEC3"),
                "TEXCOORD_0": add_accessor(t0v, GLTF_FLOAT, len(t0), "VEC2"),
                "TEXCOORD_1": add_accessor(t1v, GLTF_FLOAT, len(t1), "VEC2"),
            },
            "indices": add_accessor(iv, GLTF_UINT, len(idx), "SCALAR"),
            "material": mat_names.index(mat_name) if mat_name in mat_names else 0,
        })

    gltf = {
        "asset": {"version": "2.0", "generator": "tessera.export.glb"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": name}],
        "meshes": [{"name": name, "primitives": primitives}],
        "materials": [
            {
                "name": m.name,
                "doubleSided": False,
                "alphaMode": "BLEND" if m.base_color[3] < 1.0 else "OPAQUE",
                "pbrMetallicRoughness": {
                    "baseColorFactor": list(m.base_color),
                    "metallicFactor": m.metallic,
                    "roughnessFactor": m.roughness,
                },
            }
            for m in materials
        ],
        "bufferViews": views,
        "accessors": accessors,
        "buffers": [{"byteLength": len(buffer)}],
    }
    return gltf, bytes(buffer)


def write_glb(path, mesh, materials, name="asset", space="three"):
    gltf, blob = build_gltf(mesh, materials, name, space)
    json_chunk = _pad(json.dumps(gltf, separators=(",", ":")).encode("utf-8"),
                      4, b" ")
    bin_chunk = _pad(blob, 4)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(json_chunk), 0x4E4F534A))
        fh.write(json_chunk)
        fh.write(struct.pack("<II", len(bin_chunk), 0x004E4942))
        fh.write(bin_chunk)
    return total
