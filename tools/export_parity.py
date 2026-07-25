"""Emit the fixtures and expected values the JavaScript adapter is tested against.

SPDX-License-Identifier: 0BSD

Cross-implementation parity is only meaningful if both sides are checked against
the same recorded ground truth. Python is the reference; this script writes what
it decided so ``node --test`` can hold JavaScript to it.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests", "fixtures"))

from broken_layouts import CASES  # noqa: E402
from tessera.catalog import load_catalog  # noqa: E402
from tessera.transform import Transform  # noqa: E402
from tessera.validate import validate_layout  # noqa: E402

#: Rules the JavaScript runtime port implements. Grid, rotation, scale and
#: connector policy stay in Python because they are build-time concerns.
JS_COVERED = {
    "TSR_LAYOUT_FLOATING", "TSR_LAYOUT_BURIED", "TSR_LAYOUT_UNSUPPORTED",
    "TSR_LAYOUT_INTERSECTION", "TSR_LAYOUT_APERTURE_BLOCKED",
    "TSR_LAYOUT_UNKNOWN_ASSET",
}


def main():
    catalog = load_catalog(os.path.join(ROOT, "build", "catalog.json"))
    with open(os.path.join(ROOT, "examples", "workshop_shell", "layout.json"),
              encoding="utf-8") as fh:
        layout = json.load(fh)

    out_dir = os.path.join(ROOT, "build", "fixtures")
    os.makedirs(out_dir, exist_ok=True)

    cases = {}
    for name, (mutate, code) in sorted(CASES.items()):
        broken = mutate(layout)
        with open(os.path.join(out_dir, name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(broken, fh, indent=2)
        collector = validate_layout(broken, catalog)
        cases[name] = {
            "code": code,
            "js_should_detect": code in JS_COVERED,
            "python_codes": sorted({d.code for d in collector.diagnostics}),
            "python_errors": len(collector.errors),
        }

    transforms = []
    for pos, rot, scale in [((0, 0, 0), (0, 0, 0), 1.0),
                            ((4, 0, 0.5), (90, 0, 0), 1.0),
                            ((12, 12, 3.5), (180, 0, 0), 1.0),
                            ((11.8, 8, 0.5), (270, 0, 0), 1.0),
                            ((1.4, 9.6, 0.5), (37, 0, 0), 1.0)]:
        t = Transform(position=pos, rotation=rot, scale=scale)
        transforms.append({
            "position": list(pos), "rotation": list(rot), "scale": scale,
            "input_point": [2.0, 0.1, 1.5],
            "expected_point": [round(v, 6) for v in t.point((2.0, 0.1, 1.5))],
            "input_direction": [1.0, 0.0, 0.0],
            "expected_direction": [round(v, 6) for v in t.direction((1.0, 0.0, 0.0))],
        })

    grounding = []
    index = {a["id"]: a for a in catalog["assets"]}
    for inst in layout["instances"]:
        rec = index[inst["asset"]]
        support = rec["placement"].get("support", {})
        datum = rec["dimensions"]["bounds"]["min"][2]
        if support.get("datum_connector"):
            for c in rec["connectors"]:
                if c["id"] == support["datum_connector"]:
                    datum = c["position"][2]
        grounding.append({
            "asset": inst["asset"],
            "surface_z": round(inst["position"][2] + datum, 6),
            "x": inst["position"][0], "y": inst["position"][1],
            "yaw": inst["rotation_degrees"][0],
            "expected_z": round(inst["position"][2], 6),
        })

    payload = {
        "generated_by": "tools/export_parity.py",
        "reference": "python",
        "js_covered_rules": sorted(JS_COVERED),
        "cases": cases,
        "transforms": transforms,
        "grounding": grounding[:20],
    }
    path = os.path.join(ROOT, "build", "parity-expected.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print("wrote %s (%d fixtures, %d transforms, %d grounding cases)"
          % (path, len(cases), len(transforms), len(payload["grounding"])))


if __name__ == "__main__":
    main()
