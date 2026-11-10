"""Bounded, passive IPSNS seed-path diagnostic on frozen EXP04 graphs.

The canonical IPSNS source is imported unchanged. Process-local wrappers observe
its RNG calls, deterministic perturbation choices, and objective evaluations.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import random
import resource
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import networkx as nx
import pandas as pd

from mwfas_data.generation import canonical_graph_sha256
from mwfas_data.graph import read_dimacs


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def order_identity(order: list[str]) -> str:
    return hashlib.sha256(("\n".join(order) + "\n").encode()).hexdigest()


def validate_graph(path: Path, item: dict):
    if sha(path) != item["dimacs_sha256"]:
        raise ValueError("frozen DIMACS SHA-256 mismatch")
    graph = read_dimacs(path)
    if len(graph.vertices) != item["n_vertices"] or len(graph.arcs) != item["n_edges"]:
        raise ValueError("frozen graph counts mismatch")
    nxg = nx.DiGraph()
    nxg.add_nodes_from(map(int, graph.vertices))
    nxg.add_weighted_edges_from((int(u), int(v), int(w)) for u, v, w in graph.arcs)
    if canonical_graph_sha256(nxg) != item["graph_sha256"]:
        raise ValueError("frozen weighted graph SHA-256 mismatch")
    if "cyclic_scc_sizes" in item:
        sizes = sorted((len(scc) for scc in nx.strongly_connected_components(nxg) if len(scc) > 1), reverse=True)
        if sizes != item["cyclic_scc_sizes"] or len(sizes) < 2:
            raise ValueError("frozen cyclic SCC structure mismatch")
    return graph


def validate_order(path: Path, graph, reported: float) -> tuple[float, str]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(graph.vertices) or {int(r["Order"]) for r in rows} != set(range(len(graph.vertices))):
        raise ValueError("ordering ranks incomplete")
    order = [r["Node ID"] for r in sorted(rows, key=lambda r: int(r["Order"]))]
    if len(set(order)) != len(order) or set(order) != set(graph.vertices):
        raise ValueError("ordering vertex identities incomplete")
    ranks = {node: i for i, node in enumerate(order)}
    objective = sum(w for u, v, w in graph.arcs if ranks[u] >= ranks[v])
    if not math.isclose(objective, reported, rel_tol=1e-10, abs_tol=1e-7):
        raise ValueError("independent weighted backward objective mismatch")
    return objective, order_identity(order)


class ObservedRandom:
    def __init__(self, state):
        self.state = state

    def seed(self, value=None, version=2):
        self.state["seed_calls"].append(value)
        return random.seed(value, version=version)

    def choices(self, population, weights=None, *, cum_weights=None, k=1):
        chosen = random.choices(population, weights=weights, cum_weights=cum_weights, k=k)
        if k != 1:
            raise ValueError("unexpected IPSNS RNG call")
        self.state["current_iteration"] += 1
        bw, vertices, edges = chosen[0]
        mapping = self.state["index_to_node"]
        member_ids = sorted(str(mapping[i]) for i in vertices)
        self.state["events"].append({
            "iteration": self.state["current_iteration"], "rng_draw": True,
            "candidate_pool_size": len(population), "chosen_scc_backward_weight": float(bw),
            "chosen_scc_size": len(vertices), "chosen_scc_min_vertex": min(member_ids, key=int),
            "chosen_scc_members_sha256": order_identity(member_ids), "chosen_scc_edge_count": len(edges),
        })
        return chosen

    def __getattr__(self, name):
        return getattr(random, name)


class ObservedTime:
    def __init__(self, state):
        self.state = state

    def perf_counter(self):
        value = time.perf_counter()
        if self.state["search_started_at"] is None:
            self.state["search_started_at"] = value
        return value


def observed_run(source: Path, graph_path: Path, order_path: Path, seed: int, config: dict) -> dict:
    if subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() != config["source_revision"]:
        raise ValueError("canonical source revision mismatch")
    sys.path.insert(0, str(source / "src"))
    import mwfas.ipsns as ipsns
    import pandas as pd

    state = {"seed_calls": [], "events": [], "evaluations": [], "current_iteration": 0,
             "index_to_node": None, "output_started_at": None, "search_started_at": None}
    original_random = ipsns.random
    original_time = ipsns.time
    original_read = ipsns.read_graph_dimacs_agg
    original_step = ipsns.lns_step_on_scc
    original_evaluate = ipsns.compute_forward_backward
    original_to_csv = pd.DataFrame.to_csv

    def to_csv_wrapper(self, *args, **kwargs):
        state["output_started_at"] = time.perf_counter()
        return original_to_csv(self, *args, **kwargs)

    def read_wrapper(path):
        result = original_read(path)
        state["index_to_node"] = result[2]
        return result

    def step_wrapper(**kwargs):
        event = state["events"][-1]
        internal = [eid for _, _, _, eid in kwargs["scc_edges"]]
        active, removed = kwargs["active"], kwargs["F"]
        W0, U, V = kwargs["W0"], kwargs["U"], kwargs["V"]
        removed_sorted = sorted((eid for eid in internal if eid in removed),
                                key=lambda eid: (-W0[eid], U[eid], V[eid], eid))
        addback = removed_sorted[:int(kwargs["destroy_addback_frac"] * len(removed_sorted))]
        after_addback = sorted((eid for eid in internal if active[eid] or eid in addback),
                               key=lambda eid: (W0[eid], U[eid], V[eid], eid))
        forced = after_addback[:int(kwargs["destroy_remove_frac"] * len(after_addback))]
        event["perturbation_addback_eids"] = addback
        event["perturbation_remove_eids"] = forced
        event["perturbation_random_draws"] = 0
        return original_step(**kwargs)

    def evaluate_wrapper(edges, scores):
        result = original_evaluate(edges, scores)
        mapping = state["index_to_node"]
        ordered = [str(mapping[i]) for i in sorted(scores, key=scores.get)]
        state["evaluations"].append({"iteration": state["current_iteration"],
                                     "backward_weight": float(result[2]),
                                     "ordering_identity_sha256": order_identity(ordered)})
        return result

    ipsns.random = ObservedRandom(state)
    ipsns.time = ObservedTime(state)
    ipsns.read_graph_dimacs_agg = read_wrapper
    ipsns.lns_step_on_scc = step_wrapper
    ipsns.compute_forward_backward = evaluate_wrapper
    pd.DataFrame.to_csv = to_csv_wrapper
    started = time.perf_counter()
    try:
        p = config["ipsns_parameters"]
        result = ipsns.lns_merge_wmsf_lr_best_incumbent(
            graph_path, order_path, seed_ordering=p["seed_ordering"], iters=config["iteration_budget"],
            topK_scc=p["topK_scc"], destroy_addback_frac=p["destroy_addback_frac"],
            destroy_remove_frac=p["destroy_remove_frac"], tol=p["tol"], rng_seed=seed,
            log_every=0, wmsf_seed_mode=p["wmsf_seed_mode"], scc_select_mode=p["scc_select_mode"],
            return_info=True)
    finally:
        ipsns.random = original_random
        ipsns.time = original_time
        ipsns.read_graph_dimacs_agg = original_read
        ipsns.lns_step_on_scc = original_step
        ipsns.compute_forward_backward = original_evaluate
        pd.DataFrame.to_csv = original_to_csv
    wall = time.perf_counter() - started
    info = result[5]
    evaluations = state["evaluations"]
    if len(evaluations) < 3:
        raise ValueError("missing seed or final objective evaluation")
    # The full WMSF initializer evaluates an internal ordering before its
    # public seed score. Use the final two pre-search evaluations (WMSF, LR).
    initial = [x for x in evaluations[:-1] if x["iteration"] == 0][-2:]
    candidates = [x for x in evaluations[:-1] if x["iteration"] > 0]
    if len(initial) != 2:
        raise ValueError("missing WMSF/LR seed objective evaluations")
    by_iteration = {x["iteration"]: x for x in candidates}
    if len(by_iteration) != len(candidates):
        raise ValueError("multiple candidate objective evaluations in an iteration")
    best = min(initial, key=lambda x: x["backward_weight"])
    best_weight, best_hash = best["backward_weight"], best["ordering_identity_sha256"]
    event_map = {e["iteration"]: e for e in state["events"]}
    checkpoints = {}
    for iteration in range(1, info["n_iters"] + 1):
        event = event_map.get(iteration)
        candidate = by_iteration.get(iteration)
        if event is not None:
            event["candidate_backward_weight"] = candidate["backward_weight"] if candidate else None
            event["candidate_ordering_identity_sha256"] = candidate["ordering_identity_sha256"] if candidate else None
            accepted = candidate is not None and candidate["backward_weight"] < best_weight - 1e-12
            event["accepted_improvement"] = accepted
            if accepted:
                best_weight, best_hash = candidate["backward_weight"], candidate["ordering_identity_sha256"]
            event["incumbent_backward_weight"] = best_weight
        if iteration in config["objective_checkpoints"]:
            checkpoints[str(iteration)] = {"best_backward_weight": best_weight,
                                           "best_ordering_identity_sha256": best_hash}
    if sum(e["accepted_improvement"] for e in state["events"]) != info["n_accepted"]:
        raise ValueError("observed acceptance count differs from canonical result")
    if len(state["events"]) != info["n_iters"] - info["n_noop"] or len(state["seed_calls"]) != 1 or state["seed_calls"][0] != seed:
        raise ValueError("RNG trace differs from canonical selection trace")
    if not math.isclose(best_weight, info["final_bw"], abs_tol=1e-7):
        raise ValueError("observed incumbent differs from final objective")
    if state["output_started_at"] is None or state["search_started_at"] is None:
        raise ValueError("output boundary was not observed")
    initialization_seconds = state["search_started_at"] - started
    search_seconds = max(0.0, state["output_started_at"] - state["search_started_at"])
    return {"status": "COMPLETED", "seed": seed, "rng_seed_calls": state["seed_calls"],
            "rng_draws": len(state["events"]), "events": state["events"], "checkpoints": checkpoints,
            "seed_objectives": [x["backward_weight"] for x in initial],
            "seed_ordering_identity_sha256": best["ordering_identity_sha256"],
            "algorithm_info": info, "reported_final_objective": info["final_bw"],
            "reported_final_ordering_identity_sha256": evaluations[-1]["ordering_identity_sha256"],
            "initialization_seconds": initialization_seconds,
            "search_seconds": search_seconds,
            "total_algorithm_seconds": wall,
            "termination_reason": "no_positive_scc" if info["n_noop"] else "iteration_budget"}


def worker(args) -> None:
    config = json.loads(args.config.read_text())
    item = next(x for x in config["instances"] if x["instance_id"] == args.instance)
    graph = validate_graph(args.graph, item)
    record = observed_run(args.source, args.graph, args.order, args.seed, config)
    if "cyclic_scc_sizes" in item and (not record["events"] or record["events"][0]["candidate_pool_size"] < 2):
        raise ValueError("expected at least two eligible positive-backward SCCs")
    objective, order_hash = validate_order(args.order, graph, record["reported_final_objective"])
    if order_hash != record["reported_final_ordering_identity_sha256"]:
        raise ValueError("instrumented and saved ordering differ")
    record.update(instance_id=args.instance, family=item["family"], graph_sha256=item["graph_sha256"],
                  dimacs_sha256=item["dimacs_sha256"], independent_objective=objective,
                  final_ordering_identity_sha256=order_hash, order_file_sha256=sha(args.order),
                  peak_memory_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    atomic(args.record, record)


def campaign(args) -> None:
    config = json.loads(args.config.read_text())
    if config["status"] != "FROZEN_PILOT" or config["iteration_budget"] != 50 or config["objective_checkpoints"] != [10, 50]:
        raise ValueError("pilot configuration differs from frozen protocol")
    if config["run_cap_seconds"] > 15 or config["campaign_cpu_cap_seconds"] > 1800:
        raise ValueError("pilot exceeds bounded protocol")
    if args.output.exists():
        raise ValueError("output directory exists; refusing overwrite")
    for item in config["instances"]:
        validate_graph(args.graphs / f"{item['instance_id']}.d", item)
    args.output.mkdir(parents=True)
    (args.output / "orders").mkdir()
    (args.output / "runs").mkdir()
    (args.output / "logs").mkdir()
    repository = Path(__file__).resolve().parents[2]
    code_revision = subprocess.check_output(["git", "-C", str(repository), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(repository), "status", "--porcelain"], text=True).strip():
        raise ValueError("pilot requires a clean committed source tree")
    cpu_model = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                      if line.startswith("model name")), None)
    manifest = {"schema": config["schema"], "config_sha256": sha(args.config),
                "code_revision": code_revision,
                "source_revision": config["source_revision"], "source_path": str(args.source.resolve()),
                "graph_dimacs_sha256": {x["instance_id"]: x["dimacs_sha256"] for x in config["instances"]},
                "hostname": platform.node(), "cpu_model": cpu_model, "python": sys.version,
                "networkx_version": nx.__version__, "pandas_version": pd.__version__,
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "command": sys.argv, "status": "RUNNING"}
    atomic(args.output / "run_manifest.json", manifest)
    completed = []
    for item in config["instances"]:
        for seed in config["seeds"]:
            used = resource.getrusage(resource.RUSAGE_CHILDREN)
            cpu_used = used.ru_utime + used.ru_stime
            if cpu_used + config["run_cap_seconds"] > config["campaign_cpu_cap_seconds"]:
                manifest["status"] = "CPU_BUDGET_EXHAUSTED"
                manifest["cpu_seconds"] = cpu_used
                atomic(args.output / "run_manifest.json", manifest)
                return
            rid = f"{item['instance_id']}__s{seed}"
            order = args.output / "orders" / f"{rid}.csv"
            record = args.output / "runs" / f"{rid}.json"
            command = [sys.executable, __file__, "worker", "--config", str(args.config.resolve()),
                       "--source", str(args.source.resolve()), "--graph", str((args.graphs / f"{item['instance_id']}.d").resolve()),
                       "--instance", item["instance_id"], "--seed", str(seed), "--order", str(order.resolve()),
                       "--record", str(record.resolve())]
            started = time.perf_counter()
            with (args.output / "logs" / f"{rid}.log").open("x") as log:
                try:
                    process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False,
                                             timeout=config["run_cap_seconds"],
                                             env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                                                  "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"})
                    status = "COMPLETED" if process.returncode == 0 and record.exists() else "FAIL"
                except subprocess.TimeoutExpired:
                    status = "CENSORED_TIMEOUT"
            elapsed = time.perf_counter() - started
            if status != "COMPLETED":
                atomic(record, {"instance_id": item["instance_id"], "seed": seed, "status": status,
                                "wall_seconds": elapsed, "run_cap_seconds": config["run_cap_seconds"]})
            else:
                saved = json.loads(record.read_text())
                graph = validate_graph(args.graphs / f"{item['instance_id']}.d", item)
                objective, order_hash = validate_order(order, graph, saved["independent_objective"])
                if objective != saved["independent_objective"] or order_hash != saved["final_ordering_identity_sha256"]:
                    raise ValueError("parent independent validation mismatch")
            completed.append({"run_id": rid, "status": status, "wall_seconds": elapsed})
            manifest["recorded"] = len(completed)
            manifest["completed"] = sum(x["status"] == "COMPLETED" for x in completed)
            manifest["timeouts"] = sum(x["status"] == "CENSORED_TIMEOUT" for x in completed)
            manifest["failures"] = sum(x["status"] == "FAIL" for x in completed)
            manifest["last_heartbeat_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            atomic(args.output / "run_manifest.json", manifest)
    used = resource.getrusage(resource.RUSAGE_CHILDREN)
    manifest["cpu_seconds"] = used.ru_utime + used.ru_stime
    expected = len(config["instances"]) * len(config["seeds"])
    manifest["expected"] = expected
    manifest["status"] = "COMPLETE" if manifest["completed"] == expected else "INCOMPLETE"
    manifest["ended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    atomic(args.output / "run_manifest.json", manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    w = sub.add_parser("worker")
    for name in ("config", "source", "graph", "order", "record"):
        w.add_argument(f"--{name}", type=Path, required=True)
    w.add_argument("--instance", required=True)
    w.add_argument("--seed", type=int, required=True)
    c = sub.add_parser("campaign")
    for name in ("config", "source", "graphs", "output"):
        c.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    worker(args) if args.mode == "worker" else campaign(args)
