"""Reconcile sealed EXP11/22 audits and emit metadata-only paired analyses.

Input directories are private, read-only audit outputs. This script never opens
or copies graph/order bytes and never writes to an input directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ARMS = ("xiong_single", "xiong_restarts", "ipsns_frozen")
SOURCES = ("original", "first", "corrected")
JOBS = {"original": "1425468", "first": "1426749", "corrected": "1426751"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def verify_seal(folder: Path) -> None:
    for line in (folder / "checksums.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        assert "/" not in name and ".." not in name
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest, name


def load_audit(folder: Path, source: str) -> tuple[dict, dict, list[dict], list[dict]]:
    verify_seal(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    report = json.loads((folder / "audit_report.json").read_text())
    rows = read_csv(folder / "task_inventory.csv")
    events = read_csv(folder / "restart_events.csv")
    assert manifest["slurm_job_id"] == JOBS[source]
    assert report["format"] == "exp11-independent-audit-v1"
    assert len(rows) == len(manifest["tasks"]) == report["planned"] == report["audited"]
    assert len({r["task_id"] for r in rows}) == len(rows)
    tasks = {t["task_id"]: t for t in manifest["tasks"]}
    inputs = {g["instance_id"]: g for g in manifest["inputs"]}
    assert len(inputs) == 5
    for row in rows:
        task = tasks[row["task_id"]]
        for field in ("task_id", "instance_id", "arm", "seed", "budget_seconds", "graph_sha256"):
            assert str(task[field]) == row[field], (source, row["task_id"], field)
        assert row["arm"] in ARMS
        assert row["graph_sha256"] == inputs[row["instance_id"]]["graph_sha256"]
        assert row["status"] in ("PASS", "TIMEOUT", "FAILED", "INVALID")
        if row["status"] == "INVALID":
            assert not row["objective"]
        else:
            assert row["wall_budget_compliant"] == "True"
            assert float(row["task_wall_seconds"]) <= float(row["budget_seconds"])
        if row["objective"]:
            assert int(row["objective"]) >= 0
            assert int(row["valid_events"]) > 0
        else:
            assert int(row["valid_events"]) == 0
    statuses = Counter(r["status"] for r in rows)
    assert {s: statuses[s] for s in report["statuses"]} == report["statuses"]
    assert sum(bool(r["objective"]) for r in rows) == report["credited_endpoints"]
    assert len(events) == report["verified_xiong_restarts"]
    grouped_events: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        assert event["task_id"] in tasks
        assert tasks[event["task_id"]]["arm"].startswith("xiong_")
        assert float(event["elapsed_seconds"]) < float(tasks[event["task_id"]]["budget_seconds"])
        grouped_events[event["task_id"]].append(event)
    for row in rows:
        ev = sorted(grouped_events[row["task_id"]], key=lambda e: int(e["index"]))
        if row["arm"].startswith("xiong_") and row["status"] != "INVALID":
            assert len(ev) == int(row["valid_events"])
            if ev:
                assert [int(e["index"]) for e in ev] == list(range(len(ev)))
                assert min(int(e["objective"]) for e in ev) == int(row["objective"])
                if row["arm"] == "xiong_restarts":
                    assert int(ev[0]["objective"]) == int(row["first_restart_objective"])
        elif row["arm"] == "ipsns_frozen":
            assert not ev
    if source == "original":
        assert len(report["violations"]) == report["wall_budget_violations"] == 22
        assert {v["task_id"] for v in report["violations"]} == {
            r["task_id"] for r in rows if r["status"] == "INVALID"
        }
    else:
        assert report["violations"] == []
        assert report["wall_budget_violations"] == 0
    return manifest, report, rows, events


def combine(audits: dict[str, tuple[dict, dict, list[dict], list[dict]]]) -> tuple[list[dict], dict]:
    original = {r["task_id"]: r for r in audits["original"][2]}
    invalid = {tid for tid, r in original.items() if r["status"] == "INVALID"}
    retained = {tid: {**r, "evidence_source": "original", "job_id": JOBS["original"]}
                for tid, r in original.items() if tid not in invalid}
    recovery_ids: set[str] = set()
    for source in ("first", "corrected"):
        for row in audits[source][2]:
            tid = row["task_id"]
            assert tid in invalid and tid not in recovery_ids
            assert row["status"] != "INVALID"
            recovery_ids.add(tid)
            retained[tid] = {**row, "evidence_source": source, "job_id": JOBS[source]}
    missing = invalid - recovery_ids
    assert len(original) == 78 and len(invalid) == 22
    assert len(audits["first"][2]) == 1 and len(audits["corrected"][2]) == 15
    assert len(retained) == 72 and len(missing) == 6
    assert all(int(original[tid]["budget_seconds"]) == 1 for tid in missing)
    # Retain the six invalid original identities, with no objective credit.
    combined = sorted([*retained.values(),
                       *({**original[tid], "evidence_source": "original_invalid",
                          "job_id": JOBS["original"]} for tid in missing)],
                      key=lambda r: (r["instance_id"], int(r["budget_seconds"]),
                                     int(r["seed"]), ARMS.index(r["arm"])))
    assert len(combined) == 78 and len({r["task_id"] for r in combined}) == 78
    assert sum(bool(r["objective"]) for r in combined) == 61
    return combined, {"original_invalid": len(invalid), "replaced_invalid": len(recovery_ids),
                      "remaining_invalid": len(missing), "remaining_invalid_task_ids": sorted(missing)}


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)


def analyze(audits: dict[str, tuple[dict, dict, list[dict], list[dict]]], output: Path) -> dict:
    manifests = {name: item[0] for name, item in audits.items()}
    base = manifests["original"]
    inputs = {g["instance_id"]: g for g in base["inputs"]}
    source_fields = ("protocol_sha256", "canonical_inventory_sha256", "xiong_revision",
                     "xiong_binary_sha256", "ipsns_revision", "ipsns_source_file_sha256")
    for manifest in manifests.values():
        assert {k: manifest[k] for k in source_fields} == {k: base[k] for k in source_fields}
        assert [{k: g[k] for k in ("instance_id", "dimacs_sha256", "graph_sha256", "n", "m", "total_weight")}
                for g in manifest["inputs"]] == [
                {k: g[k] for k in ("instance_id", "dimacs_sha256", "graph_sha256", "n", "m", "total_weight")}
                for g in base["inputs"]]
        assert manifest["cpu_model"] == base["cpu_model"]
    assert base["xiong_revision"] == "8340e1633ba9290a567a882aff4d74f01b38102d"
    assert base["ipsns_revision"] == "40209c26966247d9bf9ad34764de4ac4181f98c2"
    combined, recovery = combine(audits)
    first_times: dict[str, float] = {}
    for source in SOURCES:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for event in audits[source][3]:
            grouped[event["task_id"]].append(event)
        for row in audits[source][2]:
            if row["status"] == "INVALID" or not row["objective"]:
                continue
            if row["arm"].startswith("xiong_"):
                first_times[row["task_id"]] = float(min(grouped[row["task_id"]], key=lambda e: int(e["index"]))["elapsed_seconds"])
            else:
                first_times[row["task_id"]] = float(row["best_event_elapsed_seconds"])
    task_rows = []
    for row in combined:
        inp = inputs[row["instance_id"]]
        task_rows.append({"instance_id": row["instance_id"], "graph_sha256": row["graph_sha256"],
                          "total_weight": inp["total_weight"], "budget_seconds": row["budget_seconds"],
                          "seed": row["seed"], "arm": row["arm"], "status": row["status"],
                          "objective": row["objective"], "task_wall_seconds": row.get("task_wall_seconds", ""),
                          "first_valid_seconds": f"{first_times[row['task_id']]:.6f}" if row["task_id"] in first_times else "",
                          "best_valid_seconds": row.get("best_event_elapsed_seconds", ""),
                          "valid_events": row.get("valid_events", ""),
                          "evidence_source": row["evidence_source"], "job_id": row["job_id"],
                          "task_id": row["task_id"]})
    by_key = {(r["instance_id"], int(r["budget_seconds"]), int(r["seed"]), r["arm"]): r
              for r in task_rows}
    paired = []
    for graph in inputs:
        budgets = sorted({int(r["budget_seconds"]) for r in task_rows if r["instance_id"] == graph})
        for budget in budgets:
            for seed in (1, 2):
                arms = {arm: by_key[(graph, budget, seed, arm)] for arm in ARMS}
                obj = {arm: int(arms[arm]["objective"]) if arms[arm]["objective"] else None for arm in ARMS}
                total = inputs[graph]["total_weight"]
                diff = lambda a, b: f"{(obj[a] - obj[b]) / total:.9f}" if obj[a] is not None and obj[b] is not None else ""
                paired.append({"instance_id": graph, "budget_seconds": budget, "seed": seed,
                               "total_weight": total,
                               **{arm + "_status": arms[arm]["status"] for arm in ARMS},
                               **{arm + "_objective": obj[arm] if obj[arm] is not None else "" for arm in ARMS},
                               "single_minus_ipsns_per_T": diff("xiong_single", "ipsns_frozen"),
                               "restart_minus_ipsns_per_T": diff("xiong_restarts", "ipsns_frozen"),
                               "restart_minus_single_per_T": diff("xiong_restarts", "xiong_single")})
    graph_budget = []
    for graph in inputs:
        for budget in sorted({int(r["budget_seconds"]) for r in paired if r["instance_id"] == graph}):
            rows = [r for r in paired if r["instance_id"] == graph and r["budget_seconds"] == budget]
            item: dict[str, object] = {"instance_id": graph, "budget_seconds": budget,
                                       "total_weight": inputs[graph]["total_weight"]}
            for arm in ARMS:
                vals = [int(r[arm + "_objective"]) for r in rows if r[arm + "_objective"] != ""]
                item[arm + "_objectives"] = ";".join(str(v) for v in vals)
                item[arm + "_valid_seeds"] = len(vals)
                item[arm + "_median"] = statistics.median(vals) if vals else ""
            for field in ("single_minus_ipsns_per_T", "restart_minus_ipsns_per_T", "restart_minus_single_per_T"):
                vals = [float(r[field]) for r in rows if r[field] != ""]
                item[field + "_paired_seeds"] = len(vals)
                item[field + "_median"] = f"{statistics.median(vals):.9f}" if vals else ""
            graph_budget.append(item)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "EXP24_TASK_MATRIX.csv", task_rows,
              ("instance_id", "graph_sha256", "total_weight", "budget_seconds", "seed", "arm", "status",
               "objective", "task_wall_seconds", "first_valid_seconds", "best_valid_seconds", "valid_events",
               "evidence_source", "job_id", "task_id"))
    write_csv(output / "EXP24_PAIRED_SEEDS.csv", paired,
              ("instance_id", "budget_seconds", "seed", "total_weight",
               *(arm + "_status" for arm in ARMS), *(arm + "_objective" for arm in ARMS),
               "single_minus_ipsns_per_T", "restart_minus_ipsns_per_T", "restart_minus_single_per_T"))
    write_csv(output / "EXP24_GRAPH_BUDGET.csv", graph_budget,
              ("instance_id", "budget_seconds", "total_weight",
               *(field for arm in ARMS for field in (arm + "_objectives", arm + "_valid_seeds", arm + "_median")),
               *(field for name in ("single_minus_ipsns_per_T", "restart_minus_ipsns_per_T", "restart_minus_single_per_T")
                 for field in (name + "_paired_seeds", name + "_median"))))
    summary = {"format": "exp24-controlled-pilot-analysis-v1", "tasks": len(task_rows),
               "statuses": dict(Counter(r["status"] for r in task_rows)),
               "usable_objectives": sum(bool(r["objective"]) for r in task_rows),
               "original_audit": {"statuses": audits["original"][1]["statuses"],
                                  "usable_objectives": audits["original"][1]["credited_endpoints"]},
               "first_audit": {"statuses": audits["first"][1]["statuses"],
                               "usable_objectives": audits["first"][1]["credited_endpoints"]},
               "corrected_audit": {"statuses": audits["corrected"][1]["statuses"],
                                   "usable_objectives": audits["corrected"][1]["credited_endpoints"]},
               "recovery": recovery, "graphs": len(inputs), "graph_budgets": len(graph_budget),
               "paired_seeds": {field: sum(bool(r[field]) for r in paired)
                                for field in ("single_minus_ipsns_per_T", "restart_minus_ipsns_per_T",
                                              "restart_minus_single_per_T")},
               "source_revisions": {"xiong": base["xiong_revision"], "ipsns": base["ipsns_revision"]}}
    assert summary["statuses"] == {"PASS": 37, "TIMEOUT": 35, "INVALID": 6}
    assert summary["usable_objectives"] == 61
    (output / "EXP24_ANALYSIS_SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in SOURCES:
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    folders = {name: getattr(args, name).resolve() for name in SOURCES}
    out = args.output.resolve()
    assert all(out != folder and folder not in out.parents for folder in folders.values())
    audits = {name: load_audit(folder, name) for name, folder in folders.items()}
    print(json.dumps(analyze(audits, out), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
