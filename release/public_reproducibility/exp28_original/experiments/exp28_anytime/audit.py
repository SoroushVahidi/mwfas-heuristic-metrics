"""Independent graph, ordering, trajectory, and deadline audit of EXP28.

No method module or worker scoring function is imported here. This module uses
only the standard library and independently parses the original DIMACS bytes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, deque
from pathlib import Path


NORMALIZATION = {"directed": True, "node_labels": "1-based-integers",
                 "parallel_edges": "absent", "self_loops": "absent",
                 "weight_type": "positive-integer"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph(path: Path) -> tuple[int, list[tuple[int, int, int]], str]:
    """Parse graph and reproduce the frozen canonical weighted hash."""
    header = None
    arcs: list[tuple[int, int, int]] = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if not fields or fields[0] == "c":
            continue
        if fields[0] == "p" and len(fields) == 4 and fields[1] in ("sp", "graph") and header is None:
            header = (int(fields[2]), int(fields[3]))
        elif fields[0] == "a" and len(fields) in (4, 5) and header is not None:
            if len(fields) == 5:
                int(fields[4])  # EXP13 preserves an extra source annotation.
            arcs.append(tuple(map(int, fields[1:4])))
        else:
            raise ValueError("unsupported DIMACS record")
    if header is None or header[0] < 1 or len(arcs) != header[1]:
        raise ValueError("DIMACS header or arc count invalid")
    n = header[0]
    if len({(u, v) for u, v, _ in arcs}) != len(arcs):
        raise ValueError("parallel arcs")
    if any(u == v or not (1 <= u <= n and 1 <= v <= n) or w <= 0 for u, v, w in arcs):
        raise ValueError("invalid vertex, self-loop or weight")
    payload = {"format": "mwfas-exp03-graph-v1", "normalization": NORMALIZATION,
               "vertices": list(range(1, n + 1)), "arcs": sorted(arcs)}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return n, arcs, digest


def ranks(path: Path, arm: str, n: int) -> list[int]:
    if arm.startswith("xiong_"):
        values = [int(x) for x in path.read_text().split()]
        if len(values) != n:
            raise ValueError("Xiong rank vector incomplete")
        return values
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != n:
        raise ValueError("CSV ordering incomplete")
    values = [-1] * n
    for row in rows:
        v = int(row["Node ID"])
        if not 1 <= v <= n or values[v - 1] != -1:
            raise ValueError("duplicate or foreign vertex")
        values[v - 1] = int(row["Order"])
    return values


def objective(n: int, arcs: list[tuple[int, int, int]], rank: list[int]) -> int:
    if len(rank) != n or sorted(rank) != list(range(n)):
        raise ValueError("not a complete vertex permutation")
    forward = [[] for _ in range(n)]
    indegree = [0] * n
    value = 0
    for u, v, w in arcs:
        if rank[u - 1] > rank[v - 1]:
            value += w
        else:
            forward[u - 1].append(v - 1)
            indegree[v - 1] += 1
    queue = deque(v for v, d in enumerate(indegree) if d == 0)
    seen = 0
    while queue:
        u = queue.popleft(); seen += 1
        for v in forward[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    if seen != n:
        raise ValueError("retained graph is cyclic")
    return value


def check_w(path: Path, n: int, arcs: list[tuple[int, int, int]]) -> None:
    lines = [list(map(int, line.split())) for line in path.read_text().splitlines()]
    if not lines or lines[0] != [n, len(arcs)] or len(lines) != len(arcs) + 1:
        raise ValueError("Xiong W header/count mismatch")
    if Counter(tuple(line) for line in lines[1:]) != Counter((u - 1, v - 1, w) for u, v, w in arcs):
        raise ValueError("Xiong W conversion changed weighted arcs")


def expected_tasks(protocol: dict) -> list[dict]:
    return protocol["tasks"]


def audit(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text())
    release = Path(manifest["release"])
    protocol_path = Path(manifest["protocol_path"])
    if protocol_path.parent != release / "experiments/exp28_anytime":
        raise ValueError("protocol path outside frozen release")
    if sha(protocol_path) != manifest["protocol_sha256"]:
        raise ValueError("protocol bytes changed")
    if sha(Path(manifest["graph_paths_file"])) != manifest["graph_paths_sha256"]:
        raise ValueError("graph path map changed")
    protocol = json.loads(protocol_path.read_text())
    tasks = expected_tasks(protocol)
    if (manifest["tasks"] != tasks or len(tasks) != protocol["max_tasks"] or
            sum(t["cap_seconds"] for t in tasks) != protocol["nominal_cap_seconds"]):
        raise ValueError("frozen EXP28 task roster changed")
    inputs = manifest["inputs"]
    graph_cache = {}
    for gid, cfg in protocol["graphs"].items():
        path = Path(inputs[gid]["path"])
        n, arcs, digest = graph(path)
        if (sha(path), digest, n, len(arcs), sum(w for _, _, w in arcs)) != (
                cfg["dimacs_sha256"], cfg["canonical_graph_sha256"], cfg["n"], cfg["m"], cfg["total_weight"]):
            raise ValueError("frozen graph bytes/identity changed: " + gid)
        graph_cache[gid] = (n, arcs)
    records = []
    violations = []
    for task in tasks:
        tid = task["task_id"]
        folder = output / "tasks" / tid
        cp_path = output / "checkpoints" / (tid + ".json")
        record = {**task, "status": "INVALID", "objective": None, "valid_events": 0,
                  "first_valid_seconds": None, "time_to_best_seconds": None,
                  "initializer_objective": None, "error": None}
        try:
            if not cp_path.exists():
                raise ValueError("missing checkpoint")
            cp = json.loads(cp_path.read_text())
            for key, value in task.items():
                if cp.get(key) != value:
                    raise ValueError("checkpoint task identity mismatch: " + key)
            if cp["status"] not in ("PASS", "TIMEOUT", "FAILED", "INVALID"):
                raise ValueError("unknown checkpoint status")
            if cp["task_wall_seconds"] < 0 or cp["task_wall_seconds"] > task["cap_seconds"] or not cp["wall_budget_compliant"]:
                raise ValueError("strict end-to-end method cap exceeded")
            if cp["end_unix_ns"] < cp["start_unix_ns"] or cp["child_cpu_seconds"] < 0:
                raise ValueError("invalid task timing or CPU accounting")
            if abs((cp["end_unix_ns"] - cp["start_unix_ns"]) / 1e9 - cp["task_wall_seconds"]) > 2:
                raise ValueError("wall and UTC task clocks disagree")
            if sha(folder / "process.log") != cp["log_sha256"]:
                raise ValueError("process log changed")
            n, arcs = graph_cache[task["graph_id"]]
            if task["arm"].startswith("xiong_"):
                check_w(folder / "input.w", n, arcs)
            events = sorted(folder.glob("event_*.json"))
            if len(events) != cp["event_count"]:
                raise ValueError("event count differs from checkpoint")
            if task["arm"] not in ("xiong_restarts", "insertion_lrta", "insertion_wmsf_l2", "ipsns") and len(events) > 1:
                raise ValueError("single-shot arm has multiple events")
            if task["arm"].startswith("insertion_") and len(events) > 2:
                raise ValueError("insertion arm has too many events")
            checked = []
            for i, event_path in enumerate(events):
                if event_path.name != f"event_{i:06d}.json":
                    raise ValueError("nonconsecutive event filenames")
                event = json.loads(event_path.read_text())
                if event["index"] != i or event["task_id"] != tid:
                    raise ValueError("event identity/index mismatch")
                if task["arm"] == "ipsns":
                    extra = event.get("extra", {})
                    if (extra.get("graph_sha256") != task["graph_sha256"] or
                            extra.get("kind") not in ("wmsf_seed", "lr_seed_improvement", "complete_initializer", "refinement_improvement") or
                            not isinstance(extra.get("iteration"), int) or extra["iteration"] < 0):
                        raise ValueError("IPSNS graph, phase, or iteration changed")
                    if i == 0 and (extra["kind"] != "wmsf_seed" or extra["iteration"] != 0):
                        raise ValueError("IPSNS first ordering is not WMSF seed")
                    if extra["kind"] == "refinement_improvement" and extra["iteration"] < 1:
                        raise ValueError("IPSNS refinement iteration invalid")
                if task["arm"].startswith("xiong_"):
                    seed = task["seed"] if i == 0 else 1 + ((task["seed"] * 1000003 + i * 104729) % 2147483646)
                    if event["seed"] != seed:
                        raise ValueError("Xiong restart seed changed")
                elif event["seed"] != task["seed"]:
                    raise ValueError("event seed changed")
                if not 0 <= event["elapsed_seconds"] < task["cap_seconds"]:
                    raise ValueError("event elapsed beyond cap")
                if not cp["start_monotonic"] <= event["saved_monotonic"] < cp["deadline_monotonic"]:
                    raise ValueError("event monotonic time beyond deadline")
                last_allowed = cp["start_unix_ns"] + int(task["cap_seconds"] * 1e9)
                path = folder / event["order_file"]
                if path.parent != folder or sha(path) != event["order_sha256"]:
                    raise ValueError("order path/hash mismatch")
                if event_path.stat().st_mtime_ns > last_allowed or path.stat().st_mtime_ns > last_allowed:
                    raise ValueError("checkpoint or order saved after deadline")
                rank = ranks(path, task["arm"], n)
                value = objective(n, arcs, rank)
                if value != event["reported_objective"]:
                    raise ValueError("independent objective differs from worker record")
                checked.append((value, event))
            if task["arm"].startswith("insertion_") and len(checked) == 2 and checked[1][0] > checked[0][0]:
                raise ValueError("insertion refinement worsened its saved seed")
            if task["arm"] == "ipsns":
                for prior, later in zip(checked, checked[1:]):
                    if later[0] > prior[0]:
                        raise ValueError("IPSNS incumbent trajectory worsened")
                    if later[1]["extra"]["kind"] in ("lr_seed_improvement", "refinement_improvement") and later[0] >= prior[0]:
                        raise ValueError("IPSNS claimed improvement is not strict")
                    if later[1]["elapsed_seconds"] < prior[1]["elapsed_seconds"]:
                        raise ValueError("IPSNS checkpoint clock reversed")
                    if later[1]["extra"]["iteration"] < prior[1]["extra"]["iteration"]:
                        raise ValueError("IPSNS iteration reversed")
                if cp["status"] == "PASS" and not (folder / "ipsns_completion.json").exists():
                    raise ValueError("completed IPSNS lacks completion record")
                if cp["status"] == "PASS":
                    completion = json.loads((folder / "ipsns_completion.json").read_text())
                    if (completion["termination_reason"] != "completed" or
                            completion["iterations"] > protocol["ipsns"]["iters"] or
                            completion["accepted_improvements"] != sum(
                                row[1]["extra"]["kind"] == "refinement_improvement" for row in checked) or
                            not 0 <= completion["checkpoint_seconds"] <= cp["task_wall_seconds"] or
                            completion["raw_order_sha256"] != sha(folder / "raw_order.csv")):
                        raise ValueError("IPSNS completion record differs")
                timeout_path = folder / "ipsns_timeout.json"
                if timeout_path.exists():
                    timeout = json.loads(timeout_path.read_text())
                    if (cp["status"] != "TIMEOUT" or timeout["termination_reason"] != "internal_deadline" or
                            not 0 <= timeout["iterations"] <= protocol["ipsns"]["iters"] or
                            timeout["best_saved_objective"] != (min(v for v, _ in checked) if checked else None) or
                            not 0 <= timeout["checkpoint_seconds"] <= cp["task_wall_seconds"]):
                        raise ValueError("IPSNS timeout record differs")
            if cp["status"] == "PASS" and not checked:
                raise ValueError("PASS has no complete ordering")
            best = min(checked, key=lambda row: row[0]) if checked else None
            initializer = next((row[0] for row in checked if row[1].get("extra", {}).get("kind") == "complete_initializer"), None)
            record.update(status=cp["status"], valid_events=len(checked),
                          task_wall_seconds=cp["task_wall_seconds"], child_cpu_seconds=cp["child_cpu_seconds"],
                          first_valid_seconds=checked[0][1]["elapsed_seconds"] if checked else None,
                          time_to_best_seconds=best[1]["elapsed_seconds"] if best else None,
                          initializer_objective=initializer,
                          objective=best[0] if best else None)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            record["status"] = "INVALID" if cp_path.exists() else "MISSING"
            record["objective"] = None
            record["error"] = str(exc)
            violations.append({"task_id": tid, "error": str(exc)})
        records.append(record)
    lodes = next((r for r in records if r["graph_id"] == "exp13_lodes_de_commute"), None)
    lodes_pass = lodes is not None and lodes["status"] in ("PASS", "TIMEOUT") and lodes["objective"] is not None
    synthetic_pass = any(r["graph_id"].startswith("exp04_") and r["arm"] == "ipsns" and r["objective"] is not None for r in records)
    real_pass = any(not r["graph_id"].startswith("exp04_") and r["arm"] == "ipsns" and r["objective"] is not None for r in records)
    violations_count = len(violations)
    pilot_gate = synthetic_pass and real_pass and violations_count == 0 and not any(r["status"] in ("FAILED", "INVALID", "MISSING") for r in records)
    report = {"format": "exp28-independent-audit-v1", "planned": len(tasks), "audited": len(records),
              "status_counts": {s: sum(r["status"] == s for r in records) for s in ("PASS", "TIMEOUT", "FAILED", "INVALID", "MISSING")},
              "usable_objectives": sum(r["objective"] is not None for r in records),
              "valid_timeouts_with_objective": sum(r["status"] == "TIMEOUT" and r["objective"] is not None for r in records),
              "valid_timeouts_without_objective": sum(r["status"] == "TIMEOUT" and r["objective"] is None for r in records),
              "total_task_wall_seconds": sum(r.get("task_wall_seconds", 0) for r in records),
              "total_child_cpu_seconds": sum(r.get("child_cpu_seconds", 0) for r in records),
              "lodes_300s_availability_gate": "PASS" if lodes_pass else "FAIL",
              "synthetic_ipsns_availability": synthetic_pass, "real_ipsns_availability": real_pass,
              "pilot_gate": "PASS" if pilot_gate else "FAIL",
              "violations": violations}
    with (output / "task_inventory.csv").open("w", newline="") as f:
        fields = sorted({key for row in records for key in row})
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(records)
    (output / "audit_report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    names = ["manifest.json", "task_inventory.csv", "audit_report.json"]
    names += [str(p.relative_to(output)) for p in sorted((output / "checkpoints").glob("*.json"))]
    (output / "checksums.sha256").write_text("".join(f"{sha(output / name)}  {name}\n" for name in names))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True, type=Path)
    result = audit(p.parse_args().output)
    print(json.dumps(result, sort_keys=True))
    if result["violations"]:
        raise SystemExit(1)
