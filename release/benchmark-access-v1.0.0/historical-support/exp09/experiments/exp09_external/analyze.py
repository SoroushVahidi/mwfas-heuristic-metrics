"""Independent EXP09 graph-level quality comparison from frozen pilot records."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.exp09_external.independent_audit import check_dag, parse_dimacs, sha, weighted_identity


def ordering(path: Path, vertices: set[int]) -> list[int]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(vertices) or {int(r["Order"]) for r in rows} != set(range(len(vertices))):
        raise ValueError(f"incomplete ordering ranks in {path}")
    result = [int(r["Node ID"]) for r in sorted(rows, key=lambda r: int(r["Order"]))]
    if set(result) != vertices or len(set(result)) != len(vertices):
        raise ValueError(f"incomplete ordering vertices in {path}")
    return result


def objective(vertices: set[int], arcs, order: list[int]) -> int:
    ranks = {node: i for i, node in enumerate(order)}
    if not check_dag(vertices, arcs, ranks):
        raise ValueError("forward arcs are cyclic")
    return sum(w for u, v, w in arcs if ranks[u] >= ranks[v])


def analyze(config_path: Path, graphs: Path, external: Path, insertion: Path,
            prior_path: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("analysis output exists")
    config = json.loads(config_path.read_text())
    previous = json.loads(prior_path.read_text())
    external_audit = json.loads((external / "independent_validation_report.json").read_text())
    if external_audit["passed"] != 24 or external_audit["failed"]:
        raise ValueError("external independent audit incomplete")
    rows = []
    for item in config["instances"]:
        graph_id = item["instance_id"]
        if sha(graphs / item["graph_file"]) != item["dimacs_sha256"]:
            raise ValueError(f"{graph_id}: DIMACS identity mismatch")
        vertices, arcs = parse_dimacs(graphs / item["graph_file"])
        if weighted_identity(vertices, arcs) != item["graph_sha256"]:
            raise ValueError(f"{graph_id}: weighted graph identity mismatch")
        prior = previous[graph_id]["algorithms"]
        prior_best = min(x["min_objective"] for x in prior.values())
        external_scores = []
        external_times = []
        external_hashes = set()
        for seed in config["seeds"]:
            run_id = f"{graph_id}__s{seed}"
            record = json.loads((external / "runs" / f"{run_id}.json").read_text())
            if record["status"] != "PASS":
                raise ValueError(f"{run_id}: incomplete external result")
            external_scores.append(record["objective"])
            external_times.append(record["total_wall_seconds"])
            external_hashes.add(record["ordering_sha256"])
        insertion_scores = {}
        insertion_times = {}
        for method in ("lrta", "wmsf_l2"):
            run_id = f"{graph_id}__insertion_{method}"
            record = json.loads((insertion / "runs" / f"{run_id}.json").read_text())
            if record["status"] not in ("PASS", "CENSORED_DEADLINE"):
                raise ValueError(f"{run_id}: incomplete insertion result")
            order_file = insertion / "orders" / f"{run_id}.csv"
            saved_order = ordering(order_file, vertices)
            order_hash = hashlib.sha256(("\n".join(map(str, saved_order)) + "\n").encode()).hexdigest()
            if sha(order_file) != record["order_file_sha256"] or order_hash != record["ordering_sha256"] or \
                    objective(vertices, arcs, saved_order) != record["objective"]:
                raise ValueError(f"{run_id}: independent insertion order or objective mismatch")
            seed_file = insertion / "seed_orders" / f"{graph_id}__{method}.csv"
            if sha(seed_file) != record["seed_order_sha256"]:
                raise ValueError(f"{run_id}: seed order file hash mismatch")
            seed_order = ordering(seed_file, vertices)
            if objective(vertices, arcs, seed_order) != record["initial_objective"] or \
                    record["initial_objective"] != prior[method]["min_objective"] or \
                    record["objective"] > record["initial_objective"] or record["accepted_moves"] > 1000:
                raise ValueError(f"{run_id}: original seed objective mismatch")
            insertion_scores[method] = record["objective"]
            insertion_times[method] = record["total_wall_seconds"]
        best_external = min(external_scores)
        best_insertion = min(insertion_scores.values())
        best_verified = min(best_external, best_insertion, prior_best)
        exact = previous[graph_id].get("exact")
        rows.append({"instance_id": graph_id, "source_experiment": item["source_experiment"],
                     "family": item["family"], "n_vertices": item["n_vertices"],
                     "scc_count": item["scc_count"], "graph_sha256": item["graph_sha256"],
                     "external_scores": external_scores, "external_ordering_diversity": len(external_hashes),
                     "external_median_wall_seconds": statistics.median(external_times),
                     "insertion_scores": insertion_scores, "insertion_times": insertion_times,
                     "prior_algorithms": prior, "prior_best": prior_best, "best_verified": best_verified,
                     "external_best": best_external, "external_relative_to_prior_best":
                     (best_external - prior_best) / prior_best if prior_best else None,
                     "external_relative_to_best_verified":
                     (best_external - best_verified) / best_verified if best_verified else None,
                     "external_vs_insertion": "WIN" if best_external < best_insertion else
                     "TIE" if best_external == best_insertion else "LOSS",
                     "exact": exact,
                     "external_certified_relative_gap":
                     (best_external - exact["objective"]) / exact["objective"] if exact and exact["status"] == "CERTIFIED_OPTIMAL" and exact["objective"] else None})
    comparisons = {}
    for method in ("lrta", "wmsf_l2", "igraph_eades_weighted", "ipsns"):
        counts = Counter()
        for row in rows:
            baseline = row["prior_algorithms"].get(method)
            if baseline is None:
                counts["missing"] += 1
            else:
                value = row["external_best"]
                target = baseline["min_objective"]
                counts["win" if value < target else "tie" if value == target else "loss"] += 1
        comparisons[method] = dict(counts)
    relative = [row["external_relative_to_best_verified"] for row in rows]
    bootstrap_rng = random.Random(1909)
    bootstrap = sorted(statistics.median(bootstrap_rng.choices(relative, k=len(relative))) for _ in range(10000))
    summary = {"schema": "mwfas-exp09-pilot-analysis-v1", "graph_count": len(rows),
               "external_run_count": 24, "insertion_run_count": 24,
               "independently_validated_external": external_audit["passed"],
               "independently_validated_insertion": sum(len(row["insertion_scores"]) for row in rows),
               "external_vs_prior_best": dict(Counter("win" if row["external_best"] < row["prior_best"] else
                                                        "tie" if row["external_best"] == row["prior_best"] else "loss"
                                                        for row in rows)),
               "external_vs_insertion": dict(Counter(row["external_vs_insertion"] for row in rows)),
               "external_vs_best_verified": dict(Counter("win" if row["external_best"] < row["best_verified"] else
                                                         "tie" if row["external_best"] == row["best_verified"] else "loss"
                                                         for row in rows)),
               "external_vs_prior_methods": comparisons,
               "median_relative_to_prior_best": statistics.median(row["external_relative_to_prior_best"] for row in rows),
               "median_relative_to_best_verified": statistics.median(relative),
               "descriptive_graph_bootstrap_median_interval_95": [bootstrap[249], bootstrap[9749]],
               "uncertainty_scope": "resampling the 12 purposively selected graph units; not a population confidence interval",
               "rows": rows}
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("config", "graphs", "external", "insertion", "prior", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.config, args.graphs, args.external, args.insertion, args.prior, args.output)
    print(json.dumps({key: result[key] for key in ("graph_count", "external_vs_prior_best", "external_vs_insertion", "median_relative_to_prior_best")}, sort_keys=True))
