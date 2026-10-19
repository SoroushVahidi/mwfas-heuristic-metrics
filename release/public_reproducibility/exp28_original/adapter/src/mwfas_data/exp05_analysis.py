"""Prespecified descriptive EXP05 comparisons with explicit source clustering."""
from __future__ import annotations

import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from .exp03 import atomic_json, write_parquet_atomic
from .exp05 import config


def _median(values):
    return statistics.median(values) if values else None


def _cluster_ci(units: list[dict], field: str, draws: int = 2000):
    groups = defaultdict(list)
    for unit in units:
        groups[unit["source_parent"]].append(unit[field])
    if len(groups) < 4:
        return None
    keys = sorted(groups)
    rng = random.Random(config()["bootstrap_seed"])
    samples = []
    for _ in range(draws):
        selected = [rng.choice(keys) for _ in keys]
        samples.append(statistics.mean(value for key in selected for value in groups[key]))
    samples.sort()
    return [samples[int(.025 * (draws - 1))], samples[int(.975 * (draws - 1))]]


def analyze(workdir: Path) -> dict:
    selection = json.loads((workdir / "selection.json").read_text())
    records = {}
    for path in (workdir / "runs").glob("*.json"):
        row = json.loads(path.read_text())
        if row["status"] == "PASS":
            records[row["run_id"]] = row
    paired = []
    units = []
    methods = ["lrta", "wmsf_l2", "igraph_eades_weighted", "insertion_lrta", "insertion_wmsf"]
    for instance in selection["instances"]:
        iid = instance["instance_id"]
        available = {m: records[f"{iid}__{m}"] for m in methods if f"{iid}__{m}" in records}
        ipsns = [r for r in records.values() if r["instance_id"] == iid and r["algorithm"] == "ipsns"]
        for budget in config()["ipsns_iteration_budgets"]:
            values = [r for r in ipsns if r["iteration_budget"] == budget]
            if len(values) == len(config()["ipsns_seeds"]):
                available[f"ipsns_b{budget}"] = {
                    "objective_weight": statistics.mean(r["objective_weight"] for r in values),
                    "total_wall_seconds": statistics.mean(r["total_wall_seconds"] for r in values)}
        for left in methods + [f"ipsns_b{b}" for b in config()["ipsns_iteration_budgets"]]:
            for right in methods + [f"ipsns_b{b}" for b in config()["ipsns_iteration_budgets"]]:
                if left >= right or left not in available or right not in available:
                    continue
                a, b = available[left], available[right]
                delta = a["objective_weight"] - b["objective_weight"]
                paired.append({"instance_id": iid, "source_parent": instance["source_parent"],
                    "source_category": instance["source_category"], "left": left, "right": right,
                    "n_vertices": instance["n_vertices"], "n_edges": instance["n_edges"],
                    "density": instance["density"], "cyclic_scc_count": instance["cyclic_scc_count"],
                    "largest_scc_fraction": instance["largest_scc_size"] / instance["n_vertices"],
                    "in_degree_cv": instance["in_degree_cv"], "out_degree_cv": instance["out_degree_cv"],
                    "scc_stratum": "multiple_cyclic" if instance["cyclic_scc_count"] > 1 else "single_or_none",
                    "size_stratum": "small_1_49" if instance["n_vertices"] <= 49 else "medium_50_999" if instance["n_vertices"] <= 999 else "large_1000_plus",
                    "degree_heterogeneity_stratum": "high_cv_ge_1" if max(instance["in_degree_cv"], instance["out_degree_cv"]) >= 1 else "lower_cv_lt_1",
                    "delta_backward_weight_left_minus_right": delta,
                    "relative_delta_total_weight": delta / instance["total_graph_weight"],
                    "outcome": "left_strict_win" if delta < -1e-7 else "right_strict_win" if delta > 1e-7 else "tie",
                    "left_seconds": a["total_wall_seconds"], "right_seconds": b["total_wall_seconds"]})
        if all(f"{iid}__{m}" in records for m in ("lrta", "wmsf_l2")):
            initial = min(records[f"{iid}__lrta"]["objective_weight"], records[f"{iid}__wmsf_l2"]["objective_weight"])
            for row in ipsns:
                units.append({"instance_id": iid, "source_parent": instance["source_parent"],
                    "source_category": instance["source_category"], "budget": row["iteration_budget"],
                    "seed": row["seed"], "initial_objective": initial, "final_objective": row["objective_weight"],
                    "relative_improvement": (initial - row["objective_weight"]) / initial if initial else None,
                    "iterations_executed": row["info"]["n_iters"],
                    "first_improving_iteration": row["info"]["first_improving_iteration"],
                    "last_improving_iteration": row["info"]["best_iter"],
                    "multi_eligible_iterations": row["info"]["multi_eligible_iterations"],
                    "initialization_seconds": row["info"]["initialization_seconds"],
                    "refinement_seconds": row["algorithm_wall_seconds"] - row["info"]["initialization_seconds"],
                    "total_seconds": row["total_wall_seconds"], "time_to_best_after_initialization": row["info"]["time_to_best"]})
    write_parquet_atomic(workdir / "paired_comparisons.parquet", paired)
    grouped = defaultdict(list)
    for row in paired:
        for stratum_name in ("source_category", "scc_stratum", "size_stratum", "degree_heterogeneity_stratum"):
            grouped[(stratum_name, row[stratum_name], row["left"], row["right"])].append(row)
    comparisons = []
    for (stratum_name, stratum_value, left, right), values in sorted(grouped.items()):
        comparisons.append({"stratum_name": stratum_name, "stratum_value": stratum_value, "left": left, "right": right,
            "instances": len(values), "source_parents": len({v["source_parent"] for v in values}),
            "left_strict_wins": sum(v["outcome"] == "left_strict_win" for v in values),
            "ties": sum(v["outcome"] == "tie" for v in values),
            "right_strict_wins": sum(v["outcome"] == "right_strict_win" for v in values),
            "median_relative_delta_total_weight": _median([v["relative_delta_total_weight"] for v in values]),
            "source_cluster_bootstrap_mean_ci": _cluster_ci(values, "relative_delta_total_weight")})
    seed_groups = defaultdict(list)
    for row in units:
        seed_groups[(row["instance_id"], row["budget"])].append(row)
    seed_differences = [{"instance_id": iid, "budget": budget, "seeds": len(values),
        "distinct_final_objectives": len({v["final_objective"] for v in values}),
        "distinct_trace_hashes": len({json.dumps(records[f"{iid}__ipsns_b{budget:03d}_s{v['seed']}"]["info"]["selection_trace"], sort_keys=True) for v in values})}
        for (iid, budget), values in seed_groups.items()]
    instance_map = {item["instance_id"]: item for item in selection["instances"]}
    budget_units = []
    for (iid, budget), values in seed_groups.items():
        if len(values) != len(config()["ipsns_seeds"]):
            continue
        budget_units.append({"instance_id": iid, "source_parent": instance_map[iid]["source_parent"],
            "source_category": instance_map[iid]["source_category"], "budget": budget,
            "mean_final_objective": statistics.mean(v["final_objective"] for v in values),
            "mean_relative_improvement": statistics.mean(v["relative_improvement"] or 0 for v in values),
            "mean_total_seconds": statistics.mean(v["total_seconds"] for v in values),
            "mean_iterations_executed": statistics.mean(v["iterations_executed"] for v in values),
            "all_seeds_identical_objective": len({v["final_objective"] for v in values}) == 1,
            "any_multi_eligible_iteration": any(v["multi_eligible_iterations"] > 0 for v in values)})
    budget_groups = defaultdict(list)
    for unit in budget_units:
        budget_groups[(unit["source_category"], unit["budget"])].append(unit)
    budget_summary = [{"source_category": category, "budget": budget,
        "instances_with_three_valid_seeds": len(values),
        "source_parents": len({v["source_parent"] for v in values}),
        "median_relative_improvement_over_initial": _median([v["mean_relative_improvement"] for v in values]),
        "median_total_seconds": _median([v["mean_total_seconds"] for v in values]),
        "median_actual_iterations": _median([v["mean_iterations_executed"] for v in values]),
        "instances_identical_seed_objective": sum(v["all_seeds_identical_objective"] for v in values),
        "instances_with_multi_eligible_scc": sum(v["any_multi_eligible_iteration"] for v in values)}
        for (category, budget), values in sorted(budget_groups.items())]
    result = {"status": "COMPLETE" if len(records) == len(selection["instances"]) * 20 else "PARTIAL",
              "validated_runs_analyzed": len(records), "source_parent_count": len({x["source_parent"] for x in selection["instances"]}),
              "comparisons": comparisons, "budget_summary": budget_summary, "seed_path_diagnostics": seed_differences,
              "inferential_note": "Source-cluster intervals omitted if fewer than four independent source parents; repeated seeds, budgets, subgraphs, matrices are not independent primary units."}
    atomic_json(workdir / "analysis.json", result)
    return result
