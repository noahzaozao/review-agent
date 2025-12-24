#!/usr/bin/env python3
import argparse
import os
import sys
from typing import Optional

from review_agent.config import load_scan_config, resolve_loaded_config_path
from review_agent.report_md import render_markdown
from review_agent.scanner import scan_codebase


def _die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def cmd_scan(args: argparse.Namespace) -> int:
    root = args.path
    if not os.path.exists(root):
        _die(f"Path not found: {root}")
    root = os.path.abspath(root)

    loaded_config_path: Optional[str] = resolve_loaded_config_path(args.config)
    config = load_scan_config(root=root, config_path=args.config)

    summary = scan_codebase(config=config, config_path=loaded_config_path)
    md = render_markdown(summary)

    out_path = os.path.abspath(args.out)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
            f.write("\n")
    except Exception as e:
        _die(f"Cannot write report to {out_path}: {e}")

    if not args.quiet:
        # Short stdout summary (no per-line comments)
        total_hits = sum(summary.rule_occurrences.values())
        print("== AI Review (offline baseline) ==")
        print(f"root: {summary.root}")
        print(f"config: {summary.config_path or '(built-in defaults)'}")
        print(f"scanned_py_files: {summary.scanned_files}")
        print(f"pruned_dirs: {getattr(summary, 'pruned_dirs', 0)}")
        print(f"read_errors: {summary.read_errors}")
        print(f"total_hits: {total_hits}")
        print(f"report: {out_path}")
        print("")
        print("Top rules by occurrences:")
        for rid, occ in sorted(summary.rule_occurrences.items(), key=lambda x: (-x[1], x[0]))[:5]:
            if occ <= 0:
                continue
            print(f"- {rid}: {occ} (files: {summary.rule_files.get(rid, 0)})")

    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai_review.py",
        description="Local, offline baseline risk scanner for Python 2.7 legacy codebases (text-only).",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan an entire codebase directory (not git diff).")
    scan.add_argument("path", help="Root directory to scan, e.g. .")
    scan.add_argument("--config", default=None, help="INI config path (default: ./ai_review.ini if present).")
    scan.add_argument("--out", default="ai_review_report.md", help="Output Markdown report path.")
    scan.add_argument("--quiet", action="store_true", help="Reduce stdout output (still writes report).")
    scan.set_defaults(func=cmd_scan)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())


