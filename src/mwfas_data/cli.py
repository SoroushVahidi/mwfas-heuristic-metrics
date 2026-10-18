"""Small command-line interface for reproducible initial checks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ROOT
from .retrieval import fetch_release
from .validate import write_report


def main() -> None:
    parser = argparse.ArgumentParser(prog="mwfas-data")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="Retrieve all pinned release files into ignored cache")
    audit = sub.add_parser("audit", help="Run checks and write a machine-readable report")
    audit.add_argument("--output", type=Path, default=ROOT / "results/baseline_validation.json")
    args = parser.parse_args()
    if args.command == "fetch":
        print(json.dumps(fetch_release(), indent=2))
    elif args.command == "audit":
        report = write_report(args.output)
        print(json.dumps({"rows_loaded": report["rows_loaded"], "status_counts": {s: sum(x["status"] == s for x in report["checks"]) for s in ("PASS", "FAIL", "NOT_VERIFIABLE")}, "report": str(args.output)}, indent=2))
