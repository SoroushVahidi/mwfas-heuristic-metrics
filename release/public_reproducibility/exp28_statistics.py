"""Accepted EXP28 integration statistics, unchanged computational functions.

The public replay supplies independently verified scans and frozen metadata.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path


def need(test: bool, message: str) -> None:
    if not test:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def number(value: str):
    return None if value == "" else int(value)


def main(private: Path, protocol_path: Path) -> dict:
    manifest = json.loads((private / "manifest.json").read_text())
    need(sha(protocol_path) == manifest["protocol_sha256"], "protocol does not match frozen source")
    protocol = json.loads(protocol_path.read_text())
    scans = {}
    event_count = 0
    boundary = 0
    selected_witnesses = 0
    for path in sorted(private.glob("graph-*.json")):
        data = json.loads(path.read_text())
        for scan in data["scans"]:
            tid = scan["task_id"]
            need(tid not in scans, "duplicate task scan")
            scans[tid] = scan
            event_count += scan["events_checked"]
            boundary += len(scan["boundary_disagreements"])
            selected_witnesses += scan["selected_witnesses_checked"]
    need(len(scans) == len(manifest["tasks"]) == 117 and event_count == 143241 and
         selected_witnesses == 160 and boundary == 0,
         "event scan incomplete or budget timestamp disputed")
    checkpoint = {r["task_id"]: r for r in rows(private / "task_inventory.csv")}
    budget_rows = rows(private / "budget_inventory.csv")
    need(len(budget_rows) == 234, "budget inventory count")
    budgets = {(r["task_id"], int(r["budget_seconds"])): r for r in budget_rows}
    need(len(budgets) == 234, "duplicate budget identity")
    publication_lags = []
    for task in manifest["tasks"]:
        tid = task["task_id"]
        need(tid in scans and tid in checkpoint, "task evidence missing")
        for budget in (30, 120) if task["graph_id"].startswith(("exp04_", "exp06_")) else (120, 300):
            row = budgets[(tid, budget)]
            need(number(row["objective"]) == scans[tid]["best"][str(budget)], "budget objective mismatch")
            need(row["original_task_status"] == checkpoint[tid]["status"], "status recoded")
            if scans[tid]["first"][str(budget)] is not None:
                lag = scans[tid]["first"][str(budget)] - float(row["first_valid_seconds"])
                need(lag >= 0, "event publication predates recorded event clock")
                publication_lags.append(lag)
    task_lookup = {(t["graph_id"], t["arm"], t["seed"]): t for t in manifest["tasks"]}
    comparisons = []
    for graph_id, cfg in protocol["graphs"].items():
        synthetic = graph_id.startswith(("exp04_", "exp06_"))
        for budget in (30, 120) if synthetic else (120, 300):
            ipsns = task_lookup[(graph_id, "ipsns", 1)]
            a = scans[ipsns["task_id"]]["best"][str(budget)]
            for comparator in ("xiong_single", "xiong_restarts", "lrta", "wmsf_l2", "weighted_eades",
                               "insertion_lrta", "insertion_wmsf_l2"):
                other = task_lookup[(graph_id, comparator, 1 if comparator.startswith("xiong") else None)]
                b = scans[other["task_id"]]["best"][str(budget)]
                outcome = "missing" if a is None or b is None else "win" if a < b else "loss" if a > b else "tie"
                comparisons.append({"cohort": "synthetic" if synthetic else "empirical", "graph_id": graph_id,
                                    "family": cfg["family"], "source_parent": cfg["source_parent"],
                                    "budget_seconds": budget, "comparator": comparator, "ipsns": a, "other": b,
                                    "outcome": outcome, "gain_pp": None if a is None or b is None else 100*(b-a)/cfg["total_weight"]})
    sealed_pairs = rows(private / "paired_inventory.csv")
    need(len(comparisons) == len(sealed_pairs) == 182, "pair count differs")
    sealed_lookup = {(r["graph_id"], int(r["budget_seconds"]), r["comparator"]): r for r in sealed_pairs}
    for row in comparisons:
        old = sealed_lookup[(row["graph_id"], row["budget_seconds"], row["comparator"])]
        need(row["ipsns"] == number(old["ipsns_objective"]) and row["other"] == number(old["comparator_objective"]) and
             row["outcome"] == old["outcome"], "sealed paired comparison differs")
        if row["gain_pp"] is not None:
            need(abs(row["gain_pp"] + 100*float(old["normalized_difference"])) < 1e-11,
                 "sealed normalized difference differs")
    groups = defaultdict(list)
    for row in comparisons:
        groups[(row["cohort"], row["budget_seconds"], row["comparator"])].append(row)
    sealed_summary = json.loads((private / "analysis_summary.json").read_text())
    need(sealed_summary["task_count"] == 117 and sealed_summary["graph_count"] == 13 and
         sealed_summary["budget_rows"] == 234 and sealed_summary["paired_rows"] == 182,
         "sealed analysis denominators differ")
    original_groups = {(r["cohort"], r["budget_seconds"], r["comparator"]): r for r in sealed_summary["summaries"]}
    report = []
    for (cohort, budget, comparator), group in sorted(groups.items()):
        gains = [r["gain_pp"] for r in group if r["gain_pp"] is not None]
        counts = Counter(r["outcome"] for r in group)
        original = original_groups[("real" if cohort == "empirical" else cohort, budget, comparator)]
        need(len(gains) == original["paired"] and counts["missing"] == original["missing"] and
             counts["win"] == original["wins"] and counts["tie"] == original["ties"] and
             counts["loss"] == original["losses"], "sealed summary counts differ")
        median = st.median(gains) if gains else None
        need(median is None or abs(median + 100*original["median_normalized_difference"]) < 1e-11,
             "sealed summary median differs")
        entry = {"cohort": cohort, "budget_seconds": budget, "comparator": comparator,
                 "graph_or_parent_units": len(group), "paired": len(gains), "missing": counts["missing"],
                 "wins": counts["win"], "ties": counts["tie"], "losses": counts["loss"],
                 "median_ipsns_gain_pp": median, "mean_ipsns_gain_pp": st.mean(gains) if gains else None}
        if cohort == "synthetic" and len(gains) >= 5:
            rng = random.Random(28)
            normalized = [-value / 100 for value in gains]
            draws = sorted(st.mean(rng.choices(normalized, k=len(normalized))) for _ in range(10000))
            need(all(abs(a - b) < 1e-12 for a, b in zip((draws[249], draws[9749]),
                     original["graph_bootstrap_mean_95_percentile"])),
                 "sealed topology-bootstrap interval differs")
            ci = [-100*draws[9749], -100*draws[249]]
            entry["topology_bootstrap_mean_gain_95_pp"] = ci
        report.append(entry)
    availability = []
    for cohort in ("synthetic", "empirical"):
        for arm in ("ipsns", "xiong_single", "xiong_restarts", "lrta", "wmsf_l2", "weighted_eades",
                    "insertion_lrta", "insertion_wmsf_l2"):
            tasks = [t for t in manifest["tasks"] if t["arm"] == arm and
                     (t["graph_id"].startswith(("exp04_", "exp06_")) == (cohort == "synthetic"))]
            small, large = ((30, 120) if cohort == "synthetic" else (120, 300))
            first = [scans[t["task_id"]]["first"][str(large)] for t in tasks]
            improvements = sum(scans[t["task_id"]]["best"][str(small)] is not None and
                               scans[t["task_id"]]["best"][str(large)] is not None and
                               scans[t["task_id"]]["best"][str(large)] < scans[t["task_id"]]["best"][str(small)]
                               for t in tasks)
            availability.append({"cohort": cohort, "arm": arm, "tasks": len(tasks),
                                 "pass": sum(checkpoint[t["task_id"]]["status"] == "PASS" for t in tasks),
                                 "timeout_with_valid_incumbent": sum(checkpoint[t["task_id"]]["status"] == "TIMEOUT" and
                                                                     scans[t["task_id"]]["best"][str(large)] is not None for t in tasks),
                                 "available_small": sum(scans[t["task_id"]]["best"][str(small)] is not None for t in tasks),
                                 "available_large": sum(scans[t["task_id"]]["best"][str(large)] is not None for t in tasks),
                                 "improved_after_small": improvements,
                                 "median_first_published_seconds": st.median(v for v in first if v is not None)})
    primary = [r for r in comparisons if r["comparator"] == "xiong_single"]
    paired_first_availability = []
    for cohort in ("synthetic", "empirical"):
        selected = [g for g in protocol["graphs"] if
                    (g.startswith(("exp04_", "exp06_")) == (cohort == "synthetic"))]
        horizon = "120" if cohort == "synthetic" else "300"
        for arm in ("ipsns", "xiong_single", "xiong_restarts"):
            times = [scans[task_lookup[(g, arm, 1)]["task_id"]]["first"][horizon] for g in selected]
            need(all(value is not None for value in times), "paired first-solution availability missing")
            paired_first_availability.append({"cohort": cohort, "arm": arm, "graph_or_parent_units": len(times),
                                              "median_first_published_seconds": st.median(times)})
    by_family = []
    for (family, budget), group in sorted(defaultdict(list, {
            key: [r for r in primary if (r["family"], r["budget_seconds"]) == key]
            for key in {(r["family"], r["budget_seconds"]) for r in primary}}).items()):
        vals = [r["gain_pp"] for r in group if r["gain_pp"] is not None]
        by_family.append({"family": family, "budget_seconds": budget, "paired": len(vals),
                          "wins": sum(r["outcome"] == "win" for r in group),
                          "ties": sum(r["outcome"] == "tie" for r in group),
                          "losses": sum(r["outcome"] == "loss" for r in group),
                          "median_ipsns_gain_pp": st.median(vals) if vals else None})
    return {"format": "exp28-independent-integration-summary-v1", "verification": "PASS",
            "source_manifest_sha256": sha(private / "manifest.json"),
            "recovery_provenance_sha256": sha(private / "recovery_provenance.json"),
            "recovery_audit_report_sha256": sha(private / "audit_report.json"),
            "recovery_seal_sha256": sha(private / "checksums.sha256"),
            "sealed_analysis_sha256": sha(private / "analysis_summary.json"),
            "audited_tasks": len(scans), "audited_events": event_count, "budget_boundary_disagreements": boundary,
            "selected_budget_order_witnesses_revalidated": selected_witnesses,
            "max_event_publication_lag_seconds": max(publication_lags),
            "budget_rows_checked": len(budgets), "paired_rows_checked": len(comparisons),
            "comparisons": report, "availability": availability,
            "paired_first_availability": paired_first_availability, "primary_by_family": by_family}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("private_scan_directory", type=Path)
    p.add_argument("frozen_protocol", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = main(args.private_scan_directory, args.frozen_protocol)
    if args.output:
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("verification", "audited_tasks", "audited_events",
                                                  "budget_boundary_disagreements", "budget_rows_checked", "paired_rows_checked")}, sort_keys=True))
