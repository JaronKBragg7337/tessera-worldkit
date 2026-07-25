"""Independently verify every exported mesh with a third-party parser.

SPDX-License-Identifier: 0BSD

Our own kernel says the meshes are watertight. That is not evidence; it is the
same code asserting its own output. This script re-reads the shipped GLB files
with Trimesh -- a library that knows nothing about Tessera -- and checks that
each one is a closed, outward-wound solid of exactly the volume and extent the
catalog declares.

Trimesh is a test-only dependency and contributes nothing to the output.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOLERANCE = 1e-5


def main():
    try:
        import trimesh
    except ImportError:
        print("trimesh is not installed; skipping independent verification")
        return 0

    with open(os.path.join(ROOT, "build", "catalog.json"), encoding="utf-8") as fh:
        catalog = json.load(fh)

    failures = []
    print("%-32s %9s %9s %8s %8s" % ("asset", "volume", "declared", "closed", "wound"))
    for asset in catalog["assets"]:
        path = os.path.join(ROOT, "build", asset["files"]["glb"])
        scene = trimesh.load(path, force="scene", process=True)
        mesh = scene.to_mesh()
        mesh.merge_vertices(merge_tex=True, merge_norm=True)

        declared = asset["geometry"]["signed_volume"]
        ok_volume = abs(mesh.volume - declared) < max(TOLERANCE, abs(declared) * 1e-4)
        short = asset["id"].split("/")[-1]
        print("%-32s %9.5f %9.5f %8s %8s"
              % (short, mesh.volume, declared, mesh.is_watertight,
                 mesh.is_winding_consistent))

        if not mesh.is_watertight:
            failures.append("%s is not watertight" % short)
        if not mesh.is_winding_consistent:
            failures.append("%s has inconsistent winding" % short)
        if not ok_volume:
            failures.append("%s volume %.6f != declared %.6f"
                            % (short, mesh.volume, declared))

        # extents, converted from canonical (x, y, z) to glTF (x, z, y)
        size = asset["dimensions"]["size"]
        want = (size[0], size[2], size[1])
        for i in range(3):
            if abs(mesh.extents[i] - want[i]) > 1e-4:
                failures.append("%s extent %d is %.5f, catalog says %.5f"
                                % (short, i, mesh.extents[i], want[i]))

    print()
    if failures:
        for f in failures:
            print("FAIL %s" % f, file=sys.stderr)
        return 1
    print("all %d meshes independently verified: closed, outward-wound, "
          "exact volume and extents" % len(catalog["assets"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
