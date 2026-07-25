"""``tessera`` command line.

SPDX-License-Identifier: 0BSD

Designed to be driven by an agent as much as by a person: every command takes
``--json`` and every command's exit code is meaningful.

    0  everything passed
    1  validation found errors
    2  the command could not run (bad path, unknown kit)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

from .assemble import Builder
from .brief import build_brief, render_text, write_brief
from .catalog import build_catalog, load_catalog, write_catalog
from .handoff import TARGETS, write_handoff_pack
from .repair import repair_layout
from .validate import (
    Collector, build_report, render_terminal, validate_asset, validate_layout,
    write_report,
)

EXIT_OK, EXIT_INVALID, EXIT_ERROR = 0, 1, 2


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_kit(kit_dir):
    kit_dir = os.path.abspath(kit_dir)
    if kit_dir not in sys.path:
        sys.path.insert(0, kit_dir)
    config = _load_module(os.path.join(kit_dir, "config.py"), "config")
    parts = _load_module(os.path.join(kit_dir, "parts.py"), "parts")
    return config, parts


# ------------------------------------------------------------------ commands
def cmd_build(args):
    config, parts = _load_kit(args.kit)
    problems = config.validate()
    if problems:
        for p in problems:
            print("CONFIG ERROR %s: %s (expected %s, got %s)"
                  % (p["code"], p["message"], p["expected"], p["actual"]),
                  file=sys.stderr)
        return EXIT_ERROR
    os.makedirs(args.out, exist_ok=True)
    catalog = build_catalog(parts.PARTS, args.out, config.KIT_ID,
                            config.KIT_VERSION, config,
                            write_meshes=not args.no_meshes)
    path = os.path.join(args.out, "catalog.json")
    digest = write_catalog(catalog, path)
    if args.json:
        print(json.dumps({"catalog": path, "sha256": digest,
                          "assets": catalog["asset_count"],
                          "triangles": catalog["totals"]["triangles"]}))
    else:
        print("built %d assets, %d triangles -> %s"
              % (catalog["asset_count"], catalog["totals"]["triangles"], path))
        print("sha256 %s" % digest)
    return EXIT_OK


def cmd_validate(args):
    catalog = load_catalog(args.catalog)
    if args.layout:
        with open(args.layout, encoding="utf-8") as fh:
            layout = json.load(fh)
        collector = validate_layout(layout, catalog)
        report = build_report(collector, layout.get("name", args.layout), "layout",
                              {"connections": collector.connection_stats})
    else:
        collector = Collector()
        for asset in catalog["assets"]:
            validate_asset(asset, collector)
        report = build_report(collector, catalog["kit"]["id"], "catalog")

    if args.report:
        write_report(report, args.report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_terminal(report, colour=not args.no_colour))
    return EXIT_OK if report["status"] == "passed" else EXIT_INVALID


def cmd_catalog(args):
    catalog = load_catalog(args.catalog)
    if args.ids:
        for asset in catalog["assets"]:
            print(asset["id"])
        return EXIT_OK
    rows = []
    for a in catalog["assets"]:
        d = a["dimensions"]
        rows.append((a["id"], a["semantic_role"],
                     "%.2f x %.2f x %.2f" % tuple(d["size"]),
                     a["pivot"]["convention"],
                     len(a["connectors"]), len(a["apertures"]),
                     a["geometry"]["triangles"]))
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK
    w = max(len(r[0]) for r in rows)
    print("%-*s  %-13s  %-20s  %-28s %5s %4s %6s"
          % (w, "id", "role", "size (m)", "pivot", "conn", "ap", "tris"))
    for r in rows:
        print("%-*s  %-13s  %-20s  %-28s %5d %4d %6d" % (w, *r))
    return EXIT_OK


def cmd_describe(args):
    catalog = load_catalog(args.catalog)
    for asset in catalog["assets"]:
        if asset["id"] == args.asset or asset["id"].endswith("/" + args.asset):
            print(json.dumps(asset, indent=2))
            return EXIT_OK
    print("no asset matching %r; try `tessera catalog --ids`" % args.asset,
          file=sys.stderr)
    return EXIT_ERROR


def cmd_assemble(args):
    catalog = load_catalog(args.catalog)
    module = _load_module(args.script, "tessera_scene")
    builder = module.build(catalog)
    if not isinstance(builder, Builder):
        print("%s.build() must return a tessera.assemble.Builder" % args.script,
              file=sys.stderr)
        return EXIT_ERROR
    layout = builder.to_layout()
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(layout, fh, indent=2)
    print("wrote %s (%d instances)" % (args.out, layout["instance_count"]))
    return EXIT_OK


def cmd_brief(args):
    """Emit the context-budgeted digest a remote or mobile agent can afford."""
    catalog = load_catalog(args.catalog)
    brief = build_brief(catalog, include_notes=args.notes, selectors=args.only)
    if args.out:
        write_brief(brief, args.out)
    if args.format == "text":
        text = render_text(brief)
        print(text)
    elif getattr(args, "json", False) or args.format == "json":
        text = json.dumps(brief, separators=(",", ":"))
        print(text)
    if args.stats:
        full = len(json.dumps(catalog, separators=(",", ":")))
        compact = len(json.dumps(brief, separators=(",", ":")))
        rendered = len(render_text(brief))
        print(json.dumps({
            "full_catalog_chars": full,
            "brief_json_chars": compact,
            "brief_text_chars": rendered,
            "ratio_json": round(compact / full, 4),
            "ratio_text": round(rendered / full, 4),
            "approx_tokens_full": round(full / 3.6),
            "approx_tokens_brief_json": round(compact / 3.6),
            "approx_tokens_brief_text": round(rendered / 3.6),
        }, indent=2), file=sys.stderr)
    return EXIT_OK


def cmd_pack(args):
    """Package the smallest useful set of hands for the target environment."""
    catalog = load_catalog(args.catalog)
    layout = None
    if args.layout:
        with open(args.layout, encoding="utf-8") as fh:
            layout = json.load(fh)
    result = write_handoff_pack(
        catalog=catalog,
        target=args.target,
        out_path=args.out,
        repo_root=args.repo,
        prompt=args.prompt or "",
        selectors=args.only,
        layout=layout,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("packed %s handoff with %d asset(s) -> %s"
              % (args.target, result["asset_count"], args.out))
        print("fingerprint %s" % result["fingerprint"])
    return EXIT_OK


def cmd_repair(args):
    """Apply validator-supplied transforms until valid or no safe fix remains."""
    catalog = load_catalog(args.catalog)
    with open(args.layout, encoding="utf-8") as fh:
        layout = json.load(fh)
    repaired, summary, report = repair_layout(
        layout, catalog, max_passes=args.max_passes)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(repaired, fh, indent=2)
    if args.report:
        write_report(report, args.report)
    if args.json:
        print(json.dumps({**summary, "out": args.out}, indent=2))
    else:
        print("repair %s after %d pass(es): %d applied, %d remaining error(s)"
              % (summary["status"], summary["passes"],
                 summary["applied_count"], summary["remaining_errors"]))
        print("wrote %s" % args.out)
    return EXIT_OK if report["status"] == "passed" else EXIT_INVALID


def cmd_doctor(args):
    """Answer 'is this environment able to run Tessera at all'."""
    import platform
    facts = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "tessera_importable": True,
        "runtime_dependencies": [],
        "blender_required": False,
        "notes": ("The core pipeline is pure standard-library Python. Blender, "
                  "Unreal and Unity are optional consumers, not build "
                  "dependencies."),
    }
    print(json.dumps(facts, indent=2) if args.json
          else "\n".join("%-24s %s" % (k, v) for k, v in facts.items()))
    return EXIT_OK


def main(argv=None):
    p = argparse.ArgumentParser(prog="tessera",
                                description="AI-readable world-building framework")
    p.add_argument("--json", action="store_true", help="machine-readable output")

    # --json is accepted on either side of the subcommand. Insisting on one
    # position is a papercut that costs an agent a whole failed invocation, and
    # `tessera doctor --json` is the order a person writes without thinking.
    # SUPPRESS keeps the subparser from overwriting a flag given before the
    # subcommand with its own default.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true",
                        default=argparse.SUPPRESS,
                        help="machine-readable output")

    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", parents=[common],
                       help="generate meshes and the catalog")
    b.add_argument("--kit", default="kits/shell_v1")
    b.add_argument("--out", default="build")
    b.add_argument("--no-meshes", action="store_true")
    b.set_defaults(func=cmd_build)

    v = sub.add_parser("validate", parents=[common], help="validate a catalog or a layout")
    v.add_argument("--catalog", default="build/catalog.json")
    v.add_argument("--layout")
    v.add_argument("--report", help="write the machine-readable report here")
    v.add_argument("--no-colour", action="store_true")
    v.set_defaults(func=cmd_validate)

    c = sub.add_parser("catalog", parents=[common], help="list what is in the catalog")
    c.add_argument("--catalog", default="build/catalog.json")
    c.add_argument("--ids", action="store_true")
    c.set_defaults(func=cmd_catalog)

    d = sub.add_parser("describe", parents=[common], help="dump one asset's full contract")
    d.add_argument("asset")
    d.add_argument("--catalog", default="build/catalog.json")
    d.set_defaults(func=cmd_describe)

    a = sub.add_parser("assemble", parents=[common], help="run a scene script and write its layout")
    a.add_argument("script")
    a.add_argument("--catalog", default="build/catalog.json")
    a.add_argument("--out", default="layout.json")
    a.set_defaults(func=cmd_assemble)

    br = sub.add_parser("brief", parents=[common],
                        help="context-budgeted digest for a phone or remote agent")
    br.add_argument("--catalog", default="build/catalog.json")
    br.add_argument("--format", choices=["json", "text"], default="text")
    br.add_argument("--out", help="also write the JSON brief here")
    br.add_argument("--notes", action="store_true",
                    help="include per-asset prose notes (costs budget)")
    br.add_argument("--only", action="append",
                    help=("select roles or asset globs, comma-separated "
                          "(wall,id:roof.*)"))
    br.add_argument("--stats", action="store_true",
                    help="print size comparison to stderr")
    br.set_defaults(func=cmd_brief)

    pack = sub.add_parser("pack", parents=[common],
                          help="build a portable handoff for an AI environment")
    pack.add_argument("--catalog", default="build/catalog.json")
    pack.add_argument("--target", choices=sorted(TARGETS), default="chat")
    pack.add_argument("--only", action="append",
                      help="select roles or asset globs, comma-separated")
    pack.add_argument("--prompt", help="the task the receiving AI should perform")
    pack.add_argument("--layout", help="include a layout to validate or continue")
    pack.add_argument("--repo", default=".",
                      help="repository root used for sandbox source files")
    pack.add_argument("--out", default="tessera-handoff.zip")
    pack.set_defaults(func=cmd_pack)

    repair = sub.add_parser("repair", parents=[common],
                            help="apply unambiguous fix_transform corrections")
    repair.add_argument("--catalog", default="build/catalog.json")
    repair.add_argument("--layout", required=True)
    repair.add_argument("--out", default="repaired-layout.json")
    repair.add_argument("--report")
    repair.add_argument("--max-passes", type=int, default=5)
    repair.set_defaults(func=cmd_repair)

    doc = sub.add_parser("doctor", parents=[common], help="report what this environment can do")
    doc.set_defaults(func=cmd_doctor)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print("cannot open %s" % exc.filename, file=sys.stderr)
        return EXIT_ERROR
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
