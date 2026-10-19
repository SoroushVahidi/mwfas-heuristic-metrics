"""One EXP28 method task; method timing includes imports and checkpoint I/O."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def complete_csv(path: Path, n: int, incident: set[int]) -> list[int]:
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    ids = [int(row["Node ID"]) for row in rows]
    positions = [int(row["Order"]) for row in rows]
    if len(set(ids)) != len(ids) or sorted(positions) != list(range(len(rows))) or any(v < 1 or v > n for v in ids):
        raise ValueError("malformed method CSV order")
    missing = sorted(set(range(1, n + 1)) - set(ids))
    if any(v in incident for v in missing):
        raise ValueError("method omitted a nonisolated vertex")
    return [int(row["Node ID"]) for row in sorted(rows, key=lambda row: int(row["Order"]))] + missing


def write_csv(path: Path, order: list[int]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Node ID", "Order"])
        writer.writeheader()
        writer.writerows({"Node ID": v, "Order": i} for i, v in enumerate(order))
    os.replace(tmp, path)


def score(order: list[int], n: int, arcs: list[tuple[int, int, int]]) -> int:
    if len(order) != n or set(order) != set(range(1, n + 1)):
        raise ValueError("not a complete order")
    pos = {v: i for i, v in enumerate(order)}
    return sum(w for u, v, w in arcs if pos[u] > pos[v])


def publish(folder: Path, task_id: str, index: int, seed: int | None, order_file: Path,
            objective: int, start: float, deadline: float, extra: dict | None = None) -> bool:
    now = time.monotonic()
    if now >= deadline:
        return False
    event = {"task_id": task_id, "index": index, "seed": seed,
             "order_file": order_file.name, "order_sha256": sha(order_file),
             "reported_objective": objective, "elapsed_seconds": now - start,
             "saved_monotonic": now, "extra": extra or {}}
    target = folder / f"event_{index:06d}.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(event, sort_keys=True) + "\n")
    os.replace(tmp, target)
    if time.monotonic() >= deadline:
        target.unlink(missing_ok=True)
        return False
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("graph", "arm", "task_id", "folder", "baseline_source", "xiong_binary",
                 "start_monotonic", "deadline_monotonic", "internal_reserve_seconds", "graph_sha256"):
        p.add_argument("--" + name.replace("_", "-"), required=True)
    p.add_argument("--seed", type=int)
    a = p.parse_args()
    graph_path = Path(a.graph); folder = Path(a.folder)
    arm = a.arm; start = float(a.start_monotonic); deadline = float(a.deadline_monotonic)
    inner_deadline = deadline - float(a.internal_reserve_seconds)
    sys.path.insert(0, str(Path(a.baseline_source) / "src"))
    from mwfas_data.graph import read_dimacs
    from mwfas_data.exp05_insertion import optimize
    from mwfas_data.exp05_runner import read_order, write_order
    from mwfas.lrta import paper_fas_ranking_from_dimacs_fast
    from mwfas.wmsf import wmsf_ranking_from_dimacs_fast
    graph = read_dimacs(graph_path)
    n = len(graph.vertices)
    if any(w <= 0 or not float(w).is_integer() for _, _, w in graph.arcs):
        raise ValueError("method-side input changed integer weights")
    arcs = [(int(u), int(v), int(w)) for u, v, w in graph.arcs]
    incident = {u for u, _, _ in arcs} | {v for _, v, _ in arcs}
    if arm in ("lrta", "wmsf_l2", "weighted_eades", "insertion_lrta", "insertion_wmsf_l2"):
        path = folder / ("seed_order.csv" if arm.startswith("insertion_") else "order.csv")
        if arm in ("lrta", "insertion_lrta"):
            paper_fas_ranking_from_dimacs_fast(graph_path, path, tol=1e-12)
        elif arm in ("wmsf_l2", "insertion_wmsf_l2"):
            wmsf_ranking_from_dimacs_fast(graph_path, path, ordering="L2", tol=1e-12)
        else:
            import igraph
            import networkx as nx
            vertices = list(graph.vertices)
            index = {v: i for i, v in enumerate(vertices)}
            original = list(graph.arcs)
            external = igraph.Graph(n=n, edges=[(index[u], index[v]) for u, v, _ in original], directed=True)
            removed = set(external.feedback_arc_set(weights=[w for _, _, w in original], method="eades"))
            dag = nx.DiGraph(); dag.add_nodes_from(vertices)
            dag.add_edges_from((u, v) for i, (u, v, _) in enumerate(original) if i not in removed)
            if not nx.is_directed_acyclic_graph(dag):
                raise ValueError("Eades retained a cycle")
            write_order(path, list(nx.lexicographical_topological_sort(dag, key=int)))
        initial = [int(v) for v in read_order(path, graph.vertices)]
        initial_value = score(initial, n, arcs)
        if not publish(folder, a.task_id, 0, None, path, initial_value, start, deadline,
                       {"kind": "complete_initializer" if arm.startswith("insertion_") else "complete_final"}):
            raise SystemExit(124)
        if arm.startswith("insertion_"):
            # The EXP12 fixed 105-second internal clock is replaced by the
            # remaining task deadline, while retaining the 1000-move rule.
            result = optimize(graph, [str(v) for v in initial], max_moves=1000, deadline=inner_deadline)
            refined = [int(v) for v in result.order]
            final_path = folder / "refined_order.csv"
            write_csv(final_path, refined)
            value = score(refined, n, arcs)
            publish(folder, a.task_id, 1, None, final_path, value, start, deadline,
                    {"kind": "complete_refinement", "accepted_moves": result.accepted_moves,
                     "termination_reason": result.termination_reason})
    elif arm == "ipsns":
        from experiments.exp28_anytime.ipsns_pinned_instrumented import lns_merge_wmsf_lr_best_incumbent
        next_index = 0
        best_value = None
        checkpoint_seconds = 0.0
        last_iteration = 0

        def on_iteration(completed_iterations):
            nonlocal last_iteration
            last_iteration = completed_iterations
            if time.monotonic() >= inner_deadline:
                record = {"termination_reason": "internal_deadline", "iterations": last_iteration,
                          "checkpoint_seconds": checkpoint_seconds,
                          "best_saved_objective": best_value}
                tmp = folder / "ipsns_timeout.json.tmp"
                tmp.write_text(json.dumps(record, sort_keys=True) + "\n")
                os.replace(tmp, folder / "ipsns_timeout.json")
                raise SystemExit(124)

        def on_incumbent(index_to_node, rank, reported_bw, kind, iteration):
            nonlocal next_index, best_value, checkpoint_seconds
            t0 = time.monotonic()
            if t0 >= inner_deadline:
                raise SystemExit(124)
            indexed = sorted(range(len(rank)), key=lambda i: rank[i])
            order = [int(index_to_node[i]) for i in indexed]
            order += sorted(set(range(1, n + 1)) - set(order))
            value = score(order, n, arcs)
            if abs(value - reported_bw) > 1e-7:
                raise ValueError("IPSNS checkpoint objective differs")
            if best_value is not None and value > best_value:
                raise ValueError("IPSNS incumbent worsened")
            if kind in ("lr_seed_improvement", "refinement_improvement") and best_value is not None and value >= best_value:
                raise ValueError("IPSNS improvement is not strict")
            path = folder / f"order_{next_index:06d}.csv"
            write_csv(path, order)
            if not publish(folder, a.task_id, next_index, a.seed, path, value, start, deadline,
                           {"kind": kind, "iteration": iteration, "graph_sha256": a.graph_sha256}):
                raise SystemExit(124)
            checkpoint_seconds += time.monotonic() - t0
            best_value = value
            next_index += 1
            if time.monotonic() >= inner_deadline:
                raise SystemExit(124)

        raw = folder / "raw_order.csv"
        result = lns_merge_wmsf_lr_best_incumbent(
            graph_path, raw, seed_ordering="L2", iters=200, topK_scc=15,
            destroy_addback_frac=0.30, destroy_remove_frac=0.02, tol=1e-12,
            rng_seed=a.seed, log_every=0, wmsf_seed_mode="full",
            scc_select_mode="weighted", return_info=True,
            incumbent_callback=on_incumbent, iteration_callback=on_iteration)
        order = complete_csv(raw, n, incident)
        value = score(order, n, arcs)
        if abs(value - result[5]["final_bw"]) > 1e-7 or result[5]["n_iters"] > 200:
            raise ValueError("IPSNS score or iteration contract differs")
        if value != best_value:
            raise ValueError("IPSNS final incumbent differs from saved best")
        summary = {"termination_reason": "completed", "iterations": result[5]["n_iters"],
                   "accepted_improvements": result[5]["n_accepted"],
                   "checkpoint_seconds": checkpoint_seconds, "raw_order_sha256": sha(raw)}
        temp = folder / "ipsns_completion.json.tmp"
        temp.write_text(json.dumps(summary, sort_keys=True) + "\n")
        os.replace(temp, folder / "ipsns_completion.json")
    elif arm in ("xiong_single", "xiong_restarts"):
        wpath = folder / "input.w"
        wpath.write_text(f"{n} {len(arcs)}\n" + "".join(f"{u-1} {v-1} {w}\n" for u, v, w in arcs))
        check = [tuple(map(int, line.split())) for line in wpath.read_text().splitlines()]
        if check[0] != (n, len(arcs)) or check[1:] != [(u - 1, v - 1, w) for u, v, w in arcs]:
            raise ValueError("Xiong conversion changed weighted arcs")
        i = 0
        while time.monotonic() < inner_deadline:
            seed = a.seed if i == 0 else 1 + ((a.seed * 1000003 + i * 104729) % 2147483646)
            rank_path = folder / f"rank_{i:06d}.txt"
            command = [a.xiong_binary, str(wpath), "W", "RASstar", "-r", str(seed), "-p", "-o", str(rank_path)]
            remaining = inner_deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=remaining)
            except subprocess.TimeoutExpired:
                break
            (folder / f"xiong_{i:06d}.stdout").write_text(result.stdout)
            (folder / f"xiong_{i:06d}.stderr").write_text(result.stderr)
            if result.returncode:
                raise RuntimeError(f"Xiong exit {result.returncode}: {result.stderr[:300]}")
            fields = result.stdout.strip().split(",")
            if len(fields) != 3:
                raise ValueError("unexpected Xiong stdout")
            ranks = [int(v) for v in rank_path.read_text().split()]
            if len(ranks) != n or sorted(ranks) != list(range(n)):
                raise ValueError("Xiong returned incomplete rank vector")
            order = sorted(range(1, n + 1), key=lambda v: ranks[v - 1])
            value = score(order, n, arcs)
            if value != int(fields[1]):
                raise ValueError("Xiong reported objective differs")
            if not publish(folder, a.task_id, i, seed, rank_path, value, start, deadline,
                           {"kind": "completed_invocation", "algorithm_only_ms": int(fields[2]),
                            "stdout_sha256": sha(folder / f"xiong_{i:06d}.stdout")}):
                break
            i += 1
            if arm == "xiong_single":
                break
        if arm == "xiong_single" and i == 0:
            raise SystemExit(124)
    else:
        raise ValueError("unknown method configuration")
    use = resource.getrusage(resource.RUSAGE_SELF)
    (folder / "worker_summary.json").write_text(json.dumps({"worker_wall_seconds": time.monotonic() - start,
        "worker_cpu_seconds": use.ru_utime + use.ru_stime, "peak_rss_kib": use.ru_maxrss}, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
