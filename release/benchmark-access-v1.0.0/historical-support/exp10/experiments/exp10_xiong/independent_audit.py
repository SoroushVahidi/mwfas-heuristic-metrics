"""Separate standard-library audit: reparses original DIMACS and both order formats."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path

NORMALIZATION = {"directed": True, "node_labels": "1-based-integers", "parallel_edges": "absent",
                 "self_loops": "absent", "weight_type": "positive-integer"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_original(path: Path) -> tuple[int, list[tuple[int, int, int]], str]:
    head = None; arcs = []
    for line in path.read_text().splitlines():
        x = line.split()
        if not x or x[0] == "c": continue
        if x[0] == "p" and head is None and len(x) == 4 and x[1] == "sp":
            head = (int(x[2]), int(x[3]))
        elif x[0] == "a" and head is not None and len(x) == 4:
            arcs.append(tuple(map(int, x[1:])))
        else: raise ValueError("original DIMACS malformed")
    if head is None or len(arcs) != head[1]: raise ValueError("original DIMACS count mismatch")
    n = head[0]
    if len({(u,v) for u,v,_ in arcs}) != len(arcs) or any(not (1 <= u <= n and 1 <= v <= n and u != v and w > 0) for u,v,w in arcs):
        raise ValueError("original DIMACS arc contract failed")
    payload = {"format": "mwfas-exp03-graph-v1", "normalization": NORMALIZATION,
               "vertices": list(range(1,n+1)), "arcs": sorted(arcs)}
    graph_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return n, arcs, graph_hash


def validate(n: int, arcs: list[tuple[int, int, int]], rank: list[int]) -> int:
    if len(rank) != n or sorted(rank) != list(range(n)):
        raise ValueError("rank not a complete permutation")
    kept = [[] for _ in range(n)]; indegree = [0] * n; value = 0
    for u, v, w in arcs:
        if rank[u-1] >= rank[v-1]: value += w
        else:
            kept[u-1].append(v-1); indegree[v-1] += 1
    q = deque(i for i, degree in enumerate(indegree) if degree == 0); seen = 0
    while q:
        u = q.popleft(); seen += 1
        for v in kept[u]:
            indegree[v] -= 1
            if indegree[v] == 0: q.append(v)
    if seen != n: raise ValueError("retained graph is cyclic")
    return value


def parse_rank(path: Path, method: str, n: int) -> list[int]:
    if method == "xiong_rasstar":
        return [int(x) for x in path.read_text().split()]
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != n: raise ValueError("IPSNS order row count mismatch")
    rank = [-1] * n; seen = set()
    for row in rows:
        vertex = int(row["Node ID"])
        if vertex < 1 or vertex > n or vertex in seen: raise ValueError("IPSNS vertex coverage failure")
        rank[vertex-1] = int(row["Order"]); seen.add(vertex)
    return rank


def verify_ipsns_completion(folder: Path, n: int, arcs: list[tuple[int,int,int]], raw: dict) -> list[int]:
    with (folder / "order.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    ids = [int(r["Node ID"]) for r in rows]
    original_ranks = [int(r["Order"]) for r in rows]
    if len(ids) != len(set(ids)) or any(v < 1 or v > n for v in ids):
        raise ValueError("raw IPSNS order vertex failure")
    if sorted(original_ranks) != list(range(len(rows))):
        raise ValueError("raw IPSNS rank failure")
    raw_order = [int(r["Node ID"]) for r in sorted(rows, key=lambda r:int(r["Order"]))]
    absent = sorted(set(range(1,n+1)) - set(ids))
    incident = {u for u,_,_ in arcs} | {v for _,v,_ in arcs}
    if any(v in incident for v in absent):
        raise ValueError("raw IPSNS omitted a nonisolated vertex")
    complete = parse_rank(folder / "complete_order.csv", "ipsns", n)
    expected = raw_order + absent
    if [v for v in sorted(range(1,n+1), key=lambda v:complete[v-1])] != expected:
        raise ValueError("derived order changed nonisolated ranks")
    provenance = raw.get("ordering_provenance", {})
    if provenance.get("missing_isolated_vertices") != absent or provenance.get("raw_order_sha256") != sha(folder / "order.csv"):
        raise ValueError("IPSNS isolate provenance mismatch")
    if provenance.get("derived_order_sha256") != sha(folder / "complete_order.csv"):
        raise ValueError("IPSNS derived order hash mismatch")
    raw_positions = {v:i for i,v in enumerate(raw_order)}
    original_objective = sum(w for u,v,w in arcs if raw_positions[u] >= raw_positions[v])
    if abs(original_objective - raw["reported_objective"]) > 1e-7:
        raise ValueError("raw IPSNS objective mismatch")
    if validate(n, arcs, complete) != original_objective:
        raise ValueError("isolate completion changed objective")
    return absent


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--output", required=True, type=Path)
    a = p.parse_args(); out = a.output
    manifest = json.loads((out / "manifest.json").read_text())
    input_by_id = {r["instance_id"]: r for r in manifest["input_inventory"]}
    audited = []; violations = []
    for task in manifest["tasks"]:
        task_id = task["task_id"]; checkpoint = out / "checkpoints" / (task_id + ".json")
        case = {"task_id": task_id, "instance_id": task["instance_id"],
                "algorithm": task["algorithm"], "seed": task["seed"],
                "status": "NOT_VERIFIABLE", "objective": None}
        try:
            cp = json.loads(checkpoint.read_text())
            if any(cp[k] != task[k] for k in ("task_id", "instance_id", "algorithm", "seed", "graph_sha256")):
                raise ValueError("checkpoint identity mismatch")
            case["process_wall_seconds"] = cp["process_wall_seconds"]
            if cp["process_wall_seconds"] > 121 and cp["status"] != "TIMEOUT":
                raise ValueError("completed process exceeded cap")
            source = input_by_id[task["instance_id"]]
            graph = Path(source["path"])
            if sha(graph) != source["dimacs_sha256"]: raise ValueError("DIMACS byte hash mismatch")
            n, arcs, gh = parse_original(graph)
            if gh != source["graph_sha256"] or gh != task["graph_sha256"]:
                raise ValueError("canonical weighted graph hash mismatch")
            if n != source["n"] or len(arcs) != source["m"] or sum(w for _,_,w in arcs) != source["total_weight"]:
                raise ValueError("graph counts or total weight mismatch")
            case["total_weight"] = source["total_weight"]
            if cp["status"] == "TIMEOUT":
                case["status"] = "TIMEOUT"; audited.append(case); continue
            if cp["status"] != "COMPLETED_UNVALIDATED":
                case["status"] = "FAILED"; audited.append(case); continue
            folder = out / "tasks" / task_id
            raw = json.loads((folder / "raw.json").read_text())
            rank_path = folder / ("ranks.txt" if task["algorithm"] == "xiong_rasstar" else "complete_order.csv")
            rank = parse_rank(rank_path, task["algorithm"], n)
            objective = validate(n, arcs, rank)
            if abs(objective - raw["reported_objective"]) > 1e-7:
                raise ValueError("reported weighted objective disagrees")
            if task["algorithm"] == "xiong_rasstar":
                w = (folder / "input.w").read_text().splitlines()
                if list(map(int, w[0].split())) != [n, len(arcs)] or len(w) != len(arcs)+1:
                    raise ValueError("W input count mismatch")
                if [tuple(map(int, x.split())) for x in w[1:]] != [(u-1,v-1,weight) for u,v,weight in arcs]:
                    raise ValueError("W input altered arcs or weights")
                case["algorithm_only_ms"] = raw["algorithm_only_ms"]
            else:
                absent = verify_ipsns_completion(folder, n, arcs, raw)
                if raw["algorithm_info"]["n_iters"] > 200:
                    raise ValueError("IPSNS exceeded iteration budget")
                case["iterations"] = raw["algorithm_info"]["n_iters"]
                case["missing_isolated_vertices"] = ";".join(map(str, absent))
                case["raw_order_status"] = "INCOMPLETE_ISOLATES" if absent else "COMPLETE"
            case.update(status="PASS_DERIVED_ISOLATES" if task["algorithm"] == "ipsns" and absent else "PASS",
                        objective=objective, order_sha256=sha(rank_path))
        except Exception as exc:
            case["status"] = "INVALID"; case["error"] = str(exc)
            violations.append(case)
        audited.append(case)
    if len(audited) != 84: raise ValueError("audit task count mismatch")
    by_key = {(x["instance_id"], x["seed"], x["algorithm"]): x for x in audited}
    pair_rows = []
    for row in manifest["input_inventory"]:
        iid = row["instance_id"]
        for seed in (1, 2):
            x = by_key[iid,seed,"xiong_rasstar"]; i = by_key[iid,seed,"ipsns"]
            pair = {"instance_id": iid, "seed": seed, "xiong_status": x["status"], "ipsns_status": i["status"],
                    "xiong_objective": x["objective"], "ipsns_objective": i["objective"],
                    "total_weight": row["total_weight"], "signed_difference_over_total_weight": None,
                    "xiong_improvement_over_ipsns_fraction": None, "comparison": "NOT_COMPARABLE"}
            if x["status"] == "PASS" and i["status"] in ("PASS", "PASS_DERIVED_ISOLATES"):
                bx, bi = x["objective"], i["objective"]
                pair["comparison"] = "XIONG_WIN" if bx < bi else ("IPSNS_WIN" if bx > bi else "TIE")
                pair["signed_difference_over_total_weight"] = (bx - bi) / row["total_weight"] if row["total_weight"] else None
                pair["xiong_improvement_over_ipsns_fraction"] = (bi - bx) / bi if bi else None
            pair_rows.append(pair)
    fieldnames = sorted({k for r in audited for k in r})
    with (out / "audit_inventory.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames); writer.writeheader(); writer.writerows(audited)
    with (out / "paired_results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(pair_rows[0])); writer.writeheader(); writer.writerows(pair_rows)
    summary = {"format": "exp10-independent-audit-v1", "planned": 84, "audited": len(audited),
               "statuses": {s: sum(x["status"] == s for x in audited)
                            for s in ("PASS","PASS_DERIVED_ISOLATES","FAILED","TIMEOUT","INVALID")},
               "valid_pairs": sum(x["comparison"] != "NOT_COMPARABLE" for x in pair_rows),
               "comparisons": {s: sum(x["comparison"] == s for x in pair_rows)
                               for s in ("XIONG_WIN", "TIE", "IPSNS_WIN", "NOT_COMPARABLE")},
               "violations": violations,
               "total_process_wall_seconds": sum(x.get("process_wall_seconds",0) for x in audited)}
    (out / "audit_report.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    files = ("manifest.json", "audit_inventory.csv", "paired_results.csv", "audit_report.json")
    (out / "checksums.sha256").write_text("".join(f"{sha(out / name)}  {name}\n" for name in files))
    if violations: raise SystemExit("independent audit found invalid outputs")


if __name__ == "__main__":
    main()
