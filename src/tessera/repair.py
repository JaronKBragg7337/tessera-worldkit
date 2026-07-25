"""Conservative, validator-driven layout repair.

SPDX-License-Identifier: 0BSD

This module does not invent fixes.  It only applies transforms the validator
already emitted as data, and it refuses an instance when two diagnostics
propose different corrections in the same pass.  That makes it useful as an
agent's hand without quietly turning it into a second placement solver.
"""
from __future__ import annotations

import copy

from .validate import build_report, validate_layout


def _translation_key(values):
    return tuple(round(float(v), 9) for v in values)


def apply_repair_pass(layout: dict, collector):
    """Apply one unambiguous translation per instance.

    Returns ``(new_layout, applied, skipped)``.  Diagnostics without an
    instance-addressed translation remain advice for the caller.
    """
    fixed = copy.deepcopy(layout)
    proposals = {}
    skipped = []

    for diag in collector.errors:
        target = (diag.where or {}).get("instance")
        transform = diag.fix_transform or {}
        translate = transform.get("translate")
        if not target or not isinstance(translate, (list, tuple)) \
                or len(translate) != 3:
            continue
        proposals.setdefault(target, []).append((diag.code, _translation_key(translate)))

    by_id = {item.get("id") or item.get("name"): item
             for item in fixed.get("instances", [])}
    applied = []
    for target, choices in sorted(proposals.items()):
        unique = {values for _, values in choices}
        if len(unique) != 1:
            skipped.append({
                "instance": target,
                "reason": "conflicting fix_transform translations",
                "diagnostics": [code for code, _ in choices],
            })
            continue
        instance = by_id.get(target)
        if not instance:
            skipped.append({"instance": target, "reason": "instance not found"})
            continue
        delta = next(iter(unique))
        position = instance.get("position", [0.0, 0.0, 0.0])
        instance["position"] = [
            round(float(position[i]) + delta[i], 9) + 0.0 for i in range(3)
        ]
        applied.append({
            "instance": target,
            "translate": list(delta),
            "diagnostics": [code for code, _ in choices],
        })
    return fixed, applied, skipped


def repair_layout(layout: dict, catalog: dict, max_passes: int = 5):
    """Repair to a fixed point, or stop when no proven improvement remains.

    A connector error can offer a transform for either end of a chain. Applying
    every offered delta at once can merely move the error into the next piece.
    Each candidate is therefore executed against a copy and revalidated. Only
    the candidate that strictly lowers the total error count is committed.
    """
    if max_passes < 1:
        raise ValueError("max_passes must be at least 1")

    current = copy.deepcopy(layout)
    history = []
    seen = set()
    for pass_number in range(1, max_passes + 1):
        collector = validate_layout(current, catalog)
        if collector.ok:
            report = build_report(
                collector, current.get("name", "layout"), "layout",
                {"connections": collector.connection_stats})
            summary = _summary("passed", history, report)
            return current, summary, report

        signature = repr([
            (item.get("id"), item.get("position"), item.get("rotation_degrees"),
             item.get("scale")) for item in current.get("instances", [])
        ])
        if signature in seen:
            break
        seen.add(signature)

        candidates = []
        skipped = []
        for diag in collector.errors:
            target = (diag.where or {}).get("instance")
            transform = diag.fix_transform or {}
            if not target or not transform:
                continue
            candidate = copy.deepcopy(current)
            instance = next(
                (item for item in candidate.get("instances", [])
                 if (item.get("id") or item.get("name")) == target), None)
            if instance is None or not _apply_transform(instance, transform):
                skipped.append({
                    "instance": target,
                    "diagnostic": diag.code,
                    "reason": "unsupported or unaddressable fix_transform",
                })
                continue
            result = validate_layout(candidate, catalog)
            if len(result.errors) < len(collector.errors):
                candidates.append((
                    len(result.errors), diag.code, target,
                    json_stable(transform), candidate, transform))

        candidates.sort(key=lambda item: item[:4])
        if candidates:
            _, code, target, _, next_layout, transform = candidates[0]
            applied = [{
                "instance": target,
                "transform": transform,
                "diagnostics": [code],
            }]
        else:
            next_layout, applied = current, []
        history.append({
            "pass": pass_number,
            "errors_before": len(collector.errors),
            "applied": applied,
            "skipped": skipped,
        })
        if not applied:
            break
        current = next_layout

    collector = validate_layout(current, catalog)
    report = build_report(
        collector, current.get("name", "layout"), "layout",
        {"connections": collector.connection_stats})
    return current, _summary("partial", history, report), report


def _apply_transform(instance, transform):
    if "translate" in transform:
        delta = transform["translate"]
        if not isinstance(delta, (list, tuple)) or len(delta) != 3:
            return False
        position = instance.get("position", [0.0, 0.0, 0.0])
        instance["position"] = [
            round(float(position[i]) + float(delta[i]), 9) + 0.0
            for i in range(3)
        ]
        return True
    if "set_rotation" in transform:
        value = transform["set_rotation"]
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            return False
        instance["rotation_degrees"] = [float(v) for v in value]
        return True
    if "rotate_z_by" in transform:
        rotation = list(instance.get("rotation_degrees", [0.0, 0.0, 0.0]))
        rotation[0] = (float(rotation[0]) + float(transform["rotate_z_by"])) % 360
        instance["rotation_degrees"] = rotation
        return True
    if "set_scale" in transform:
        instance["scale"] = float(transform["set_scale"])
        return True
    return False


def json_stable(value):
    """A deterministic ordering key without importing a heavier helper."""
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _summary(status, history, report):
    return {
        "schema": "tessera.repair/1",
        "status": status,
        "passes": len(history),
        "applied_count": sum(len(item["applied"]) for item in history),
        "remaining_errors": report["counts"]["errors"],
        "history": history,
    }
