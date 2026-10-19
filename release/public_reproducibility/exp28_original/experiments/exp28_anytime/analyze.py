"""Fixed-budget descriptive analysis of independently audited EXP28 events.

This consumes the audit seal and does not import a heuristic objective function.
The graph, rather than a seed or event, is the independent synthetic unit.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from .audit import sha


def sealed(output: Path) -> dict:
    report = json.loads((output / "audit_report.json").read_text())
    if report["violations"] or report["audited"] != report["planned"]:
        raise ValueError("analysis requires a complete violation-free independent audit")
    for line in (output / "checksums.sha256").read_text().splitlines():
        expected, name = line.split("  ", 1)
        if sha(output / name) != expected:
            raise ValueError("audit seal changed: " + name)
    return json.loads((output / "manifest.json").read_text())


def analyze(output: Path) -> dict:
    manifest = sealed(output)
    protocol = json.loads(Path(manifest["protocol_path"]).read_text())
    rows = []
    for task in manifest["tasks"]:
        folder = output / "tasks" / task["task_id"]
        cp = json.loads((output / "checkpoints" / (task["task_id"] + ".json")).read_text())
        events = [json.loads(path.read_text()) for path in sorted(folder.glob("event_*.json"))]
        cfg = protocol["graphs"][task["graph_id"]]
        budgets = protocol["budget_schedule"]["synthetic_seconds" if task["graph_id"].startswith(("exp04_", "exp06_")) else "real_seconds"]
        for budget in budgets:
            eligible = [e for e in events if e["elapsed_seconds"] <= budget]
            best = min(eligible, key=lambda e: e["reported_objective"]) if eligible else None
            init = next((e for e in eligible if e.get("extra", {}).get("kind") == "complete_initializer"), None)
            rows.append({"graph_id": task["graph_id"], "graph_sha256": task["graph_sha256"],
                         "family": cfg["family"], "source_parent": cfg["source_parent"],
                         "total_weight": cfg["total_weight"], "budget_seconds": budget,
                         "arm": task["arm"], "seed": task["seed"], "task_id": task["task_id"],
                         "original_task_status": cp["status"],
                         "completed_by_budget": cp["status"] == "PASS" and cp["task_wall_seconds"] <= budget,
                         "objective": best["reported_objective"] if best else None,
                         "first_valid_seconds": eligible[0]["elapsed_seconds"] if eligible else None,
                         "time_to_best_seconds": best["elapsed_seconds"] if best else None,
                         "initializer_objective": init["reported_objective"] if init else None,
                         "valid_checkpoints_by_budget": len(eligible),
                         "task_wall_seconds": cp["task_wall_seconds"],
                         "child_cpu_seconds": cp["child_cpu_seconds"]})
    with (output / "budget_inventory.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    lookup = {(r["graph_id"], r["budget_seconds"], r["arm"], r["seed"]): r for r in rows}
    paired = []
    for gid, cfg in protocol["graphs"].items():
        budgets = protocol["budget_schedule"]["synthetic_seconds" if gid.startswith(("exp04_", "exp06_")) else "real_seconds"]
        for budget in budgets:
            ipsns = lookup[(gid, budget, "ipsns", 1)]
            for comparator in ("xiong_single", "xiong_restarts", "lrta", "wmsf_l2", "weighted_eades", "insertion_lrta", "insertion_wmsf_l2"):
                other = lookup[(gid, budget, comparator, 1 if comparator.startswith("xiong") else None)]
                a, b = ipsns["objective"], other["objective"]
                paired.append({"graph_id": gid, "family": cfg["family"], "source_parent": cfg["source_parent"],
                               "budget_seconds": budget, "comparator": comparator,
                               "ipsns_objective": a, "comparator_objective": b,
                               "outcome": "missing" if a is None or b is None else "win" if a < b else "loss" if a > b else "tie",
                               "normalized_difference": None if a is None or b is None else (a-b)/cfg["total_weight"],
                               "baseline_relative_improvement": None if a is None or b in (None, 0) else (b-a)/b})
    with (output / "paired_inventory.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paired[0]))
        writer.writeheader(); writer.writerows(paired)
    groups = defaultdict(list)
    for row in paired:
        cohort = "synthetic" if row["graph_id"].startswith(("exp04_", "exp06_")) else "real"
        groups[(cohort, row["budget_seconds"], row["comparator"])].append(row)
    summaries = []
    for (cohort, budget, comparator), group in sorted(groups.items()):
        values = [r["normalized_difference"] for r in group if r["normalized_difference"] is not None]
        summary = {"cohort": cohort, "budget_seconds": budget, "comparator": comparator,
                   "graph_units": len(group), "paired": len(values), "missing": len(group)-len(values),
                   "wins": sum(r["outcome"] == "win" for r in group),
                   "ties": sum(r["outcome"] == "tie" for r in group),
                   "losses": sum(r["outcome"] == "loss" for r in group),
                   "median_normalized_difference": statistics.median(values) if values else None,
                   "mean_normalized_difference": statistics.mean(values) if values else None}
        if cohort == "synthetic" and len(values) >= 5:
            rng = random.Random(28)
            boots = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(10000))
            summary["graph_bootstrap_mean_95_percentile"] = [boots[249], boots[9749]]
        summaries.append(summary)
    result = {"format": "exp28-fixed-budget-descriptive-v1", "task_count": len(manifest["tasks"]),
              "graph_count": len(protocol["graphs"]), "budget_rows": len(rows),
              "paired_rows": len(paired), "summaries": summaries,
              "uncertainty_unit": "synthetic graph topology; empirical parent comparisons descriptive",
              "interpretation_note": "A timeout with a valid predeadline ordering remains incomplete. Missing objectives are never imputed. Smaller budgets are extracted from saved timestamps of the same long-cap task."}
    (output / "analysis_summary.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True, type=Path)
    result = analyze(parser.parse_args().output)
    print(json.dumps({key: result[key] for key in ("task_count", "graph_count", "budget_rows", "paired_rows")}, sort_keys=True))
