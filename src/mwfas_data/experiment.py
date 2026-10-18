"""Bounded independent rerun adapter for the pinned upstream implementation."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .config import load_project
from .graph import acyclic_after_removal, backward_weight, read_dimacs

SCRIPTS = {"lrta": "run_lrta.py", "wmsf": "run_wmsf.py", "ipsns": "run_ipsns.py", "exact": "run_exact.py"}


def command_for(source: Path, algorithm: str, graph: Path, ranking: Path, seed: int = 1, iterations: int = 400) -> list[str]:
    if algorithm not in SCRIPTS:
        raise ValueError(f"unknown algorithm: {algorithm}")
    cmd = [sys.executable, str(source / "scripts" / SCRIPTS[algorithm]), "--input", str(graph), "--output", str(ranking)]
    if algorithm == "ipsns":
        cmd += ["--rng-seed", str(seed), "--iters", str(iterations), "--wmsf-seed-mode", "full"]
    if algorithm == "wmsf":
        cmd += ["--ordering", "L2"]
    return cmd


def run_once(source: Path, graph_path: Path, algorithm: str, output_dir: Path, *, seed: int = 1, iterations: int = 400, timeout: int = 60) -> dict:
    config = load_project()
    actual_revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual_revision != config["source_revision"]:
        raise ValueError(f"source revision mismatch: {actual_revision}")
    graph = read_dimacs(graph_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    ranking = output_dir / f"{graph_path.stem}_{algorithm}_ranking.csv"
    cmd = command_for(source, algorithm, graph_path, ranking, seed, iterations)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(source / "src")
    start = time.perf_counter()
    process = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    elapsed = time.perf_counter() - start
    result = {"algorithm": algorithm, "graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
              "source_revision": actual_revision, "seed": seed if algorithm == "ipsns" else None,
              "iterations": iterations if algorithm == "ipsns" else None,
              "wall_seconds": elapsed, "command": cmd, "returncode": process.returncode,
              "stderr": process.stderr[-2000:], "status": "FAIL" if process.returncode else "PASS"}
    if process.returncode == 0 and ranking.exists():
        with ranking.open(newline="") as stream:
            rows = list(csv.DictReader(stream))
        try:
            order = [row["Node ID"] for row in sorted(rows, key=lambda row: int(row["Order"]))]
            objective = backward_weight(graph, order)
            rank = {vertex: index for index, vertex in enumerate(order)}
            removed = {(u, v) for u, v, _ in graph.arcs if rank[u] >= rank[v]}
            acyclic = acyclic_after_removal(graph, removed)
            result.update({"objective_weight": objective, "ordering_valid": True,
                           "acyclicity_valid": acyclic})
            if not acyclic:
                result["status"] = "FAIL"
        except (KeyError, ValueError) as exc:
            result.update({"status": "FAIL", "ordering_valid": False, "error": str(exc)})
    else:
        result.update({"status": "FAIL", "error": "ranking file missing or algorithm failed"})
    (output_dir / f"{graph_path.stem}_{algorithm}_result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
