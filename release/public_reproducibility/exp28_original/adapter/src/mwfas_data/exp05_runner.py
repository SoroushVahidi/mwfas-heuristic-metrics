"""Checkpoint-safe EXP05 worker, scheduler, aggregation, and independent validation."""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import platform
import resource
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import igraph
import networkx as nx
import pandas as pd
import pyarrow

from .exp03 import atomic_json, sha256_file, write_parquet_atomic
from .exp05 import CONFIG_PATH, SELECTION_PATH, SOURCE_MANIFEST_PATH, config, expected_tasks
from .generation import canonical_graph_sha256
from .exp04 import topology_sha256
from .graph import acyclic_after_removal, backward_weight, read_dimacs
from .exp05_insertion import optimize

DIAGNOSTIC = Path(__file__).resolve().parents[2] / "experiments/exp05_realworld_dense/ipsns_diagnostic.py"
STOP = threading.Event()
ACTIVE: set[subprocess.Popen] = set()
LOCK = threading.Lock()


def utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stop(_sig, _frame) -> None:
    STOP.set()
    with LOCK:
        for process in list(ACTIVE):
            process.terminate()


def revision(source: Path) -> str:
    return subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()


def read_order(path: Path, vertices: tuple[str, ...]) -> list[str]:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(vertices) or {int(row["Order"]) for row in rows} != set(range(len(vertices))):
        raise ValueError("ordering rank count/permutation invalid")
    order = [row["Node ID"] for row in sorted(rows, key=lambda row: int(row["Order"]))]
    if set(order) != set(vertices) or len(set(order)) != len(vertices):
        raise ValueError("ordering vertex set invalid")
    return order


def write_order(path: Path, order: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["Node ID", "Order"])
        writer.writeheader()
        writer.writerows({"Node ID": v, "Order": rank} for rank, v in enumerate(order))


def worker(args) -> None:
    if revision(args.source) != config()["source_revision"]:
        raise ValueError("upstream source revision mismatch")
    sys.path.insert(0, str(args.source / "src"))
    from mwfas.evaluation import compute_forward_backward
    from mwfas.lrta import paper_fas_ranking_from_dimacs_fast
    from mwfas.wmsf import wmsf_ranking_from_dimacs_fast
    begin = time.perf_counter()
    graph = read_dimacs(args.graph)
    info: dict = {}
    if args.algorithm == "igraph_eades_weighted":
        index = {v: i for i, v in enumerate(graph.vertices)}
        arcs = list(graph.arcs)
        external = igraph.Graph(n=len(index), edges=[(index[u], index[v]) for u, v, _ in arcs], directed=True)
        conversion = time.perf_counter() - begin
        ids = list(external.feedback_arc_set(weights=[w for _, _, w in arcs], method="eades"))
        if len(ids) != len(set(ids)) or any(i < 0 or i >= len(arcs) for i in ids):
            raise ValueError("invalid igraph FAS edge ids")
        removed_ids = set(ids)
        dag = nx.DiGraph()
        dag.add_nodes_from(graph.vertices)
        dag.add_edges_from((u, v) for i, (u, v, _) in enumerate(arcs) if i not in removed_ids)
        if not nx.is_directed_acyclic_graph(dag):
            raise ValueError("igraph FAS retained a cycle")
        order = list(nx.lexicographical_topological_sort(dag, key=int))
        write_order(args.order, order)
        info = {"fas_edge_ids": ids, "fas_weight": sum(arcs[i][2] for i in ids), "conversion_seconds": conversion}
        objective = backward_weight(graph, order)
    elif args.algorithm.startswith("insertion_"):
        seed_alg = "lrta" if args.algorithm == "insertion_lrta" else "wmsf_l2"
        seed_path = args.seed_order
        if seed_path is None:
            raise ValueError("insertion seed order missing")
        initial_order = read_order(seed_path, graph.vertices)
        deadline = time.monotonic() + args.deadline_seconds if args.deadline_seconds is not None else None
        result = optimize(graph, initial_order, max_moves=config()["insertion_max_moves"], deadline=deadline)
        write_order(args.order, result.order)
        info = {"initial_objective": result.initial_objective, "accepted_moves": result.accepted_moves,
                "refinement_seconds": result.refinement_seconds, "termination_reason": result.termination_reason,
                "seed_algorithm": seed_alg}
        objective = result.final_objective
    elif args.algorithm == "lrta":
        result = paper_fas_ranking_from_dimacs_fast(args.graph, args.order, tol=1e-12)
        objective = compute_forward_backward(result[0], result[3])[2]
    elif args.algorithm == "wmsf_l2":
        result = wmsf_ranking_from_dimacs_fast(args.graph, args.order, ordering="L2", tol=1e-12)
        objective = compute_forward_backward(result[0], result[3])[2]
    else:
        spec = importlib.util.spec_from_file_location("mwfas.ipsns_exp05_diagnostic", DIAGNOSTIC)
        if spec is None or spec.loader is None:
            raise ValueError("cannot load EXP05 diagnostic adapter")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = module.lns_merge_wmsf_lr_best_incumbent(
            args.graph, args.order, seed_ordering="L2", iters=args.budget, topK_scc=15,
            destroy_addback_frac=0.30, destroy_remove_frac=0.02, tol=1e-12,
            rng_seed=args.seed, log_every=0, wmsf_seed_mode="full",
            scc_select_mode="weighted", return_info=True)
        objective = compute_forward_backward(result[0], result[3])[2]
        info = result[5]
    atomic_json(args.raw, {"reported_objective": float(objective), "info": info,
                           "algorithm_wall_seconds": time.perf_counter() - begin,
                           "peak_memory_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


def independently_check(graph_path: Path, order_path: Path, reported: float) -> tuple[float, str]:
    graph = read_dimacs(graph_path)
    order = read_order(order_path, graph.vertices)
    objective = backward_weight(graph, order)
    if not math.isclose(objective, reported, rel_tol=1e-10, abs_tol=1e-7):
        raise ValueError("reported and reconstructed objective disagree")
    ranks = {v: i for i, v in enumerate(order)}
    removed = {(u, v) for u, v, _ in graph.arcs if ranks[u] >= ranks[v]}
    if not acyclic_after_removal(graph, removed):
        raise ValueError("retained graph is cyclic")
    return objective, sha256_file(order_path)


def task_run(task: dict, instance: dict, args) -> dict:
    run_id = task["run_id"]
    checkpoint = args.workdir / "runs" / f"{run_id}.json"
    graph_path = args.workdir / "graphs" / instance["graph_file"]
    order_tmp = args.workdir / "orders" / f"{run_id}.csv.tmp"
    order_final = args.workdir / "orders" / f"{run_id}.csv"
    raw_tmp = args.workdir / "worker" / f"{run_id}.json.tmp"
    log_path = args.workdir / "logs" / f"{run_id}.log"
    for path in (checkpoint, order_tmp, raw_tmp, log_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path == checkpoint and json.loads(path.read_text())["status"] != "INTERRUPTED":
                raise ValueError("refusing to overwrite terminal checkpoint")
            archive = args.workdir / "attempts" / f"{run_id}_{int(time.time())}_{path.name}"
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, archive)
            if path != checkpoint:
                path.unlink()
    row = {"run_id": run_id, "instance_id": task["instance_id"], "algorithm": task["algorithm"],
           "seed": task["seed"], "iteration_budget": task["budget"],
           "budget_semantics": "independent_fresh_run" if task["algorithm"] == "ipsns" else None,
           "graph_sha256": instance["graph_sha256"], "topology_sha256": instance["topology_sha256"],
           "config_sha256": sha256_file(CONFIG_PATH), "code_revision": args.code_revision,
           "source_revision": config()["source_revision"], "status": "INTERRUPTED"}
    if task["algorithm"].startswith("insertion_"):
        base = "lrta" if task["algorithm"] == "insertion_lrta" else "wmsf_l2"
        seed_checkpoint = args.workdir / "runs" / f"{task['instance_id']}__{base}.json"
        if not seed_checkpoint.exists() or json.loads(seed_checkpoint.read_text())["status"] != "PASS":
            row.update(status="SKIPPED_DEPENDENCY", error=f"validated {base} seed ordering unavailable")
            atomic_json(checkpoint, row)
            return row
    command = [sys.executable, "-m", "mwfas_data.exp05_runner", "worker", "--source", str(args.source),
               "--graph", str(graph_path), "--order", str(order_tmp), "--raw", str(raw_tmp),
               "--algorithm", task["algorithm"]]
    if task["algorithm"] == "ipsns":
        command += ["--seed", str(task["seed"]), "--budget", str(task["budget"])]
    if task["algorithm"].startswith("insertion_"):
        base = "lrta" if task["algorithm"] == "insertion_lrta" else "wmsf_l2"
        command += ["--seed-order", str(args.workdir / "orders" / f"{task['instance_id']}__{base}.csv")]
        command += ["--deadline-seconds", str(min(config()["insertion_refinement_cap_seconds"], args.timeout - 5))]
    row["command"] = command
    started = time.perf_counter()
    with log_path.open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env={**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        with LOCK:
            ACTIVE.add(process)
        try:
            exit_code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            exit_code = None
        finally:
            with LOCK:
                ACTIVE.discard(process)
    row["total_wall_seconds"] = time.perf_counter() - started
    if exit_code is None:
        row.update(status="TIMEOUT", error=f"per-run timeout {args.timeout}s")
    elif STOP.is_set() and exit_code != 0:
        row.update(status="INTERRUPTED", error=f"worker exited {exit_code} after signal")
    elif exit_code != 0 or not order_tmp.exists() or not raw_tmp.exists():
        row.update(status="FAIL", error=f"worker exit {exit_code}; see {log_path}")
    else:
        try:
            raw = json.loads(raw_tmp.read_text())
            objective, order_sha = independently_check(graph_path, order_tmp, raw["reported_objective"])
            info = raw["info"]
            row.update(status="PASS", objective_weight=objective, reported_objective=raw["reported_objective"],
                       normalized_objective=objective / instance["total_graph_weight"], order_sha256=order_sha,
                       algorithm_wall_seconds=raw["algorithm_wall_seconds"], peak_memory_kib=raw["peak_memory_kib"],
                       info=info)
            if task["algorithm"] == "igraph_eades_weighted":
                fas_path = args.workdir / "fas" / f"{run_id}.json"
                graph = read_dimacs(graph_path)
                ids = info["fas_edge_ids"]
                if not math.isclose(sum(graph.arcs[i][2] for i in ids), info["fas_weight"], abs_tol=1e-7):
                    raise ValueError("igraph original FAS weight mismatch")
                removed = {(graph.arcs[i][0], graph.arcs[i][1]) for i in ids}
                if not acyclic_after_removal(graph, removed):
                    raise ValueError("igraph original FAS invalid")
                atomic_json(fas_path, {"edge_ids": ids, "graph_sha256": instance["graph_sha256"],
                                       "fas_weight": info["fas_weight"]})
                row["fas_sha256"] = sha256_file(fas_path)
            if task["algorithm"] == "ipsns":
                baseline_crosscheck = "PASS"
                for baseline, field in (("lrta", "lr_seed_bw"), ("wmsf_l2", "wmsf_seed_bw")):
                    path = args.workdir / "runs" / f"{task['instance_id']}__{baseline}.json"
                    comparator = json.loads(path.read_text()) if path.exists() else None
                    if comparator is None or comparator["status"] != "PASS":
                        baseline_crosscheck = "NOT_VERIFIABLE"
                        continue
                    if not math.isclose(comparator["objective_weight"], info[field], abs_tol=1e-7):
                        raise ValueError(f"IPSNS seed differs from {baseline}")
                row["baseline_crosscheck_status"] = baseline_crosscheck
                if objective > info["best_seed_bw"] + 1e-7:
                    raise ValueError("IPSNS worsens best initial incumbent")
            if task["algorithm"].startswith("insertion_"):
                base = "lrta" if task["algorithm"] == "insertion_lrta" else "wmsf_l2"
                comparator = json.loads((args.workdir / "runs" / f"{task['instance_id']}__{base}.json").read_text())
                if comparator["status"] != "PASS" or not math.isclose(comparator["objective_weight"], info["initial_objective"], abs_tol=1e-7):
                    raise ValueError("insertion initial objective differs from saved seed")
                row["initialization_inclusive_seconds"] = comparator["total_wall_seconds"] + row["total_wall_seconds"]
            os.replace(order_tmp, order_final)
            raw_tmp.unlink()
        except Exception as exc:
            row.update(status="FAIL", error=f"independent validation: {exc}")
    atomic_json(checkpoint, row)
    return row


def aggregate(workdir: Path, tasks: list[dict], *, validate: bool = True) -> dict:
    rows = []
    for task in tasks:
        path = workdir / "runs" / f"{task['run_id']}.json"
        if path.exists():
            rows.append(json.loads(path.read_text()))
    write_parquet_atomic(workdir / "algorithm_runs.parquet", rows)
    write_parquet_atomic(workdir / "insertion_local_search.parquet", [r for r in rows if r["algorithm"].startswith("insertion_")])
    write_parquet_atomic(workdir / "budget_metrics.parquet", [r for r in rows if r["algorithm"] == "ipsns"])
    write_parquet_atomic(workdir / "seed_diagnostics.parquet", [{"run_id": r["run_id"], "instance_id": r["instance_id"], "seed": r["seed"], "budget": r["iteration_budget"],
        "status": r["status"], "selection_trace": r.get("info", {}).get("selection_trace"),
        "multi_eligible_iterations": r.get("info", {}).get("multi_eligible_iterations")}
        for r in rows if r["algorithm"] == "ipsns"])
    summary = {"expected_tasks": len(tasks), "recorded_tasks": len(rows),
               "validated_pass": sum(r["status"] == "PASS" for r in rows),
               "failed": sum(r["status"] == "FAIL" for r in rows),
               "timeouts": sum(r["status"] == "TIMEOUT" for r in rows),
               "interrupted": sum(r["status"] == "INTERRUPTED" for r in rows),
               "skipped_dependency": sum(r["status"] == "SKIPPED_DEPENDENCY" for r in rows),
               "missing": len(tasks) - len(rows), "updated_utc": utc()}
    summary["status"] = "COMPLETE" if summary["validated_pass"] == len(tasks) else "INCOMPLETE"
    atomic_json(workdir / "summary.json", summary)
    if validate:
        independently_validate(workdir, tasks)
        from .exp05_analysis import analyze
        analyze(workdir)
    return summary


def independently_validate(workdir: Path, tasks: list[dict]) -> dict:
    selection = json.loads((workdir / "selection.json").read_text())
    instances = {x["instance_id"]: x for x in selection["instances"]}
    issues = []
    passed = 0
    seed_crosscheck_not_verifiable = 0
    for task in tasks:
        run_id = task["run_id"]
        path = workdir / "runs" / f"{run_id}.json"
        if not path.exists():
            issues.append({"run_id": run_id, "status": "NOT_VERIFIABLE", "reason": "missing checkpoint"})
            continue
        row = json.loads(path.read_text())
        if row["status"] != "PASS":
            issues.append({"run_id": run_id, "status": row["status"], "reason": row.get("error")})
            continue
        try:
            instance = instances[task["instance_id"]]
            graph_path = workdir / "graphs" / instance["graph_file"]
            if sha256_file(graph_path) != instance["dimacs_sha256"]:
                raise ValueError("graph file hash mismatch")
            graph = read_dimacs(graph_path)
            nxg = nx.DiGraph()
            nxg.add_nodes_from(int(v) for v in graph.vertices)
            nxg.add_weighted_edges_from((int(u), int(v), int(w)) for u, v, w in graph.arcs)
            if canonical_graph_sha256(nxg) != instance["graph_sha256"] or topology_sha256(nxg) != instance["topology_sha256"]:
                raise ValueError("graph identity mismatch")
            if row["graph_sha256"] != instance["graph_sha256"] or row["code_revision"] != json.loads((workdir / "run_manifest.json").read_text())["code_revision"]:
                raise ValueError("checkpoint identity mismatch")
            if row["algorithm"] != task["algorithm"] or row["seed"] != task["seed"] or row["iteration_budget"] != task["budget"]:
                raise ValueError("task identity mismatch")
            order_path = workdir / "orders" / f"{run_id}.csv"
            if sha256_file(order_path) != row["order_sha256"]:
                raise ValueError("order hash mismatch")
            objective, _ = independently_check(graph_path, order_path, row["reported_objective"])
            if not math.isclose(objective, row["objective_weight"], abs_tol=1e-7):
                raise ValueError("objective mismatch")
            if task["algorithm"] == "igraph_eades_weighted":
                fas_path = workdir / "fas" / f"{run_id}.json"
                if sha256_file(fas_path) != row["fas_sha256"]:
                    raise ValueError("original FAS artifact hash mismatch")
                fas = json.loads(fas_path.read_text())
                ids = fas["edge_ids"]
                if fas["graph_sha256"] != instance["graph_sha256"] or len(ids) != len(set(ids)) or any(i < 0 or i >= len(graph.arcs) for i in ids):
                    raise ValueError("original FAS identities invalid")
                fas_weight = sum(graph.arcs[i][2] for i in ids)
                if not math.isclose(fas_weight, fas["fas_weight"], abs_tol=1e-7) or not math.isclose(fas_weight, row["info"]["fas_weight"], abs_tol=1e-7):
                    raise ValueError("original FAS weight mismatch")
                removed = {(graph.arcs[i][0], graph.arcs[i][1]) for i in ids}
                if not acyclic_after_removal(graph, removed) or objective > fas_weight + 1e-7:
                    raise ValueError("original FAS DAG or reconstructed order relation invalid")
            if task["algorithm"].startswith("insertion_"):
                base = "lrta" if task["algorithm"] == "insertion_lrta" else "wmsf_l2"
                seed = json.loads((workdir / "runs" / f"{task['instance_id']}__{base}.json").read_text())
                if seed["status"] != "PASS" or not math.isclose(seed["objective_weight"], row["info"]["initial_objective"], abs_tol=1e-7):
                    raise ValueError("insertion initialization differs from saved baseline")
                if objective > seed["objective_weight"] + 1e-7 or row["info"]["accepted_moves"] > config()["insertion_max_moves"]:
                    raise ValueError("insertion result worsened seed or exceeded move budget")
                if not math.isclose(row["initialization_inclusive_seconds"], row["total_wall_seconds"] + seed["total_wall_seconds"], abs_tol=1e-7):
                    raise ValueError("insertion inclusive runtime mismatch")
            if task["algorithm"] == "ipsns":
                if row.get("baseline_crosscheck_status") == "PASS":
                    better = min(json.loads((workdir / "runs" / f"{task['instance_id']}__{base}.json").read_text())["objective_weight"] for base in ("lrta", "wmsf_l2"))
                    if not math.isclose(better, row["info"]["best_seed_bw"], abs_tol=1e-7):
                        raise ValueError("IPSNS best initial objective mismatch")
                else:
                    seed_crosscheck_not_verifiable += 1
                if row["info"]["n_iters"] > task["budget"]:
                    raise ValueError("IPSNS iterations exceed budget")
                if len(row["info"]["selection_trace"]) > row["info"]["n_iters"]:
                    raise ValueError("selection trace exceeds iterations")
                if objective > row["info"]["best_seed_bw"] + 1e-7 or row["info"]["n_accepted"] > row["info"]["n_iters"]:
                    raise ValueError("IPSNS worsened seed or impossible move count")
                if any(not item["random_choice_invoked"] or item["eligible_cyclic_sccs"] < 1 for item in row["info"]["selection_trace"]):
                    raise ValueError("IPSNS selection trace invalid")
            passed += 1
        except Exception as exc:
            issues.append({"run_id": run_id, "status": "FAIL", "reason": str(exc)})
    report = {"expected": len(tasks), "passed": passed, "issues": issues,
              "seed_crosscheck_not_verifiable": seed_crosscheck_not_verifiable, "updated_utc": utc(),
              "status": "COMPLETE" if passed == len(tasks) else "INCOMPLETE"}
    atomic_json(workdir / "validation_report.json", report)
    return report


def run(args) -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGUSR1, stop)
    cfg = config()
    if revision(args.source) != cfg["source_revision"]:
        raise ValueError("pinned algorithm revision mismatch")
    if args.mode == "production" and (cfg["status"] != "FROZEN_PRIMARY_DESIGN" or len(args.code_revision) != 40):
        raise ValueError("production requires frozen protocol and commit")
    selection = json.loads((args.workdir / "selection.json").read_text())
    if args.mode == "production" and selection != json.loads(SELECTION_PATH.read_text()):
        raise ValueError("production selection differs from frozen manifest")
    tasks = expected_tasks(selection)
    if args.mode == "pilot":
        selected = set(cfg["pilot_instances"])
        tasks = [t for t in tasks if t["instance_id"] in selected and
                 (t["algorithm"] != "ipsns" or (t["budget"] == 10 and t["seed"] == 1))]
    instances = {x["instance_id"]: x for x in selection["instances"]}
    identity = {"mode": args.mode, "code_revision": args.code_revision, "source_revision": cfg["source_revision"],
                "config_sha256": sha256_file(CONFIG_PATH), "selection_sha256": sha256_file(args.workdir / "selection.json"),
                "source_manifest_sha256": sha256_file(SOURCE_MANIFEST_PATH),
                "diagnostic_sha256": sha256_file(DIAGNOSTIC), "expected_run_ids": [t["run_id"] for t in tasks]}
    manifest_path = args.workdir / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        if any(manifest[k] != value for k, value in identity.items()):
            raise ValueError("resume identity mismatch")
        manifest["resume_count"] += 1
    else:
        manifest = identity | {"created_utc": utc(), "resume_count": 0,
            "environment": {"python": sys.version, "networkx": nx.__version__, "pandas": pd.__version__,
                "pyarrow": pyarrow.__version__, "igraph": igraph.__version__, "hostname": platform.node(),
                "slurm_job_id": os.getenv("SLURM_JOB_ID"), "slurm_account": os.getenv("SLURM_JOB_ACCOUNT"),
                "slurm_partition": os.getenv("SLURM_JOB_PARTITION"), "slurm_qos": os.getenv("SLURM_JOB_QOS"),
                "slurm_cpus_per_task": os.getenv("SLURM_CPUS_PER_TASK"), "slurm_mem_per_node": os.getenv("SLURM_MEM_PER_NODE"),
                "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), None)},
            "command": sys.argv}
    manifest["status"] = "RUNNING"
    atomic_json(manifest_path, manifest)
    atomic_json(args.workdir / "startup_health.json", {"status": "PASS", "time_utc": utc(),
         "writable": os.access(args.workdir, os.W_OK), "expected_tasks": len(tasks), "worker_pid": os.getpid()})
    statuses = {}
    for task in tasks:
        path = args.workdir / "runs" / f"{task['run_id']}.json"
        if path.exists():
            old = json.loads(path.read_text())
            if any(old[k] != value for k, value in (("config_sha256", identity["config_sha256"]),
                    ("code_revision", args.code_revision), ("graph_sha256", instances[task["instance_id"]]["graph_sha256"]))):
                raise ValueError("checkpoint identity mismatch")
            statuses[task["run_id"]] = old["status"]
        else:
            statuses[task["run_id"]] = "PENDING"
    def heartbeat(active: list[str]) -> None:
        atomic_json(args.workdir / "progress.json", {"heartbeat_utc": utc(), "worker_pid": os.getpid(),
          "hostname": platform.node(), "expected": len(tasks),
          "recorded": sum(s in ("PASS", "FAIL", "TIMEOUT", "INTERRUPTED", "SKIPPED_DEPENDENCY") for s in statuses.values()),
          "validated": sum(s == "PASS" for s in statuses.values()),
          "failed": sum(s == "FAIL" for s in statuses.values()),
          "timeouts": sum(s == "TIMEOUT" for s in statuses.values()), "running": active})
    heartbeat([])
    deadline = time.monotonic() + max(0, args.max_wall_seconds - cfg["reserve_seconds"])
    args.timeout = cfg["pilot_timeout_seconds"] if args.mode == "pilot" else cfg["task_timeout_seconds"]
    stages = [
        [t for t in tasks if t["algorithm"] in ("lrta", "wmsf_l2", "igraph_eades_weighted")],
        [t for t in tasks if t["algorithm"].startswith("insertion_")],
        [t for t in tasks if t["algorithm"] == "ipsns"],
    ]
    completed_since_export = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for stage in stages:
            pending = [t for t in stage if statuses[t["run_id"]] in ("PENDING", "INTERRUPTED")]
            futures = {}
            while (pending or futures) and not STOP.is_set():
                while pending and len(futures) < args.workers and time.monotonic() < deadline and not STOP.is_set():
                    task = pending.pop(0)
                    statuses[task["run_id"]] = "RUNNING"
                    futures[pool.submit(task_run, task, instances[task["instance_id"]], args)] = task
                heartbeat([t["run_id"] for t in futures.values()])
                if not futures:
                    break
                done, _ = wait(futures, timeout=20, return_when=FIRST_COMPLETED)
                for future in done:
                    task = futures.pop(future)
                    try:
                        statuses[task["run_id"]] = future.result()["status"]
                    except Exception as exc:
                        row = {"run_id": task["run_id"], "instance_id": task["instance_id"], "algorithm": task["algorithm"],
                               "seed": task["seed"], "iteration_budget": task["budget"],
                               "status": "FAIL", "error": repr(exc), "code_revision": args.code_revision,
                               "config_sha256": identity["config_sha256"], "graph_sha256": instances[task["instance_id"]]["graph_sha256"]}
                        atomic_json(args.workdir / "runs" / f"{task['run_id']}.json", row)
                        statuses[task["run_id"]] = "FAIL"
                    completed_since_export += 1
                if completed_since_export >= 25:
                    aggregate(args.workdir, tasks, validate=False)
                    completed_since_export = 0
            if STOP.is_set() or time.monotonic() >= deadline:
                break
    heartbeat([])
    summary = aggregate(args.workdir, tasks)
    manifest["status"] = summary["status"]
    manifest["ended_utc"] = utc()
    atomic_json(manifest_path, manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("worker")
    for flag in ("source", "graph", "order", "raw"):
        p.add_argument(f"--{flag}", type=Path, required=True)
    p.add_argument("--algorithm", choices=config()["algorithms"], required=True)
    p.add_argument("--seed", type=int)
    p.add_argument("--budget", type=int)
    p.add_argument("--seed-order", type=Path)
    p.add_argument("--deadline-seconds", type=float)
    p = sub.add_parser("run")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--workdir", type=Path, required=True)
    p.add_argument("--mode", choices=["pilot", "production"], required=True)
    p.add_argument("--code-revision", required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--max-wall-seconds", type=int, default=32400)
    p = sub.add_parser("aggregate")
    p.add_argument("--workdir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "worker":
        worker(args)
    elif args.command == "run":
        run(args)
    else:
        selection = json.loads((args.workdir / "selection.json").read_text())
        aggregate(args.workdir, expected_tasks(selection))

if __name__ == "__main__":
    main()
