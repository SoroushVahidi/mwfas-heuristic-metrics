"""Independent, read-only graph/order/deadline audit of the EXP27 pilot.

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
    a, b = "exp04_cm_n480_k08_r02", "exp13_lodes_de_commute"
    tasks = []
    for gid, arms in ((a, protocol["synthetic_arms"]), (b, [protocol["real_arm"]])):
        for item in arms:
            arm, seed = item["arm"], item["seed"]
            suffix = f"s{seed}" if seed is not None else "det"
            tasks.append({"task_id": f"{gid}__b{protocol['graphs'][gid]['cap_seconds']}__{arm}__{suffix}",
                          "graph_id": gid, "arm": arm, "seed": seed,
                          "cap_seconds": protocol["graphs"][gid]["cap_seconds"],
                          "graph_sha256": protocol["graphs"][gid]["canonical_graph_sha256"]})
    return tasks


def audit(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text())
    release = Path(manifest["release"])
    protocol_path = release / "experiments/exp27_compat/protocol.json"
    if sha(protocol_path) != manifest["protocol_sha256"]:
        raise ValueError("protocol bytes changed")
    protocol = json.loads(protocol_path.read_text())
    tasks = expected_tasks(protocol)
    if manifest["tasks"] != tasks or len(tasks) != 12 or sum(t["cap_seconds"] for t in tasks) != 630:
        raise ValueError("frozen 12-task roster changed")
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
                  "first_valid_seconds": None, "error": None}
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
            if task["arm"] not in ("xiong_restarts", "insertion_lrta", "insertion_wmsf_l2") and len(events) > 1:
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
            if cp["status"] == "PASS" and not checked:
                raise ValueError("PASS has no complete ordering")
            record.update(status=cp["status"], valid_events=len(checked),
                          task_wall_seconds=cp["task_wall_seconds"], child_cpu_seconds=cp["child_cpu_seconds"],
                          first_valid_seconds=checked[0][1]["elapsed_seconds"] if checked else None,
                          objective=min(v for v, _ in checked) if checked else None)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            record["status"] = "INVALID" if cp_path.exists() else "MISSING"
            record["objective"] = None
            record["error"] = str(exc)
            violations.append({"task_id": tid, "error": str(exc)})
        records.append(record)
    gate = next(r for r in records if r["graph_id"] == "exp13_lodes_de_commute")
    gate_pass = gate["status"] in ("PASS", "TIMEOUT") and gate["objective"] is not None
    report = {"format": "exp27-independent-audit-v1", "planned": 12, "audited": len(records),
              "status_counts": {s: sum(r["status"] == s for r in records) for s in ("PASS", "TIMEOUT", "FAILED", "INVALID", "MISSING")},
              "usable_objectives": sum(r["objective"] is not None for r in records),
              "valid_timeouts_with_objective": sum(r["status"] == "TIMEOUT" and r["objective"] is not None for r in records),
              "valid_timeouts_without_objective": sum(r["status"] == "TIMEOUT" and r["objective"] is None for r in records),
              "total_task_wall_seconds": sum(r.get("task_wall_seconds", 0) for r in records),
              "total_child_cpu_seconds": sum(r.get("child_cpu_seconds", 0) for r in records),
              "lodes_300s_availability_gate": "PASS" if gate_pass else "FAIL",
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
