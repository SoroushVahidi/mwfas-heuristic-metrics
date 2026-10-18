"""Run bounded upstream algorithms on an independent three-node graph."""
import argparse
import json
from pathlib import Path

from mwfas_data.config import ROOT
from mwfas_data.experiment import run_once

parser = argparse.ArgumentParser()
parser.add_argument("--source", required=True, type=Path, help="checkout at configured source revision")
parser.add_argument("--graph", type=Path, default=ROOT / "tests/fixtures/triangle.dimacs")
parser.add_argument("--output", type=Path, default=ROOT / "results/exp01_smoke")
args = parser.parse_args()
results = [run_once(args.source, args.graph, algorithm, args.output, iterations=5, timeout=30)
           for algorithm in ("lrta", "wmsf", "ipsns", "exact")]
print(json.dumps([{"algorithm": x["algorithm"], "status": x["status"],
                   "objective_weight": x.get("objective_weight"),
                   "acyclicity_valid": x.get("acyclicity_valid"), "error": x.get("error")}
                  for x in results], indent=2))
if any(x["status"] != "PASS" for x in results):
    raise SystemExit(1)
