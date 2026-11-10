"""Build and verify the metadata-only EXP10 final review package.

Build reads local copies of the frozen Wulver metadata and the JSON emitted by
final_review.py. Verify needs only the committed package and never touches raw
graphs, orderings, executables, or the Wulver filesystem.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def csv_bytes(rows: list[dict], columns: list[str]) -> bytes:
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


INPUT_COLUMNS = ["instance_id", "cohort", "family", "size", "n", "m", "total_weight",
                 "isolated_vertices", "dimacs_sha256", "graph_sha256", "topology_sha256",
                 "source_parent", "source_id", "source_sha256", "weight_distribution",
                 "code_revision", "source_revision", "config_sha256", "selection_sha256"]
GRAPH_COLUMNS = ["instance_id", "cohort", "family", "size", "total_weight", "xiong_status",
                 "ipsns_status", "xiong_seed1_objective", "xiong_seed2_objective",
                 "ipsns_seed1_objective", "ipsns_seed2_objective", "xiong_median_objective",
                 "ipsns_median_objective", "xiong_seed_span", "ipsns_seed_span",
                 "xiong_median_process_wall_seconds", "ipsns_median_process_wall_seconds",
                 "objective_delta_xiong_minus_ipsns", "delta_over_total_weight",
                 "delta_over_ipsns_objective", "comparison"]
CELL_COLUMNS = ["family", "size", "topologies", "ipsns_wins", "ties", "xiong_wins",
                "median_delta_over_total_weight", "minimum_delta_over_total_weight",
                "maximum_delta_over_total_weight", "median_xiong_process_wall_seconds",
                "median_ipsns_process_wall_seconds"]


def input_rows(manifest: dict, canonical: dict[str, dict]) -> list[dict]:
    topologies = defaultdict(set)
    for task in manifest["tasks"]:
        topologies[task["instance_id"]].add(task["topology_sha256"])
    rows = []
    for source in manifest["input_inventory"]:
        iid = source["instance_id"]
        assert len(topologies[iid]) == 1, iid
        record = canonical[iid]
        for field in ("dimacs_sha256", "graph_sha256", "n", "m", "total_weight"):
            assert str(source[field]) == record[field], (iid, field)
        assert next(iter(topologies[iid])) == record["topology_sha256"], iid
        if iid.startswith("exp04_"):
            parts = iid.split("_")
            assert len(parts) == 5 and parts[1] in ("cm", "er", "sf")
            cohort, family, size = "synthetic", record["family"], int(parts[2][1:])
            assert family == {"cm": "directed_community", "er": "erdos_renyi_directed",
                              "sf": "directed_scale_free"}[parts[1]]
        else:
            cohort, family, size = "real_source_parent", record["family"], ""
        rows.append({"instance_id": iid, "cohort": cohort, "family": family, "size": size,
                     "n": source["n"], "m": source["m"], "total_weight": source["total_weight"],
                     "isolated_vertices": source["isolated_vertices"],
                     "dimacs_sha256": source["dimacs_sha256"], "graph_sha256": source["graph_sha256"],
                     "topology_sha256": next(iter(topologies[iid])),
                     **{field: record[field] for field in ("source_parent", "source_id", "source_sha256",
                                                       "weight_distribution", "code_revision", "source_revision",
                                                       "config_sha256", "selection_sha256")}})
    return rows


def derive(inputs: list[dict], tasks: list[dict], pairs: list[dict], source_review: dict) -> tuple[list[dict], list[dict], dict]:
    assert len(inputs) == 21 and len(tasks) == 84 and len(pairs) == 42
    task_by_key = {(r["instance_id"], r["algorithm"], int(r["seed"])): r for r in tasks}
    pair_by_key = {(r["instance_id"], int(r["seed"])): r for r in pairs}
    assert len(task_by_key) == 84 and len(pair_by_key) == 42
    statuses = defaultdict(Counter)
    for task in tasks:
        statuses[task["algorithm"]][task["status"]] += 1
    comparisons = Counter()
    graph_rows = []
    for source in inputs:
        iid = source["instance_id"]
        x = [task_by_key[iid, "xiong_rasstar", seed] for seed in (1, 2)]
        i = [task_by_key[iid, "ipsns", seed] for seed in (1, 2)]
        pair = [pair_by_key[iid, seed] for seed in (1, 2)]
        assert all(row["status"] == "PASS" and row["objective"] for row in x)
        assert {row["status"] for row in i} in ({"PASS"}, {"TIMEOUT"})
        for seed, p in enumerate(pair, 1):
            assert p["xiong_objective"] == x[seed - 1]["objective"]
            assert p["ipsns_objective"] == i[seed - 1]["objective"]
            expected = ("NOT_COMPARABLE" if i[seed - 1]["status"] == "TIMEOUT" else
                        "IPSNS_WIN" if int(i[seed - 1]["objective"]) < int(x[seed - 1]["objective"]) else
                        "XIONG_WIN" if int(i[seed - 1]["objective"]) > int(x[seed - 1]["objective"]) else "TIE")
            assert p["comparison"] == expected
            comparisons[expected] += 1
        xvals = [int(row["objective"]) for row in x]
        ivals = [int(row["objective"]) for row in i if row["status"] == "PASS"]
        xmed = statistics.median(xvals)
        imed = statistics.median(ivals) if ivals else None
        delta = xmed - imed if imed is not None else None
        comparison = ("NOT_COMPARABLE" if delta is None else
                      "IPSNS_WIN" if delta > 0 else "XIONG_WIN" if delta < 0 else "TIE")
        wall = lambda records: statistics.median(float(record["process_wall_seconds"]) for record in records)
        graph_rows.append({"instance_id": iid, "cohort": source["cohort"], "family": source["family"],
                           "size": source["size"], "total_weight": source["total_weight"],
                           "xiong_status": "PASS_2_OF_2", "ipsns_status": "PASS_2_OF_2" if ivals else "TIMEOUT_2_OF_2",
                           "xiong_seed1_objective": xvals[0], "xiong_seed2_objective": xvals[1],
                           "ipsns_seed1_objective": ivals[0] if ivals else "",
                           "ipsns_seed2_objective": ivals[1] if ivals else "",
                           "xiong_median_objective": xmed, "ipsns_median_objective": imed if imed is not None else "",
                           "xiong_seed_span": abs(xvals[0] - xvals[1]),
                           "ipsns_seed_span": abs(ivals[0] - ivals[1]) if ivals else "",
                           "xiong_median_process_wall_seconds": wall(x),
                           "ipsns_median_process_wall_seconds": wall(i),
                           "objective_delta_xiong_minus_ipsns": delta if delta is not None else "",
                           "delta_over_total_weight": delta / int(source["total_weight"]) if delta is not None else "",
                           "delta_over_ipsns_objective": delta / imed if imed else "",
                           "comparison": comparison})
    assert len(graph_rows) == 21
    synthetic = [row for row in graph_rows if row["cohort"] == "synthetic"]
    assert len(synthetic) == 18
    cells = []
    for family in ("directed_community", "erdos_renyi_directed", "directed_scale_free"):
        for size in (120, 240, 480):
            group = [row for row in synthetic if row["family"] == family and int(row["size"]) == size]
            assert len(group) == 2
            delta_values = [row["delta_over_total_weight"] for row in group]
            cells.append({"family": family, "size": size, "topologies": len(group),
                          "ipsns_wins": sum(row["comparison"] == "IPSNS_WIN" for row in group),
                          "ties": sum(row["comparison"] == "TIE" for row in group),
                          "xiong_wins": sum(row["comparison"] == "XIONG_WIN" for row in group),
                          "median_delta_over_total_weight": statistics.median(delta_values),
                          "minimum_delta_over_total_weight": min(delta_values),
                          "maximum_delta_over_total_weight": max(delta_values),
                          "median_xiong_process_wall_seconds": statistics.median(
                              row["xiong_median_process_wall_seconds"] for row in group),
                          "median_ipsns_process_wall_seconds": statistics.median(
                              row["ipsns_median_process_wall_seconds"] for row in group)})
    synth_task = [row for row in tasks if row["instance_id"].startswith("exp04_")]
    xwall = [float(row["process_wall_seconds"]) for row in synth_task if row["algorithm"] == "xiong_rasstar"]
    iwall = [float(row["process_wall_seconds"]) for row in synth_task if row["algorithm"] == "ipsns"]
    summary = {"format": "exp10-final-scientific-summary-v1", "independent_units": {
        "synthetic_weighted_topologies": 18, "real_source_parent_cases": 3, "seed_pairs": 42,
        "comparable_synthetic_seed_pairs": 36},
        "task_denominators": {method: dict(statuses[method]) for method in ("xiong_rasstar", "ipsns")},
        "seed_pair_comparisons": dict(comparisons),
        "synthetic_graph_comparisons": dict(Counter(row["comparison"] for row in synthetic)),
        "synthetic_graph_median_objective_delta": statistics.median(
            row["objective_delta_xiong_minus_ipsns"] for row in synthetic),
        "synthetic_graph_objective_delta_range": [
            min(row["objective_delta_xiong_minus_ipsns"] for row in synthetic),
            max(row["objective_delta_xiong_minus_ipsns"] for row in synthetic)],
        "synthetic_graph_median_delta_over_total_weight": statistics.median(
            row["delta_over_total_weight"] for row in synthetic),
        "synthetic_graph_median_delta_over_ipsns_objective": statistics.median(
            row["delta_over_ipsns_objective"] for row in synthetic),
        "synthetic_graph_delta_over_ipsns_objective_range": [
            min(row["delta_over_ipsns_objective"] for row in synthetic),
            max(row["delta_over_ipsns_objective"] for row in synthetic)],
        "synthetic_graph_delta_over_total_weight_range": [
            min(row["delta_over_total_weight"] for row in synthetic),
            max(row["delta_over_total_weight"] for row in synthetic)],
        "synthetic_graphs_with_seed_objective_difference": {
            "xiong_rasstar": sum(row["xiong_seed_span"] > 0 for row in synthetic),
            "ipsns": sum(row["ipsns_seed_span"] > 0 for row in synthetic)},
        "synthetic_graph_median_seed_objective_span": {
            "xiong_rasstar": statistics.median(row["xiong_seed_span"] for row in synthetic),
            "ipsns": statistics.median(row["ipsns_seed_span"] for row in synthetic)},
        "synthetic_comparable_task_median_process_wall_seconds": {
            "xiong_rasstar": statistics.median(xwall), "ipsns": statistics.median(iwall)},
        "synthetic_algorithm_only_median": {
            "xiong_rasstar_milliseconds_reported": source_review["synthetic_xiong_algorithm_only_ms_median"],
            "ipsns_seconds_measured": source_review["synthetic_ipsns_algorithm_only_seconds_median"]},
        "all_task_process_wall_seconds": sum(float(row["process_wall_seconds"]) for row in tasks),
        "timeout_task_process_wall_seconds": sum(float(row["process_wall_seconds"]) for row in tasks
                                                 if row["status"] == "TIMEOUT"),
        "slurm_accounting": {"job_id": "REDACTED_EXECUTION_ID", "state": "COMPLETED", "exit_code": "0:0",
                             "elapsed": "00:20:26", "allocated_cpus": 1, "requested_memory": "8G",
                             "total_cpu_seconds": 1159.005, "user_cpu_seconds": 1143.319,
                             "system_cpu_seconds": 15.686, "batch_max_rss_kib": 192684,
                             "batch_max_vm_size_kib": 189500, "node": "REDACTED_EXECUTION_ID"}}
    assert summary["task_denominators"] == source_review["method_statuses"]
    assert summary["seed_pair_comparisons"] == source_review["seed_pair_comparisons"]
    assert abs(summary["all_task_process_wall_seconds"] - source_review["total_task_process_wall_seconds"]) < 1e-7
    return graph_rows, cells, summary


def build(source: Path, destination: Path) -> None:
    manifest = json.loads((source / "manifest.json").read_text())
    repo = Path(__file__).resolve().parents[2]
    plan = json.loads((repo / "experiments/exp10_xiong/plan.json").read_text())
    canonical_path = repo / plan["canonical_inventory"]
    assert sha((repo / "experiments/exp10_xiong/plan.json").read_bytes()) == manifest["plan_sha256"]
    assert sha(canonical_path.read_bytes()) == manifest["canonical_inventory_sha256"]
    with gzip.open(canonical_path, "rt", newline="") as handle:
        canonical = {row["instance_id"]: row for row in csv.DictReader(handle)}
    review = json.loads((source / "final_review.json").read_text())
    original = json.loads((source / "audit_report.json").read_text())
    inputs = input_rows(manifest, canonical)
    tasks = read_csv(source / "audit_inventory.csv")
    pairs = read_csv(source / "paired_results.csv")
    graphs, cells, summary = derive(inputs, tasks, pairs, review)
    assert original["audited"] == 84 and original["violations"] == []
    assert {k: v for k, v in original["statuses"].items() if v} == review["statuses"]
    assert {k: v for k, v in original["comparisons"].items() if v} == review["seed_pair_comparisons"]
    for name, expected in review["source_sha256"].items():
        assert sha((source / name).read_bytes()) == expected
    destination.mkdir(parents=True, exist_ok=True)
    provenance = {"format": "exp10-final-package-provenance-v1", "frozen_output":
        "CUSTODY_PATH/459f2f5-v1",
        "frozen_output_policy": "read-only; no files changed by final review",
        "source_file_sha256": review["source_sha256"], "plan_sha256": manifest["plan_sha256"],
        "canonical_inventory_sha256": manifest["canonical_inventory_sha256"],
        "xiong_binary_sha256": manifest["xiong_binary_sha256"],
        "source_revisions": review["source_revisions"], "cpu_model": manifest["cpu"],
        "python": manifest["python"], "slurm_job_id": manifest["slurm_job_id"]}
    files = {"inputs.csv": csv_bytes(inputs, INPUT_COLUMNS),
             "task_audit_inventory.csv": (source / "audit_inventory.csv").read_bytes(),
             "seed_pair_results.csv": (source / "paired_results.csv").read_bytes(),
             "source_audit_report.json": (source / "audit_report.json").read_bytes(),
             "source_review.json": json_bytes(review),
             "graph_results.csv": csv_bytes(graphs, GRAPH_COLUMNS),
             "family_size_summary.csv": csv_bytes(cells, CELL_COLUMNS),
             "summary.json": json_bytes(summary), "provenance.json": json_bytes(provenance)}
    assert (destination / "README.md").exists(), "Write the review report before building checksums"
    for name, content in files.items():
        (destination / name).write_bytes(content)
    checksum_names = sorted([*files, "README.md"])
    (destination / "checksums.sha256").write_text("".join(
        f"{sha((destination / name).read_bytes())}  {name}\n" for name in checksum_names))


def verify(destination: Path) -> None:
    checksums = (destination / "checksums.sha256").read_text().splitlines()
    listed = {}
    for line in checksums:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        assert match, line
        listed[match[2]] = match[1]
    assert len(listed) == 10 and set(listed) == {path.name for path in destination.iterdir()
                                                if path.is_file() and path.name != "checksums.sha256"}
    for name, expected in listed.items():
        assert sha((destination / name).read_bytes()) == expected, name
    review = json.loads((destination / "source_review.json").read_text())
    provenance = json.loads((destination / "provenance.json").read_text())
    for package_name, source_name in (("task_audit_inventory.csv", "audit_inventory.csv"),
                                      ("seed_pair_results.csv", "paired_results.csv"),
                                      ("source_audit_report.json", "audit_report.json")):
        assert listed[package_name] == provenance["source_file_sha256"][source_name]
    assert provenance["source_file_sha256"] == review["source_sha256"]
    inputs = read_csv(destination / "inputs.csv")
    assert len({r["graph_sha256"] for r in inputs}) == 21
    assert len({r["topology_sha256"] for r in inputs}) == 21
    tasks = read_csv(destination / "task_audit_inventory.csv")
    pairs = read_csv(destination / "seed_pair_results.csv")
    graphs, cells, summary = derive(inputs, tasks, pairs, review)
    assert csv_bytes(graphs, GRAPH_COLUMNS) == (destination / "graph_results.csv").read_bytes()
    assert csv_bytes(cells, CELL_COLUMNS) == (destination / "family_size_summary.csv").read_bytes()
    assert json_bytes(summary) == (destination / "summary.json").read_bytes()
    assert json.loads((destination / "source_audit_report.json").read_text())["violations"] == []


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("package", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        assert args.source is not None
        build(args.source, args.package)
    verify(args.package)
    print("EXP10 final package: PASS")
