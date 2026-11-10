"""Reparse EXP09 raw evidence without importing the run-time adapter."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path


NORMALIZATION = {"directed": True, "node_labels": "1-based-integers",
                 "parallel_edges": "absent", "self_loops": "absent",
                 "weight_type": "positive-integer"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_dimacs(path: Path):
    n = m = None
    arcs = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts or parts[0] == "c":
            continue
        if parts[0] == "p":
            if n is not None or len(parts) != 4:
                raise ValueError("bad DIMACS header")
            n, m = int(parts[2]), int(parts[3])
        elif parts[0] == "a":
            if len(parts) != 4:
                raise ValueError("bad DIMACS arc")
            arcs.append(tuple(map(int, parts[1:])))
        else:
            raise ValueError("unknown DIMACS record")
    if n is None or m != len(arcs) or any(w < 0 for _, _, w in arcs):
        raise ValueError("DIMACS count or weight error")
    endpoints = {v for u, v, _ in arcs} | {u for u, v, _ in arcs}
    start = 0 if 0 in endpoints else 1
    vertices = set(range(start, start + n))
    if not endpoints <= vertices:
        raise ValueError("DIMACS vertex identity error")
    return vertices, arcs


def weighted_identity(vertices, arcs):
    if any(u == v or w <= 0 for u, v, w in arcs) or len({(u, v) for u, v, _ in arcs}) != len(arcs):
        raise ValueError("canonical weighted identity requires positive simple loopless arcs")
    payload = {"format": "mwfas-exp03-graph-v1", "normalization": NORMALIZATION,
               "vertices": sorted(vertices), "arcs": sorted(arcs)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def check_dag(vertices, arcs, ranks):
    indegree = {v: 0 for v in vertices}
    forward = {v: [] for v in vertices}
    for u, v, _ in arcs:
        if ranks[u] < ranks[v]:
            forward[u].append(v)
            indegree[v] += 1
    queue = deque(v for v, degree in indegree.items() if degree == 0)
    seen = 0
    while queue:
        u = queue.popleft()
        seen += 1
        for v in forward[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    return seen == len(vertices)


def audit(config_path: Path, graphs: Path, output: Path, report_path: Path) -> dict:
    if report_path.exists():
        raise ValueError("independent audit report already exists")
    config = json.loads(config_path.read_text())
    manifest = json.loads((output / "run_manifest.json").read_text())
    if manifest["config_sha256"] != sha(config_path) or manifest["external_source_revision"] != config["external_source_revision"]:
        raise ValueError("manifest provenance mismatch")
    checks = []
    for item in config["instances"]:
        graph_path = graphs / item["graph_file"]
        if sha(graph_path) != item["dimacs_sha256"]:
            raise ValueError("DIMACS hash mismatch")
        vertices, arcs = parse_dimacs(graph_path)
        if len(vertices) != item["n_vertices"] or len(arcs) != item["n_edges"] or \
                weighted_identity(vertices, arcs) != item["graph_sha256"]:
            raise ValueError("weighted graph identity mismatch")
        grouped = defaultdict(int)
        for u, v, w in arcs:
            if u != v:
                grouped[u, v] += w
        converted = output / "external_inputs" / f"{item['instance_id']}.csv"
        with converted.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        observed = {(int(r["source"]), int(r["target"])): int(r["weight"]) for r in rows}
        if len(observed) != len(rows) or observed != dict(grouped):
            raise ValueError("external input conversion mismatch")
        active = {v for pair in grouped for v in pair}
        isolated = sorted(vertices - active)
        for seed in config["seeds"]:
            run_id = f"{item['instance_id']}__s{seed}"
            record = json.loads((output / "runs" / f"{run_id}.json").read_text())
            if record["status"] != "PASS" or record["graph_sha256"] != item["graph_sha256"]:
                checks.append({"run_id": run_id, "status": "FAIL", "reason": "record status or identity"})
                continue
            raw = output / "raw" / f"{run_id}.txt"
            raw_lines = raw.read_text().splitlines()
            if not raw_lines or not raw_lines[0].startswith("forward_score\t"):
                raise ValueError(f"{run_id}: malformed original C output")
            native_score = int(raw_lines[0].split("\t")[1])
            native_order = [int(x) for x in raw_lines[1:]]
            if len(native_order) != len(active) or set(native_order) != active:
                raise ValueError(f"{run_id}: incomplete original C ordering")
            full_order = native_order + isolated
            saved = output / "orders" / f"{run_id}.csv"
            with saved.open(newline="") as stream:
                ordered_rows = list(csv.DictReader(stream))
            saved_order = [int(r["Node ID"]) for r in sorted(ordered_rows, key=lambda r: int(r["Order"]))]
            if len(saved_order) != len(vertices) or saved_order != full_order or \
                    {int(r["Order"]) for r in ordered_rows} != set(range(len(vertices))):
                raise ValueError(f"{run_id}: saved order mismatch")
            ranks = {v: index for index, v in enumerate(full_order)}
            objective = sum(w for u, v, w in arcs if ranks[u] >= ranks[v])
            forward = sum(w for u, v, w in arcs if ranks[u] < ranks[v])
            order_hash = hashlib.sha256(("\n".join(map(str, full_order)) + "\n").encode()).hexdigest()
            if objective != record["objective"] or forward != native_score or \
                    order_hash != record["ordering_sha256"] or sha(raw) != record["raw_output_sha256"] or \
                    sha(saved) != record["order_file_sha256"] or not check_dag(vertices, arcs, ranks):
                raise ValueError(f"{run_id}: independent objective, hash, or DAG mismatch")
            checks.append({"run_id": run_id, "status": "PASS", "objective": objective,
                           "forward": forward, "ordering_sha256": order_hash})
    result = {"schema": "mwfas-exp09-independent-audit-v1", "config_sha256": sha(config_path),
              "pilot_code_revision": manifest["code_revision"], "external_source_revision": manifest["external_source_revision"],
              "expected": len(config["instances"]) * len(config["seeds"]), "passed": sum(x["status"] == "PASS" for x in checks),
              "failed": sum(x["status"] == "FAIL" for x in checks), "checks": checks}
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.config, args.graphs, args.output, args.report)
    print(json.dumps({key: result[key] for key in ("expected", "passed", "failed")}, sort_keys=True))
