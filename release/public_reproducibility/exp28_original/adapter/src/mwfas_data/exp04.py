"""Frozen EXP04 topology replication, stable work identities and partial exports."""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
import time
from pathlib import Path

import networkx as nx

from .config import ROOT
from .exp03 import atomic_json, sha256_file, write_parquet_atomic
from .generation import canonical_graph_sha256, generate_candidate, structural_properties, write_dimacs

CONFIG_PATH = ROOT / "configs/exp04.json"
SELECTION_PATH = ROOT / "data/manifests/exp04_selection.json"
GENERATOR_PATH = ROOT / "src/mwfas_data/generation.py"
INSTRUMENTED_PATH = ROOT / "experiments/exp04_independent_replication/ipsns_instrumented.py"
EXP03_SELECTION_PATH = ROOT / "data/manifests/exp03_selection.json"
FAMILY_CODES = {"erdos_renyi_directed": "er", "directed_scale_free": "sf", "directed_community": "cm"}


def load_config() -> dict:
    config = json.loads(CONFIG_PATH.read_text())
    if config["status"] != "FROZEN_PRIMARY_DESIGN" or config["paired_weight_extension"]:
        raise ValueError("EXP04 primary configuration is not frozen")
    if len(config["families"]) != 3 or config["replicates"] != 5:
        raise ValueError("EXP04 factorial design changed")
    return config


def specs(config: dict) -> list[dict]:
    result = []
    for degree in config["mean_out_degrees"]:
        for size in config["sizes"]:
            for family_index, family in enumerate(config["families"]):
                for replicate in range(1, config["replicates"] + 1):
                    offset = family_index * 10_000_000 + size * 10_000 + degree * 100 + replicate
                    result.append({"instance_id": f"exp04_{FAMILY_CODES[family]}_n{size:03d}_k{degree:02d}_r{replicate:02d}",
                                   "family": family, "n_vertices": size, "target_mean_out_degree": degree,
                                   "replicate": replicate, "generation_seed": config["topology_seed_base"] + offset,
                                   "weight_seed": config["weight_seed_base"] + offset})
    return result


def topology_sha256(graph: nx.DiGraph) -> str:
    payload = {"format": "exp04-topology-v1", "directed": True,
               "vertices": sorted(int(v) for v in graph.nodes()),
               "arcs": sorted((int(u), int(v)) for u, v in graph.edges())}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _cv(values) -> float:
    values = list(values)
    average = statistics.mean(values)
    return statistics.pstdev(values) / average if average else 0.0


def extra_properties(graph: nx.DiGraph) -> dict:
    n = graph.number_of_nodes()
    arcs = list(graph.edges())
    return {"topology_sha256": topology_sha256(graph),
            "total_graph_weight": sum(graph[u][v]["weight"] for u, v in arcs),
            "in_degree_cv": _cv(graph.in_degree(v) for v in graph),
            "out_degree_cv": _cv(graph.out_degree(v) for v in graph),
            "total_degree_cv": _cv(graph.degree(v) for v in graph),
            "reciprocity": nx.reciprocity(graph),
            "community_internal_arc_fraction": sum((u <= n // 2) == (v <= n // 2) for u, v in arcs) / len(arcs)}


def generate_selection(workdir: Path, *, freeze: bool = False) -> dict:
    config = load_config()
    old = json.loads(EXP03_SELECTION_PATH.read_text())
    old_seeds = {row["generation_seed_actual"] for row in old["instances"]}
    old_topology_seeds = {row["generation_seed"] for row in old["instances"]}
    config_hash = sha256_file(CONFIG_PATH)
    generator_hash = sha256_file(GENERATOR_PATH)
    instrumented_hash = sha256_file(INSTRUMENTED_PATH)
    graph_dir = workdir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    seen_topologies = set()
    seen_weighted = set()
    for spec in specs(config):
        if spec["generation_seed"] in old_seeds | old_topology_seeds:
            raise ValueError("EXP04 generation seed collides with EXP03")
        graph = generate_candidate(spec["family"], spec["n_vertices"], spec["generation_seed"],
                                   spec["target_mean_out_degree"], spec["weight_seed"])
        props = structural_properties(graph) | extra_properties(graph)
        if props["isolated_vertices"] or props["topology_sha256"] in seen_topologies or props["graph_sha256"] in seen_weighted:
            raise ValueError(f"invalid or repeated fixed-seed graph: {spec['instance_id']}")
        seen_topologies.add(props["topology_sha256"])
        seen_weighted.add(props["graph_sha256"])
        path = graph_dir / f"{spec['instance_id']}.d"
        write_dimacs(graph, path)
        rows.append(spec | props | {"graph_file": path.name, "dimacs_sha256": sha256_file(path),
                    "generator_sha256": generator_hash, "config_sha256": config_hash,
                    "source_type": "generated", "weight_distribution": config["weight_distribution"],
                    "generator_revision": "a9fda5af7a4cf390ad06085f118f3512a953c832"})
    if len(rows) != 135:
        raise ValueError("EXP04 selection must contain 135 independent topologies")
    selection = {"format": "mwfas-exp04-selection-v1", "config_sha256": config_hash,
                 "generator_sha256": generator_hash, "instrumented_sha256": instrumented_hash,
                 "source_revision": config["source_revision"], "dataset_revision": config["dataset_revision"],
                 "instances": rows}
    if SELECTION_PATH.exists():
        if selection != json.loads(SELECTION_PATH.read_text()):
            raise ValueError("generated graphs differ from committed EXP04 selection")
    elif freeze:
        atomic_json(SELECTION_PATH, selection)
    else:
        raise ValueError("missing committed EXP04 selection")
    write_parquet_atomic(workdir / "instances.parquet", rows)
    write_parquet_atomic(workdir / "graph_properties.parquet", rows)
    return selection


def verify_selection(workdir: Path) -> dict:
    selection = json.loads(SELECTION_PATH.read_text())
    for name, actual in (("config_sha256", sha256_file(CONFIG_PATH)),
                         ("generator_sha256", sha256_file(GENERATOR_PATH)),
                         ("instrumented_sha256", sha256_file(INSTRUMENTED_PATH))):
        if selection[name] != actual:
            raise ValueError(f"EXP04 {name} changed")
    for row in selection["instances"]:
        if sha256_file(workdir / "graphs" / row["graph_file"]) != row["dimacs_sha256"]:
            raise ValueError(f"graph file changed: {row['instance_id']}")
    return selection


def expected_tasks(selection: dict, config: dict) -> list[dict]:
    tasks = []
    for algorithm in ("lrta", "wmsf_l2", "igraph_eades_weighted"):
        for row in selection["instances"]:
            tasks.append({"run_id": f"{row['instance_id']}__{algorithm}", "instance_id": row["instance_id"],
                          "algorithm": algorithm, "seed": None, "budget": None})
    for budget in config["ipsns_iteration_budgets"]:
        for row in selection["instances"]:
            for seed in config["ipsns_seeds"]:
                tasks.append({"run_id": f"{row['instance_id']}__ipsns_b{budget:03d}_s{seed}",
                              "instance_id": row["instance_id"], "algorithm": "ipsns",
                              "seed": seed, "budget": budget})
    if len(tasks) != 2025 or len({t["run_id"] for t in tasks}) != 2025:
        raise ValueError("EXP04 task count or identity changed")
    return tasks


RUN_COLUMNS = ["run_id", "instance_id", "family", "n_vertices", "target_mean_out_degree", "replicate",
               "topology_sha256", "graph_sha256", "algorithm", "algorithm_version", "seed", "iteration_budget",
               "budget_semantics", "status", "reported_objective", "objective_weight", "total_graph_weight",
               "normalized_objective", "fas_weight", "fas_sha256", "ordering_valid", "objective_match",
               "acyclicity_valid", "fas_acyclicity_valid", "total_wall_seconds", "algorithm_wall_seconds",
               "initialization_seconds", "conversion_seconds", "peak_memory_kib", "lrta_objective",
               "wmsf_objective", "better_seed_objective", "improvement_over_lrta", "improvement_over_wmsf",
               "improvement_over_better_seed", "relative_improvement_over_better_seed",
               "strict_improvement_over_better_seed", "accepted_improving_moves", "best_iteration",
               "time_to_best_seconds_after_initialization", "iterations_executed", "termination_reason",
               "source_revision", "code_revision", "config_sha256", "command", "order_sha256", "error"]


def pilot_tasks(tasks: list[dict]) -> list[dict]:
    ids = {"exp04_er_n120_k03_r01", "exp04_cm_n240_k05_r01",
           "exp04_sf_n480_k08_r01", "exp04_er_n480_k08_r01"}
    return [t for t in tasks if t["instance_id"] in ids and
            (t["algorithm"] != "ipsns" or
             (t["seed"] == 1 and t["budget"] == (50 if "n480" in t["instance_id"] else 400)))]


def export_partial(workdir: Path, selection: dict, tasks: list[dict]) -> dict:
    rows = []
    for task in tasks:
        path = workdir / "runs" / f"{task['run_id']}.json"
        if path.exists():
            rows.append(json.loads(path.read_text()))
    write_parquet_atomic(workdir / "algorithm_runs.parquet", rows, RUN_COLUMNS)
    budgets = [{"run_id": r["run_id"], "instance_id": r["instance_id"], "topology_sha256": r["topology_sha256"],
                "seed": r["seed"], "iteration_budget": r["iteration_budget"], "status": r["status"],
                "semantics": "independent_fresh_run", "better_seed_objective": r["better_seed_objective"],
                "final_objective": r["objective_weight"], "strict_improvement": r["strict_improvement_over_better_seed"],
                "absolute_improvement": r["improvement_over_better_seed"],
                "relative_improvement": r["relative_improvement_over_better_seed"],
                "total_wall_seconds": r["total_wall_seconds"], "iterations_executed": r["iterations_executed"]}
               for r in rows if r["algorithm"] == "ipsns"]
    write_parquet_atomic(workdir / "budget_comparisons.parquet", budgets,
                         ["run_id", "instance_id", "topology_sha256", "seed", "iteration_budget", "status",
                          "semantics", "better_seed_objective", "final_objective", "strict_improvement",
                          "absolute_improvement", "relative_improvement", "total_wall_seconds", "iterations_executed"])
    groups = {}
    expected = {}
    instance_map = {r["instance_id"]: r for r in selection["instances"]}
    for task in tasks:
        instance = instance_map[task["instance_id"]]
        key = (instance["family"], instance["n_vertices"], instance["target_mean_out_degree"],
               task["algorithm"], task["budget"])
        expected[key] = expected.get(key, 0) + 1
    for row in rows:
        key = (row["family"], row["n_vertices"], row["target_mean_out_degree"], row["algorithm"], row["iteration_budget"])
        groups.setdefault(key, []).append(row)
    group_rows = []
    for key, count in expected.items():
        present = groups.get(key, [])
        valid = [r for r in present if r["status"] == "PASS"]
        group_rows.append({"family": key[0], "n_vertices": key[1], "target_mean_out_degree": key[2],
                           "algorithm": key[3], "iteration_budget": key[4], "expected_runs": count,
                           "recorded_runs": len(present), "validated_runs": len(valid),
                           "failed_or_timeout_runs": sum(r["status"] in ("FAIL", "TIMEOUT") for r in present),
                           "median_normalized_objective_validated": statistics.median(r["normalized_objective"] for r in valid) if valid else None,
                           "median_wall_seconds_validated": statistics.median(r["total_wall_seconds"] for r in valid) if valid else None})
    summary = {"status": "COMPLETE" if len(rows) == len(tasks) and all(r["status"] == "PASS" for r in rows) else "INCOMPLETE",
               "expected_runs": len(tasks), "recorded_runs": len(rows),
               "validated_runs": sum(r["status"] == "PASS" for r in rows),
               "failed_or_timeout_runs": sum(r["status"] in ("FAIL", "TIMEOUT") for r in rows),
               "primary_topologies": len(selection["instances"]), "groups": group_rows,
               "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    atomic_json(workdir / "summary.json", summary)
    return summary
