"""Independent post-run audit of every creditable EXP11 endpoint."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from experiments.exp10_xiong.independent_audit import parse_original, parse_rank, validate


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_ipsns_raw(folder: Path, event: dict, n: int, arcs: list[tuple[int, int, int]], final_rank: list[int]) -> None:
    raw = folder / "order.csv"
    if sha(raw) != event["raw_order_sha256"]:
        raise ValueError("IPSNS raw order hash mismatch")
    with raw.open(newline="") as f:
        rows = list(csv.DictReader(f))
    ids = [int(r["Node ID"]) for r in rows]
    ranks = [int(r["Order"]) for r in rows]
    if len(ids) != len(set(ids)) or sorted(ranks) != list(range(len(rows))):
        raise ValueError("malformed raw IPSNS order")
    absent = sorted(set(range(1, n + 1)) - set(ids))
    incident = {u for u, _, _ in arcs} | {v for _, v, _ in arcs}
    if any(v in incident for v in absent) or absent != event["missing_isolated_vertices"]:
        raise ValueError("IPSNS isolated vertex claim mismatch")
    expected = [int(r["Node ID"]) for r in sorted(rows, key=lambda r: int(r["Order"]))] + absent
    actual = sorted(range(1, n + 1), key=lambda v: final_rank[v - 1])
    if actual != expected:
        raise ValueError("derived IPSNS ordering changed ranks")
    if event["iterations"] > 200:
        raise ValueError("IPSNS iteration maximum exceeded")


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(); out = a.output
    manifest = json.loads((out / "manifest.json").read_text())
    inputs = {r["instance_id"]: r for r in manifest["inputs"]}
    records = []; restart_records = []; violations = []
    for task in manifest["tasks"]:
        tid = task["task_id"]
        folder = out / "tasks" / tid
        record = {**task, "status": "INVALID", "objective": None,
                  "output_kind": None, "valid_events": 0}
        try:
            cp = json.loads((out / "checkpoints" / (tid + ".json")).read_text())
            for key in ("task_id", "instance_id", "budget_seconds", "arm", "seed", "graph_sha256"):
                if cp[key] != task[key]:
                    raise ValueError("checkpoint task identity mismatch")
            record.update(task_wall_seconds=cp["task_wall_seconds"],
                          child_user_cpu_seconds=cp["child_user_cpu_seconds"],
                          child_system_cpu_seconds=cp["child_system_cpu_seconds"],
                          wall_budget_compliant=cp["wall_budget_compliant"])
            if cp["task_wall_seconds"] > task["budget_seconds"] or not cp["wall_budget_compliant"]:
                raise ValueError("end-to-end wall budget exceeded")
            source = inputs[task["instance_id"]]
            graph = Path(source["path"])
            if sha(graph) != source["dimacs_sha256"]:
                raise ValueError("original graph byte hash mismatch")
            n, arcs, graph_hash = parse_original(graph)
            if graph_hash != task["graph_sha256"] or graph_hash != source["graph_sha256"]:
                raise ValueError("original weighted graph identity mismatch")
            if n != source["n"] or len(arcs) != source["m"] or sum(w for _, _, w in arcs) != source["total_weight"]:
                raise ValueError("original graph size or integer weights mismatch")
            if task["arm"].startswith("xiong_") and (folder / "input.w").exists():
                w = [line.split() for line in (folder / "input.w").read_text().splitlines()]
                if list(map(int, w[0])) != [n, len(arcs)] or [tuple(map(int, x)) for x in w[1:]] != [(u-1,v-1,weight) for u,v,weight in arcs]:
                    raise ValueError("Xiong W conversion changed original weights")
            events = sorted(folder.glob("event_*.json"))
            if len(events) != cp["event_count"]:
                raise ValueError("event count checkpoint mismatch")
            verified = []
            for index, path in enumerate(events):
                e = json.loads(path.read_text())
                if path.name != f"event_{index:06d}.json" or e["index"] != index:
                    raise ValueError("nonconsecutive event or restart index")
                expected_seed = task["seed"] if index == 0 else 1 + ((task["seed"] * 1000003 + index * 104729) % 2147483646)
                if e["seed"] != expected_seed:
                    raise ValueError("restart seed provenance mismatch")
                if not (0 <= e["elapsed_seconds"] < task["budget_seconds"]):
                    raise ValueError("event after deadline")
                if path.stat().st_mtime_ns > cp["start_unix_ns"] + int(task["budget_seconds"] * 1e9):
                    raise ValueError("event file checkpointed after deadline")
                rank_file = folder / e["rank_path"]
                if sha(rank_file) != e["rank_sha256"]:
                    raise ValueError("ordering hash mismatch")
                method = "xiong_rasstar" if task["arm"].startswith("xiong_") else "ipsns"
                rank = parse_rank(rank_file, method, n)
                objective = validate(n, arcs, rank)
                if objective != e["objective"]:
                    raise ValueError("independently recomputed objective mismatch")
                if method == "ipsns":
                    if index != 0:
                        raise ValueError("unexpected IPSNS intermediate event")
                    check_ipsns_raw(folder, e, n, arcs, rank)
                verified.append(e)
                if method == "xiong_rasstar":
                    restart_records.append({"task_id": tid, "index": index, "seed": e["seed"],
                                            "objective": objective, "elapsed_seconds": e["elapsed_seconds"],
                                            "rank_sha256": e["rank_sha256"]})
            if task["arm"] in ("xiong_single", "ipsns_frozen") and len(verified) > 1:
                raise ValueError("single execution produced multiple endpoints")
            if cp["status"] == "COMPLETED_UNVALIDATED" and not verified:
                record["status"] = "TIMEOUT" if cp["task_wall_seconds"] >= task["budget_seconds"] - 0.1 else "FAILED"
            elif cp["status"] == "COMPLETED_UNVALIDATED":
                record["status"] = "PASS"
            elif cp["status"] in ("TIMEOUT", "FAILED"):
                record["status"] = cp["status"]
            else:
                raise ValueError("unknown process status")
            record["valid_events"] = len(verified)
            if verified:
                best = min(verified, key=lambda e: (e["objective"], e["elapsed_seconds"]))
                record["objective"] = best["objective"]
                record["best_event_elapsed_seconds"] = best["elapsed_seconds"]
                record["best_event_seed"] = best["seed"]
                record["output_kind"] = "interrupted_run_completed_restart" if record["status"] == "TIMEOUT" else "completed_execution"
                if task["arm"] == "xiong_restarts":
                    record["first_restart_objective"] = verified[0]["objective"]
                    record["improvement_over_first"] = verified[0]["objective"] - best["objective"]
                if task["arm"] == "ipsns_frozen":
                    record["ipsns_iterations"] = best["iterations"]
            if record["status"] == "FAILED" and record["objective"] is not None:
                record["output_kind"] = "failed_run_prior_completed_restart"
        except Exception as exc:
            record["status"] = "INVALID"; record["objective"] = None
            record["error"] = str(exc); violations.append({"task_id": tid, "error": str(exc)})
        records.append(record)
    pairs = []
    by_key = {(r["instance_id"], r["budget_seconds"], r["seed"], r["arm"]): r for r in records}
    for task in manifest["tasks"]:
        if task["arm"] != "xiong_single":
            continue
        key = (task["instance_id"], task["budget_seconds"], task["seed"])
        trio = [by_key[key + (arm,)] for arm in ("xiong_single", "xiong_restarts", "ipsns_frozen")]
        pair = {"instance_id": key[0], "budget_seconds": key[1], "seed": key[2],
                **{arm + "_status": r["status"] for arm, r in zip(("xiong_single", "xiong_restarts", "ipsns_frozen"), trio)},
                **{arm + "_objective": r["objective"] for arm, r in zip(("xiong_single", "xiong_restarts", "ipsns_frozen"), trio)}}
        pair["restart_minus_ipsns_over_total_weight"] = ((trio[1]["objective"] - trio[2]["objective"]) / inputs[key[0]]["total_weight"]
                                                        if trio[1]["objective"] is not None and trio[2]["objective"] is not None else None)
        pairs.append(pair)
    for name, rows in (("task_inventory.csv", records), ("restart_events.csv", restart_records), ("comparisons.csv", pairs)):
        fields = sorted({key for row in rows for key in row})
        with (out / name).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    report = {"format": "exp11-independent-audit-v1", "planned": len(manifest["tasks"]),
              "audited": len(records), "statuses": {s: sum(r["status"] == s for r in records) for s in ("PASS", "TIMEOUT", "FAILED", "INVALID")},
              "credited_endpoints": sum(r["objective"] is not None for r in records),
              "verified_xiong_restarts": len(restart_records),
              "wall_budget_violations": sum(r.get("wall_budget_compliant") is False for r in records),
              "total_task_wall_seconds": sum(r.get("task_wall_seconds", 0) for r in records),
              "total_child_cpu_seconds": sum(r.get("child_user_cpu_seconds", 0) + r.get("child_system_cpu_seconds", 0) for r in records),
              "violations": violations}
    (out / "audit_report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    names = ("manifest.json", "task_inventory.csv", "restart_events.csv", "comparisons.csv", "audit_report.json")
    (out / "checksums.sha256").write_text("".join(f"{sha(out / name)}  {name}\n" for name in names))
    if violations:
        raise SystemExit("independent audit found invalid endpoints")


if __name__ == "__main__":
    main()
