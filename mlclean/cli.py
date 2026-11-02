"""Command line interface: ``mlclean audit data.csv --target churn``."""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from mlclean import __version__, audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mlclean",
        description="ML-aware data quality audit for tabular files.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit_cmd = sub.add_parser("audit", help="audit a CSV or Parquet file")
    audit_cmd.add_argument("path", help="CSV or Parquet file to audit")
    audit_cmd.add_argument("--target", help="target/label column name")
    audit_cmd.add_argument(
        "--task", choices=["classification", "regression"], default=None
    )
    audit_cmd.add_argument(
        "--id-columns", default="", help="comma-separated identifier columns"
    )
    audit_cmd.add_argument("--json", metavar="PATH", help="also write a JSON report")
    audit_cmd.add_argument(
        "--markdown", metavar="PATH", help="also write a Markdown report"
    )
    audit_cmd.add_argument(
        "--fail-on",
        choices=["critical", "high", "medium", "low"],
        help="exit non-zero when an issue at or above this severity exists (for CI)",
    )

    args = parser.parse_args(argv)

    if args.path.endswith((".parquet", ".pq")):
        df = pd.read_parquet(args.path)
    else:
        df = pd.read_csv(args.path)

    report = audit(
        df,
        target=args.target,
        task=args.task,
        id_columns=[c for c in args.id_columns.split(",") if c],
    )
    report.show()
    if args.json:
        report.to_json(args.json)
    if args.markdown:
        report.to_markdown(args.markdown)

    if args.fail_on:
        from mlclean.issues import SEVERITY_ORDER

        limit = SEVERITY_ORDER.index(args.fail_on)
        worst = min(
            (SEVERITY_ORDER.index(i.severity) for i in report.issues),
            default=len(SEVERITY_ORDER),
        )
        if worst <= limit:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
