"""One isolated task. The parent supplies a monotonic deadline."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from experiments.exp10_xiong.independent_audit import parse_rank, validate
from experiments.exp10_xiong.input_contract import check_w, parse_dimacs, write_w


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_event(folder: Path, event: dict, deadline: float) -> bool:
    """Publish a complete event only when its checkpoint fits the deadline."""
    path = folder / f"event_{event['index']:06d}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(event, sort_keys=True) + "\n")
    tmp.replace(path)
    if time.monotonic() >= deadline:
        path.unlink(missing_ok=True)
        return False
    return True


def ipsns_complete(raw_path: Path, full_path: Path, n: int, arcs: list[tuple[int, int, int]]) -> list[int]:
    with raw_path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    ids = [int(row["Node ID"]) for row in rows]
    ranks = [int(row["Order"]) for row in rows]
    if len(ids) != len(set(ids)) or sorted(ranks) != list(range(len(rows))):
        raise ValueError("malformed raw IPSNS ordering")
    if any(v < 1 or v > n for v in ids):
        raise ValueError("foreign IPSNS vertex")
    missing = sorted(set(range(1, n + 1)) - set(ids))
    incident = {u for u, _, _ in arcs} | {v for _, v, _ in arcs}
    if any(v in incident for v in missing):
        raise ValueError("IPSNS omitted nonisolated vertex")
    ordered = [int(row["Node ID"]) for row in sorted(rows, key=lambda r: int(r["Order"]))] + missing
    with full_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Node ID", "Order"])
        writer.writeheader()
        writer.writerows({"Node ID": v, "Order": i} for i, v in enumerate(ordered))
    return missing


def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("graph", "row", "arm", "seed", "folder", "binary", "ipsns_source", "start", "deadline"):
        p.add_argument("--" + name.replace("_", "-"), required=True)
    a = p.parse_args()
    folder = Path(a.folder); graph = Path(a.graph)
    row = json.loads(a.row); seed = int(a.seed)
    start, deadline = float(a.start), float(a.deadline)
    n, arcs, info = parse_dimacs(graph, row)
    (folder / "input_check.json").write_text(json.dumps(info, sort_keys=True) + "\n")
    if a.arm.startswith("xiong_"):
        wfile = folder / "input.w"
        write_w(wfile, n, arcs)
        check_w(wfile, n, arcs)
        index = 0
        while time.monotonic() < deadline - 0.035:
            run_seed = seed if index == 0 else 1 + ((seed * 1000003 + index * 104729) % 2147483646)
            rank_path = folder / f"rank_{index:06d}.txt"
            command = [a.binary, str(wfile), "W", "RASstar", "-r", str(run_seed), "-p", "-o", str(rank_path)]
            remaining = deadline - time.monotonic() - 0.025
            if remaining <= 0:
                break
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=remaining)
            except subprocess.TimeoutExpired:
                break
            if result.returncode:
                raise RuntimeError(f"Xiong exit {result.returncode}: {result.stderr[:500]}")
            fields = result.stdout.strip().split(",")
            if len(fields) != 3:
                raise ValueError("unexpected Xiong stdout")
            rank = parse_rank(rank_path, "xiong_rasstar", n)
            objective = validate(n, arcs, rank)
            if objective != int(fields[1]):
                raise ValueError("Xiong reported weighted objective mismatch")
            event = {"index": index, "seed": run_seed, "objective": objective,
                     "rank_path": rank_path.name, "rank_sha256": sha(rank_path),
                     "elapsed_seconds": time.monotonic() - start,
                     "algorithm_only_ms": int(fields[2]), "output_kind": "completed_execution"}
            if not save_event(folder, event, deadline):
                break
            index += 1
            if a.arm == "xiong_single":
                break
    elif a.arm == "ipsns_frozen":
        sys.path.insert(0, str(Path(a.ipsns_source) / "src"))
        from mwfas.ipsns import lns_merge_wmsf_lr_best_incumbent
        raw_path = folder / "order.csv"
        result = lns_merge_wmsf_lr_best_incumbent(
            graph, raw_path, seed_ordering="L2", iters=200, topK_scc=15,
            destroy_addback_frac=0.30, destroy_remove_frac=0.02, tol=1e-12,
            rng_seed=seed, log_every=0, wmsf_seed_mode="full",
            scc_select_mode="weighted", return_info=True)
        full_path = folder / "complete_order.csv"
        missing = ipsns_complete(raw_path, full_path, n, arcs)
        objective = validate(n, arcs, parse_rank(full_path, "ipsns", n))
        if abs(objective - result[5]["final_bw"]) > 1e-7 or result[5]["n_iters"] > 200:
            raise ValueError("IPSNS objective or iteration mismatch")
        event = {"index": 0, "seed": seed, "objective": objective,
                 "rank_path": full_path.name, "rank_sha256": sha(full_path),
                 "raw_order_sha256": sha(raw_path), "missing_isolated_vertices": missing,
                 "iterations": result[5]["n_iters"], "elapsed_seconds": time.monotonic() - start,
                 "output_kind": "completed_execution"}
        save_event(folder, event, deadline)
    else:
        raise ValueError("unknown arm")


if __name__ == "__main__":
    main()
