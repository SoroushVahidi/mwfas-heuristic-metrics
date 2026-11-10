"""Independently validate EXP08 and summarize seed paths and convergence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments.exp08_seed_sensitivity.diagnostic import atomic, sha, validate_graph, validate_order


def signature(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def quantiles(values):
    data = sorted(values)
    return {"min": data[0], "median": statistics.median(data), "max": data[-1]}


def analyze(config_path: Path, graphs: Path, output: Path) -> dict:
    config = json.loads(config_path.read_text())
    manifest = json.loads((output / "run_manifest.json").read_text())
    if manifest["config_sha256"] != sha(config_path) or manifest["source_revision"] != config["source_revision"]:
        raise ValueError("run manifest identity mismatch")
    rows = []
    curves = []
    summaries = []
    for item in config["instances"]:
        graph = validate_graph(graphs / f"{item['instance_id']}.d", item)
        group = []
        for seed in config["seeds"]:
            run_id = f"{item['instance_id']}__s{seed}"
            record = json.loads((output / "runs" / f"{run_id}.json").read_text())
            if record["status"] != "COMPLETED":
                rows.append({"run_id": run_id, "status": record["status"]})
                continue
            if record["graph_sha256"] != item["graph_sha256"] or record["dimacs_sha256"] != item["dimacs_sha256"]:
                raise ValueError(f"{run_id}: graph identity")
            order_path = output / "orders" / f"{run_id}.csv"
            objective, order_hash = validate_order(order_path, graph, record["reported_final_objective"])
            if (sha(order_path) != record["order_file_sha256"] or
                    order_hash != record["final_ordering_identity_sha256"] or
                    objective != record["independent_objective"]):
                raise ValueError(f"{run_id}: independent order/hash/objective mismatch")
            if record["rng_seed_calls"] != [seed] or record["rng_draws"] != len(record["events"]):
                raise ValueError(f"{run_id}: RNG observation")
            if len(record["events"]) != config["iteration_budget"] or record["termination_reason"] != "iteration_budget":
                raise ValueError(f"{run_id}: unexpected early termination")
            if "cyclic_scc_sizes" in item and record["events"][0]["candidate_pool_size"] < 2:
                raise ValueError(f"{run_id}: initial eligible SCC pool too small")
            if sum(e["accepted_improvement"] for e in record["events"]) != record["algorithm_info"]["n_accepted"]:
                raise ValueError(f"{run_id}: accepted improvement mismatch")
            best = min(record["seed_objectives"])
            curves.append({"instance_id": item["instance_id"], "seed": seed, "iteration": 0,
                           "best_backward_weight": best})
            for event in record["events"]:
                best = event["incumbent_backward_weight"]
                curves.append({"instance_id": item["instance_id"], "seed": seed,
                               "iteration": event["iteration"], "best_backward_weight": best})
            for checkpoint in config["objective_checkpoints"]:
                if record["checkpoints"][str(checkpoint)]["best_backward_weight"] != next(
                        e["incumbent_backward_weight"] for e in record["events"] if e["iteration"] == checkpoint):
                    raise ValueError(f"{run_id}: objective checkpoint mismatch")
            group.append(record)
            rows.append({"run_id": run_id, "status": "COMPLETED", "objective": objective})
        if not group:
            continue
        path_signatures = [signature(r["events"]) for r in group]
        selection_signatures = [signature([e["chosen_scc_members_sha256"] for e in r["events"]]) for r in group]
        perturbation_signatures = [signature([(e["perturbation_addback_eids"], e["perturbation_remove_eids"])
                                            for e in r["events"]]) for r in group]
        candidate_signatures = [signature([e["candidate_backward_weight"] for e in r["events"]]) for r in group]
        first_divergence = next((iteration for iteration in range(1, config["iteration_budget"] + 1)
                                 if len({signature(r["events"][iteration - 1]) for r in group}) > 1), None)
        first_selection_divergence = next((iteration for iteration in range(1, config["iteration_budget"] + 1)
                                           if len({r["events"][iteration - 1]["chosen_scc_members_sha256"] for r in group}) > 1), None)
        summaries.append({"instance_id": item["instance_id"], "family": item["family"],
            "n_vertices": item["n_vertices"], "n_edges": item["n_edges"],
            "graph_sha256": item["graph_sha256"], "dimacs_sha256": item["dimacs_sha256"],
            "completed_seeds": len(group), "distinct_selection_paths": len(set(selection_signatures)),
            "distinct_perturbation_paths": len(set(perturbation_signatures)),
            "distinct_candidate_objective_paths": len(set(candidate_signatures)),
            "distinct_full_trajectories": len(set(path_signatures)),
            "first_trajectory_divergence_iteration": first_divergence,
            "first_selection_divergence_iteration": first_selection_divergence,
            "initial_scc_candidate_pool": group[0]["events"][0]["candidate_pool_size"],
            "max_scc_candidate_pool": max(e["candidate_pool_size"] for r in group for e in r["events"]),
            "distinct_final_objectives": len({r["independent_objective"] for r in group}),
            "distinct_final_orderings": len({r["final_ordering_identity_sha256"] for r in group}),
            "initial_objective": quantiles([min(r["seed_objectives"]) for r in group]),
            "checkpoint_10": quantiles([r["checkpoints"]["10"]["best_backward_weight"] for r in group]),
            "checkpoint_50": quantiles([r["checkpoints"]["50"]["best_backward_weight"] for r in group]),
            "accepted_improvements": quantiles([r["algorithm_info"]["n_accepted"] for r in group]),
            "first_improving_iteration": [next((e["iteration"] for e in r["events"] if e["accepted_improvement"]), None)
                                          for r in group],
            "initialization_seconds": quantiles([r["initialization_seconds"] for r in group]),
            "search_seconds": quantiles([r["search_seconds"] for r in group]),
            "total_algorithm_seconds": quantiles([r["total_algorithm_seconds"] for r in group])})
    with (output / "convergence.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["instance_id", "seed", "iteration", "best_backward_weight"])
        writer.writeheader()
        writer.writerows(curves)
    result = {"schema": "mwfas-exp08-seed-diagnostic-analysis-v1", "config_sha256": sha(config_path),
              "source_revision": config["source_revision"], "code_revision": manifest["code_revision"],
              "expected_runs": len(config["instances"]) * len(config["seeds"]),
              "statuses": dict(Counter(r["status"] for r in rows)),
              "independently_validated_completed": sum(r["status"] == "COMPLETED" for r in rows),
              "curve_rows": len(curves), "convergence_csv_sha256": sha(output / "convergence.csv"),
              "groups": summaries, "cpu_seconds": manifest.get("cpu_seconds"),
              "scope": "bounded, structurally selected diagnostic; graph and seed measurements are not a population sample"}
    atomic(output / "analysis.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.config, args.graphs, args.output), indent=2))
