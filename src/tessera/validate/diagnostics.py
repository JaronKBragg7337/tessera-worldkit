"""Diagnostics that are useful to a human *and* actionable by an agent.

SPDX-License-Identifier: 0BSD

The failure mode this repository exists to remove is an agent burning a
round-trip on "something looks wrong, let me render it and guess". A diagnostic
that says ``invalid placement`` costs exactly as much as no diagnostic at all.

So every diagnostic answers five questions, and where possible a sixth:

* ``what``     -- one sentence, no jargon
* ``where``    -- the instance, asset, connector and coordinates involved
* ``why``      -- the rule that was broken and the reasoning behind it
* ``expected`` -- the value the rule wanted
* ``actual``   -- the value it got
* ``fix``      -- the corrective action in words
* ``fix_transform`` -- the correction as data, when one exists

``fix_transform`` is the point. An agent that receives
``{"translate": [0, 0, -0.372]}`` does not need to render anything; it applies
the delta and re-runs the validator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class Diagnostic:
    code: str
    severity: str
    what: str
    where: dict = field(default_factory=dict)
    why: str = ""
    expected: object = None
    actual: object = None
    fix: str = ""
    fix_transform: dict | None = None
    rule: str = ""

    def to_dict(self):
        return asdict(self)

    def human(self) -> str:
        head = "%-7s %-32s %s" % (self.severity.upper(), self.code, self.what)
        lines = [head]
        loc = self.where.get("instance") or self.where.get("asset")
        detail = []
        if loc:
            detail.append("at %s" % loc)
        if self.where.get("position") is not None:
            detail.append("position %s" % _fmt(self.where["position"]))
        if self.where.get("connector"):
            detail.append("connector %s" % self.where["connector"])
        if detail:
            lines.append("          " + "  ".join(detail))
        if self.expected is not None or self.actual is not None:
            lines.append("          expected %s, got %s"
                         % (_fmt(self.expected), _fmt(self.actual)))
        if self.why:
            lines.append("          why: %s" % self.why)
        if self.fix:
            lines.append("          fix: %s" % self.fix)
        if self.fix_transform:
            lines.append("          apply: %s" % _fmt(self.fix_transform))
        return "\n".join(lines)


def _fmt(v):
    if isinstance(v, float):
        return "%.4f" % v
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join("%s: %s" % (k, _fmt(x)) for k, x in v.items()) + "}"
    return str(v)


class Collector:
    """Accumulates diagnostics and knows which checks it actually ran.

    Recording the checks that *passed* is what turns a report into a coverage
    statement. "No errors" is only meaningful alongside "and here are the
    nineteen rules that were evaluated".
    """

    def __init__(self):
        self.diagnostics = []
        self.checks_run = []
        self.checks_failed = set()

    def check(self, name):
        if name not in self.checks_run:
            self.checks_run.append(name)

    def add(self, diag: Diagnostic):
        self.diagnostics.append(diag)
        if diag.severity == ERROR:
            self.checks_failed.add(diag.rule or diag.code)

    def error(self, **kw):
        self.add(Diagnostic(severity=ERROR, **kw))

    def warn(self, **kw):
        self.add(Diagnostic(severity=WARNING, **kw))

    def info(self, **kw):
        self.add(Diagnostic(severity=INFO, **kw))

    @property
    def errors(self):
        return [d for d in self.diagnostics if d.severity == ERROR]

    @property
    def warnings(self):
        return [d for d in self.diagnostics if d.severity == WARNING]

    @property
    def ok(self) -> bool:
        return not self.errors
