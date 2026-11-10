"""Verify the frozen EXP09 comparator snapshot against immutable prior exports."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path

import pyarrow.parquet as pq


def verify(config_path: Path, snapshot_path: Path, sources_path: Path, exports: Path) -> int:
    config = json.loads(config_path.read_text())
    snapshot = json.loads(snapshot_path.read_text())
    sources = json.loads(sources_path.read_text())["exports"]
    assert {x["instance_id"] for x in config["instances"]} == set(snapshot)
    tables = {}
    for exp, metadata in sources.items():
        filename = Path(metadata["path"]).name
        local = exports / f"{exp.lower()}_{filename}"
        assert hashlib.sha256(local.read_bytes()).hexdigest() == metadata["sha256"]
        tables[exp] = pq.read_table(local).to_pylist()
        if "exact_path" in metadata:
            exact = exports / f"{exp.lower()}_{Path(metadata['exact_path']).name}"
            assert hashlib.sha256(exact.read_bytes()).hexdigest() == metadata["exact_sha256"]
            tables["EXP06_EXACT"] = pq.read_table(exact).to_pylist()
    count = 0
    for item in config["instances"]:
        graph_id = item["instance_id"]
        exp = item["source_experiment"]
        saved = snapshot[graph_id]
        assert saved["source_experiment"] == exp
        rows = [r for r in tables[exp] if r["instance_id"] == graph_id]
        assert rows and all(r["graph_sha256"] == item["graph_sha256"] for r in rows)
        methods = {r["algorithm"] for r in rows if r["algorithm"] != "ipsns"} | {"ipsns"}
        assert set(saved["algorithms"]) == methods
        for method in methods:
            selected = [r for r in rows if r["algorithm"] == method and
                        (method != "ipsns" or r["iteration_budget"] == (200 if exp == "EXP06" else 400))]
            assert selected
            assert all(r["status"] == "PASS" and r["ordering_valid"] and
                       r["objective_match"] and r["acyclicity_valid"] for r in selected)
            prior = saved["algorithms"][method]
            objectives = [r["objective_weight"] for r in selected]
            runtimes = [r["total_wall_seconds"] for r in selected]
            assert prior["n"] == len(selected)
            if method == "ipsns":
                assert prior["iteration_budget"] == (200 if exp == "EXP06" else 400)
            else:
                assert prior["iteration_budget"] is None
            for actual, expected in ((min(objectives), prior["min_objective"]),
                                     (statistics.median(objectives), prior["median_objective"]),
                                     (statistics.median(runtimes), prior["median_wall_seconds"])):
                assert math.isclose(actual, expected, rel_tol=0, abs_tol=1e-9), (graph_id, method, actual, expected)
            count += len(selected)
        if exp == "EXP06":
            exact = [r for r in tables["EXP06_EXACT"] if r["instance_id"] == graph_id and
                     r["algorithm"] == "scipy_highs_ordering_milp"]
            assert len(exact) == 1
            result = exact[0]
            assert result["status"] == "CERTIFIED_OPTIMAL" and result["ordering_valid"] and \
                result["objective_match"] and result["acyclicity_valid"]
            assert saved["exact"] == {"status": result["status"], "objective": result["objective_weight"],
                                      "lower_bound": result["lower_bound"]}
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("config", "snapshot", "sources", "exports"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(f"verified {verify(args.config, args.snapshot, args.sources, args.exports)} prior validated runs")
