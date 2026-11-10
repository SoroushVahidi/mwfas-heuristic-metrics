"""Bounded same-graph EXP09 insertion comparator using existing project code."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

from mwfas_data.exp05_insertion import optimize
from mwfas_data.graph import acyclic_after_removal, backward_weight, read_dimacs


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def read_order(path: Path, vertices: tuple[str, ...]) -> list[str]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(vertices) or {int(row["Order"]) for row in rows} != set(range(len(vertices))):
        raise ValueError("seed order ranks incomplete")
    order = [row["Node ID"] for row in sorted(rows, key=lambda row: int(row["Order"]))]
    if set(order) != set(vertices) or len(set(order)) != len(vertices):
        raise ValueError("seed order vertices incomplete")
    return order


def validate(graph, order: list[str], objective: float) -> str:
    score = backward_weight(graph, order)
    if score != objective:
        raise ValueError("independent insertion objective mismatch")
    ranks = {node: i for i, node in enumerate(order)}
    removed = {(u, v) for u, v, _ in graph.arcs if ranks[u] >= ranks[v]}
    if not acyclic_after_removal(graph, removed):
        raise ValueError("insertion order leaves a cycle after removal")
    return hashlib.sha256(("\n".join(order) + "\n").encode()).hexdigest()


def worker(args) -> None:
    start = time.perf_counter()
    graph = read_dimacs(args.graph)
    initial = read_order(args.seed_order, graph.vertices)
    result = optimize(graph, initial, max_moves=1000, deadline=time.monotonic() + 110)
    ordering_hash = validate(graph, result.order, result.final_objective)
    if result.final_objective > result.initial_objective:
        raise ValueError("insertion worsened seed")
    with args.order.open("x", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Node ID", "Order"])
        writer.writerows((node, rank) for rank, node in enumerate(result.order))
    atomic(args.record, {"instance_id": args.instance, "algorithm": args.algorithm,
                         "status": "CENSORED_DEADLINE" if result.termination_reason == "deadline" else "PASS",
                         "initial_objective": result.initial_objective, "objective": result.final_objective,
                         "accepted_moves": result.accepted_moves, "termination_reason": result.termination_reason,
                         "refinement_seconds": result.refinement_seconds,
                         "total_wall_seconds": time.perf_counter() - start,
                         "seed_order_sha256": sha(args.seed_order), "ordering_sha256": ordering_hash,
                         "order_file_sha256": sha(args.order),
                         "peak_memory_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


def campaign(args) -> None:
    config = json.loads(args.config.read_text())
    if len(config["instances"]) != 12 or args.output.exists():
        raise ValueError("frozen selection or new output directory required")
    code_root = Path(__file__).resolve().parents[2]
    revision = subprocess.check_output(["git", "-C", str(code_root), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(code_root), "status", "--porcelain"], text=True).strip():
        raise ValueError("comparison requires committed clean release")
    for sub in ("runs", "orders", "logs"):
        (args.output / sub).mkdir(parents=True, exist_ok=False)
    manifest = {"status": "RUNNING", "code_revision": revision, "config_sha256": sha(args.config),
                "host": platform.node(), "python": sys.version, "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "command": sys.argv, "expected": 24, "recorded": 0,
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    atomic(args.output / "run_manifest.json", manifest)
    for item in config["instances"]:
        graph = args.graphs / item["graph_file"]
        if sha(graph) != item["dimacs_sha256"]:
            raise ValueError("frozen graph hash mismatch")
        for method in ("lrta", "wmsf_l2"):
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            if usage.ru_utime + usage.ru_stime + 120 > 7200:
                manifest["status"] = "CPU_BUDGET_EXHAUSTED"
                atomic(args.output / "run_manifest.json", manifest)
                return
            run_id = f"{item['instance_id']}__insertion_{method}"
            seed_order = args.seed_orders / f"{item['instance_id']}__{method}.csv"
            order = args.output / "orders" / f"{run_id}.csv"
            record = args.output / "runs" / f"{run_id}.json"
            command = [sys.executable, __file__, "worker", "--graph", str(graph), "--seed-order", str(seed_order),
                       "--order", str(order), "--record", str(record), "--instance", item["instance_id"],
                       "--algorithm", f"insertion_{method}"]
            with (args.output / "logs" / f"{run_id}.log").open("x") as stream:
                try:
                    p = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=120, check=False)
                    status = "PASS" if p.returncode == 0 and record.exists() else "FAIL"
                except subprocess.TimeoutExpired:
                    status = "CENSORED_TIMEOUT"
            if status == "PASS":
                saved = json.loads(record.read_text())
                status = saved["status"]
                original = read_dimacs(graph)
                order_nodes = read_order(order, original.vertices)
                if validate(original, order_nodes, saved["objective"]) != saved["ordering_sha256"]:
                    raise ValueError("parent insertion validation mismatch")
            else:
                atomic(record, {"instance_id": item["instance_id"], "algorithm": f"insertion_{method}", "status": status})
            manifest["recorded"] += 1
            manifest["passed"] = manifest.get("passed", 0) + (status == "PASS")
            manifest["censored"] = manifest.get("censored", 0) + status.startswith("CENSORED")
            manifest["failed"] = manifest.get("failed", 0) + (status == "FAIL")
            manifest["last_heartbeat_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            atomic(args.output / "run_manifest.json", manifest)
            if status == "PASS" and not (args.output / "startup_health.json").exists():
                atomic(args.output / "startup_health.json", {"status": "PASS", "first_validated_run": run_id,
                            "heartbeat_utc": manifest["last_heartbeat_utc"]})
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    manifest["cpu_seconds"] = usage.ru_utime + usage.ru_stime
    manifest["status"] = "COMPLETE" if manifest.get("passed", 0) == 24 else "INCOMPLETE"
    manifest["ended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    atomic(args.output / "run_manifest.json", manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    w = sub.add_parser("worker")
    for name in ("graph", "seed_order", "order", "record"):
        w.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    w.add_argument("--instance", required=True)
    w.add_argument("--algorithm", required=True)
    c = sub.add_parser("campaign")
    for name in ("config", "graphs", "seed_orders", "output"):
        c.add_argument(f"--{name.replace('_', '-')}", type=Path, required=True)
    args = parser.parse_args()
    worker(args) if args.mode == "worker" else campaign(args)
