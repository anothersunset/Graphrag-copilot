"""CLI: ``python -m graphrag_eval.bench``."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .report import render_markdown
from .runner import run_bench


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the v3.2 Provenance benchmark and emit a markdown report.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the report to this file. If omitted, write to stdout.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any KPI does not pass.",
    )
    args = parser.parse_args(argv)

    report = run_bench()
    md = render_markdown(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(md)

    if args.strict and not report.all_kpis_pass():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
