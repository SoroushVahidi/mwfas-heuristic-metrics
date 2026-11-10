"""EXP09 bounded adapter and independent audit for Bader-Research C components."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

import networkx as nx

from mwfas_data.generation import canonical_graph_sha256
from mwfas_data.graph import acyclic_after_removal, backward_weight, read_dimacs


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, data: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def load_frozen_graph(path: Path, item: dict):
    if digest(path) != item["dimacs_sha256"]:
        raise ValueError("DIMACS SHA-256 mismatch")
    graph = read_dimacs(path)
    if len(graph.vertices) != item["n_vertices"] or len(graph.arcs) != item["n_edges"]:
        raise ValueError("graph counts mismatch")
    nx_graph = nx.DiGraph()
    nx_graph.add_nodes_from(map(int, graph.vertices))
    for u, v, w in graph.arcs:
        if not float(w).is_integer():
            raise ValueError("external C library requires integral weights")
        nx_graph.add_edge(int(u), int(v), weight=int(w))
    if canonical_graph_sha256(nx_graph) != item["graph_sha256"]:
        raise ValueError("weighted graph SHA-256 mismatch")
    return graph


def convert_to_external_csv(graph, path: Path) -> dict:
    """Aggregate parallel arcs via read_dimacs; omit constant self-loops."""
    vertices = {int(v) for v in graph.vertices}
    if any(v < 0 or v > 2**64 - 1 for v in vertices):
        raise ValueError("external loader requires unsigned 64-bit IDs")
    active = set()
    self_loop_weight = 0
    with path.open("x", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["source", "target", "weight"])
        for u, v, weight in graph.arcs:
            if not float(weight).is_integer() or not 0 <= weight <= 2**31 - 1:
                raise ValueError("external C library requires nonnegative int32 arc weights")
            if u == v:
                self_loop_weight += int(weight)
                continue
            writer.writerow([u, v, int(weight)])
            active.update((int(u), int(v)))
    if not active:
        raise ValueError("external loader cannot represent a graph with no non-loop arcs")
    return {"active_vertices": sorted(active), "isolated_vertices": sorted(vertices - active),
            "self_loop_constant": self_loop_weight, "external_csv_sha256": digest(path),
            "external_arc_count": sum(u != v for u, v, _ in graph.arcs)}


def validate_raw_order(graph, raw_path: Path, expected_active: list[int]) -> dict:
    lines = raw_path.read_text().splitlines()
    if not lines or not lines[0].startswith("forward_score\t"):
        raise ValueError("malformed external result header")
    try:
        external_forward = int(lines[0].split("\t", 1)[1])
        external_order = [int(x) for x in lines[1:]]
    except ValueError as exc:
        raise ValueError("malformed external ordering or score") from exc
    if len(external_order) != len(expected_active) or set(external_order) != set(expected_active):
        raise ValueError("external ordering is not an active-vertex permutation")
    isolated = sorted({int(v) for v in graph.vertices} - set(expected_active))
    full_order = [str(v) for v in external_order + isolated]
    objective = backward_weight(graph, full_order)
    total = sum(w for _, _, w in graph.arcs)
    if not math.isclose(total - objective, external_forward, rel_tol=0, abs_tol=1e-7):
        raise ValueError("external forward score differs from original-graph objective")
    rank = {v: i for i, v in enumerate(full_order)}
    removed = {(u, v) for u, v, _ in graph.arcs if rank[u] >= rank[v]}
    if not acyclic_after_removal(graph, removed):
        raise ValueError("removing backward arcs left a cycle")
    order_hash = hashlib.sha256(("\n".join(full_order) + "\n").encode()).hexdigest()
    return {"external_forward_score": external_forward, "objective": objective,
            "ordering": full_order, "ordering_sha256": order_hash,
            "appended_isolated_vertices": isolated, "removed_arc_count": len(removed)}


def write_order(path: Path, ordering: list[str]) -> None:
    with path.open("x", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Node ID", "Order"])
        writer.writerows((node, rank) for rank, node in enumerate(ordering))


def run_one(item: dict, seed: int, config: dict, graphs: Path, binary: Path, output: Path) -> dict:
    run_id = f"{item['instance_id']}__s{seed}"
    graph_path = graphs / item["graph_file"]
    start = time.perf_counter()
    graph = load_frozen_graph(graph_path, item)
    external_input = output / "external_inputs" / f"{item['instance_id']}.csv"
    if external_input.exists():
        converted = {"active_vertices": sorted({int(u) for u, v, _ in graph.arcs if u != v} |
                                             {int(v) for u, v, _ in graph.arcs if u != v}),
                     "isolated_vertices": sorted({int(v) for v in graph.vertices} -
                                                 {int(x) for u, v, _ in graph.arcs if u != v for x in (u, v)}),
                     "self_loop_constant": int(sum(w for u, v, w in graph.arcs if u == v)),
                     "external_csv_sha256": digest(external_input),
                     "external_arc_count": sum(u != v for u, v, _ in graph.arcs)}
    else:
        converted = convert_to_external_csv(graph, external_input)
    raw = output / "raw" / f"{run_id}.txt"
    log = output / "logs" / f"{run_id}.log"
    command = [str(binary), str(external_input), str(raw), str(seed),
               str(config["okubo_epochs"]), str(config["anneal_iterations"]),
               str(config["anneal_go_back_window"]), str(config["anneal_toposhuffle_frequency"])]
    remaining = config["run_cap_seconds"] - (time.perf_counter() - start)
    if remaining <= 0:
        return {"run_id": run_id, "status": "CENSORED_TIMEOUT", "total_wall_seconds": time.perf_counter() - start}
    with log.open("x") as stream:
        try:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                     timeout=remaining, check=False, env={**os.environ, "OMP_NUM_THREADS": "1"})
            status = "PASS" if process.returncode == 0 and raw.exists() else "FAIL"
        except subprocess.TimeoutExpired:
            status = "CENSORED_TIMEOUT"
    result = {"run_id": run_id, "instance_id": item["instance_id"], "seed": seed,
              "status": status, "command": command, "graph_sha256": item["graph_sha256"],
              "dimacs_sha256": item["dimacs_sha256"], "transformation": converted,
              "total_wall_seconds": time.perf_counter() - start,
              "external_input_sha256": digest(external_input), "log_path": str(log)}
    if status == "PASS":
        checked = validate_raw_order(graph, raw, converted["active_vertices"])
        order_path = output / "orders" / f"{run_id}.csv"
        write_order(order_path, checked.pop("ordering"))
        result.update(checked)
        result.update(raw_output_sha256=digest(raw), order_file_sha256=digest(order_path))
    result["peak_child_memory_kib"] = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return result


def campaign(args) -> None:
    config = json.loads(args.config.read_text())
    if config["status"] != "FROZEN_SELECTION" or len(config["instances"]) > 12 or \
            config["run_cap_seconds"] > 120 or config["campaign_cpu_cap_seconds"] > 7200:
        raise ValueError("campaign exceeds frozen pilot limits")
    if args.output.exists():
        raise ValueError("output already exists; raw evidence cannot be overwritten")
    source_revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    if source_revision != config["external_source_revision"]:
        raise ValueError("external source revision mismatch")
    code_root = Path(__file__).resolve().parents[2]
    code_revision = subprocess.check_output(["git", "-C", str(code_root), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(code_root), "status", "--porcelain"], text=True).strip():
        raise ValueError("pilot requires a committed clean release")
    for item in config["instances"]:
        load_frozen_graph(args.graphs / item["graph_file"], item)
    for sub in ("runs", "raw", "orders", "logs", "external_inputs"):
        (args.output / sub).mkdir(parents=True, exist_ok=False)
    cpu_model = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                      if line.startswith("model name")), None)
    manifest = {"schema": config["schema"], "status": "RUNNING", "config_sha256": digest(args.config),
                "code_revision": code_revision, "external_source_revision": source_revision,
                "external_source_path": str(args.source.resolve()), "binary_sha256": digest(args.binary),
                "host": platform.node(), "cpu_model": cpu_model, "python": sys.version,
                "networkx": nx.__version__, "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "command": sys.argv, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "expected": len(config["instances"]) * len(config["seeds"]), "recorded": 0}
    atomic_json(args.output / "run_manifest.json", manifest)
    for item in config["instances"]:
        for seed in config["seeds"]:
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu_used = usage.ru_utime + usage.ru_stime
            if cpu_used + config["run_cap_seconds"] > config["campaign_cpu_cap_seconds"]:
                manifest["status"] = "CPU_BUDGET_EXHAUSTED"
                manifest["cpu_seconds"] = cpu_used
                atomic_json(args.output / "run_manifest.json", manifest)
                return
            run_id = f"{item['instance_id']}__s{seed}"
            try:
                result = run_one(item, seed, config, args.graphs, args.binary, args.output)
            except Exception as exc:
                result = {"run_id": run_id, "instance_id": item["instance_id"], "seed": seed,
                          "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
            atomic_json(args.output / "runs" / f"{run_id}.json", result)
            manifest["recorded"] += 1
            manifest["passed"] = manifest.get("passed", 0) + (result["status"] == "PASS")
            manifest["timeouts"] = manifest.get("timeouts", 0) + (result["status"] == "CENSORED_TIMEOUT")
            manifest["failures"] = manifest.get("failures", 0) + (result["status"] == "FAIL")
            manifest["last_heartbeat_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            atomic_json(args.output / "run_manifest.json", manifest)
            if result["status"] == "PASS" and not (args.output / "startup_health.json").exists():
                atomic_json(args.output / "startup_health.json", {"status": "PASS", "first_independently_validated_run": run_id,
                            "heartbeat_utc": manifest["last_heartbeat_utc"]})
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    manifest["cpu_seconds"] = usage.ru_utime + usage.ru_stime
    manifest["status"] = "COMPLETE" if manifest.get("passed", 0) == manifest["expected"] else "INCOMPLETE"
    manifest["ended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    atomic_json(args.output / "run_manifest.json", manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--graphs", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    campaign(parser.parse_args())
