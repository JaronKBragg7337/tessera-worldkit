"""Report rendering: one report, two readers.

SPDX-License-Identifier: 0BSD
"""
from __future__ import annotations

import json

from ..contract import REPORT_SCHEMA_ID
from ..measure import utcnow
from .asset import VALIDATOR_VERSION


def build_report(collector, subject, subject_kind="layout", extra=None):
    diags = [d.to_dict() for d in collector.diagnostics]
    by_code = {}
    for d in diags:
        by_code[d["code"]] = by_code.get(d["code"], 0) + 1
    return {
        "schema": REPORT_SCHEMA_ID,
        "validator_version": VALIDATOR_VERSION,
        "generated_utc": utcnow(),
        "subject": subject,
        "subject_kind": subject_kind,
        "status": "passed" if collector.ok else "failed",
        "counts": {
            "errors": len(collector.errors),
            "warnings": len(collector.warnings),
            "info": len(diags) - len(collector.errors) - len(collector.warnings),
        },
        "coverage": {
            "checks_run": collector.checks_run,
            "checks_run_count": len(collector.checks_run),
            "rules_failed": sorted(collector.checks_failed),
        },
        "by_code": by_code,
        "diagnostics": diags,
        **(extra or {}),
    }


def write_report(report, path):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report, fh, indent=2)
    return path


BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
DIM = "\033[2m"
RESET = "\033[0m"


def render_terminal(report, colour=True) -> str:
    def paint(text, code):
        return "%s%s%s" % (code, text, RESET) if colour else text

    lines = []
    status = report["status"]
    head = "%s  %s" % (report["subject_kind"], report["subject"])
    lines.append(paint("Tessera validation  ", BOLD) + head)
    lines.append("")

    order = {"error": 0, "warning": 1, "info": 2}
    for d in sorted(report["diagnostics"], key=lambda x: order.get(x["severity"], 3)):
        colour_code = {"error": RED, "warning": YELLOW}.get(d["severity"], DIM)
        first = "%-7s %-36s %s" % (d["severity"].upper(), d["code"], d["what"])
        lines.append(paint(first, colour_code))
        w = d.get("where") or {}
        bits = []
        for key in ("instance", "asset", "other_instance", "connector",
                    "other_connector", "aperture", "support", "field", "axis"):
            if w.get(key):
                bits.append("%s=%s" % (key, w[key]))
        if w.get("position"):
            bits.append("position=%s" % _num(w["position"]))
        if bits:
            lines.append("        " + paint(" ".join(bits), DIM))
        if d.get("expected") is not None or d.get("actual") is not None:
            lines.append("        expected %s   actual %s"
                         % (_num(d.get("expected")), _num(d.get("actual"))))
        if d.get("why"):
            lines.append("        " + paint("why  " + d["why"], DIM))
        if d.get("fix"):
            lines.append("        fix  " + d["fix"])
        if d.get("fix_transform"):
            lines.append("        " + paint("apply " + json.dumps(d["fix_transform"]), DIM))
        lines.append("")

    c = report["counts"]
    cov = report["coverage"]
    summary = ("%d error(s), %d warning(s), %d note(s) across %d checks"
               % (c["errors"], c["warnings"], c["info"], cov["checks_run_count"]))
    lines.append(paint(summary, BOLD))
    if status == "passed":
        lines.append(paint("PASSED", GREEN))
    else:
        lines.append(paint("FAILED  rules: %s" % ", ".join(cov["rules_failed"]), RED))
    return "\n".join(lines)


def _num(v):
    if isinstance(v, float):
        return "%.4f" % v
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_num(x) for x in v) + "]"
    return str(v)
