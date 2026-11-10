"""Sequential, single-CPU, checkpoint-safe bounded EXP10 campaign."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

from .input_contract import digest, graph_path, parse_dimacs, selected
from .independent_audit import parse_original, parse_rank, validate, verify_ipsns_completion

XIONG = "8340e1633ba9290a567a882aff4d74f01b38102d"
IPSNS = "40209c26966247d9bf9ad34764de4ac4181f98c2"


def atomic(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    tmp.replace(path)


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def code_revision(repo: Path) -> str:
    if (repo / ".git").exists():
        return revision(repo)
    return (repo / "RELEASE_REVISION").read_text().strip()


def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("repo", "source_root", "output", "xiong_source", "xiong_binary", "ipsns_source"):
        p.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    p.add_argument("--preflight-only", action="store_true")
    a = p.parse_args()
    cfg = json.loads((a.repo / "experiments/exp10_xiong/plan.json").read_text())
    if revision(a.xiong_source) != XIONG or revision(a.ipsns_source) != IPSNS:
        raise ValueError("candidate or IPSNS source revision mismatch")
    if subprocess.check_output(["git", "-C", str(a.xiong_source), "status", "--porcelain"], text=True).strip():
        raise ValueError("third-party source checkout is modified")
    if a.output.exists():
        raise ValueError("refusing to reuse output directory")
    rows = selected(a.repo)
    verified = []
    for row in rows:
        path = graph_path(a.source_root, row)
        _, _, info = parse_dimacs(path, row)
        verified.append({"instance_id": row["instance_id"], "path": str(path), **info})
    tasks = [{"task_id": f"{r['instance_id']}__{algorithm}__s{seed}",
              "instance_id": r["instance_id"], "algorithm": algorithm, "seed": seed,
              "graph_sha256": r["graph_sha256"], "topology_sha256": r["topology_sha256"]}
             for r in rows for algorithm in cfg["algorithms"] for seed in cfg["seeds"]]
    if len(tasks) != cfg["maximum_tasks"] or cfg["process_wall_cap_seconds"] != 120:
        raise ValueError("task count or cap differs from approved ceiling")
    if a.preflight_only:
        print(json.dumps({"preflight": "PASS", "weighted_inputs": len(verified),
                          "tasks": len(tasks), "xiong_revision": XIONG, "ipsns_revision": IPSNS,
                          "input_inventory": verified}, sort_keys=True))
        return
    a.output.mkdir(parents=True)
    lock = (a.output / "campaign.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for folder in ("tasks", "checkpoints"):
        (a.output / folder).mkdir()
    manifest = {"format": "exp10-run-manifest-v1", "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "repo_revision": code_revision(a.repo), "xiong_revision": XIONG, "ipsns_revision": IPSNS,
                "plan_sha256": digest(a.repo / "experiments/exp10_xiong/plan.json"),
                "canonical_inventory_sha256": digest(a.repo / cfg["canonical_inventory"]),
                "xiong_binary_sha256": digest(a.xiong_binary), "python": sys.version,
                "hostname": platform.node(),
                "cpu": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                             if line.startswith("model name")), platform.processor()),
                "task_count": len(tasks), "task_wall_cap_seconds": cfg["process_wall_cap_seconds"],
                "input_inventory": verified, "tasks": tasks}
    atomic(a.output / "manifest.json", manifest)
    by_id = {r["instance_id"]: r for r in rows}
    atomic(a.output / "progress.json", {"phase": "RUNNING", "complete": 0, "planned": len(tasks)})
    for number, task in enumerate(tasks, 1):
        dest = a.output / "tasks" / task["task_id"]
        dest.mkdir()
        checkpoint = a.output / "checkpoints" / (task["task_id"] + ".json")
        row = by_id[task["instance_id"]]
        command = [sys.executable, "-m", "experiments.exp10_xiong.worker",
                   "--graph", str(graph_path(a.source_root, row)), "--row", json.dumps(row),
                   "--algorithm", task["algorithm"], "--seed", str(task["seed"]),
                   "--output", str(dest), "--xiong-binary", str(a.xiong_binary),
                   "--ipsns-source", str(a.ipsns_source)]
        begun = time.perf_counter()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, cwd=a.repo, start_new_session=True,
                                   env={**os.environ, "PYTHONPATH": str(a.repo / "src") + ":" + str(a.repo),
                                        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        try:
            log, _ = process.communicate(timeout=120)
            status = "COMPLETED_UNVALIDATED" if process.returncode == 0 else "FAILED"
            code = process.returncode
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            log, _ = process.communicate()
            status = "TIMEOUT"; code = process.returncode
        wall = time.perf_counter() - begun
        (dest / "process.log").write_text(log)
        if status == "COMPLETED_UNVALIDATED":
            try:
                original = graph_path(a.source_root, row)
                n, arcs, gh = parse_original(original)
                if gh != row["graph_sha256"]:
                    raise ValueError("graph hash changed before result check")
                ranks = parse_rank(dest / ("ranks.txt" if task["algorithm"] == "xiong_rasstar" else "complete_order.csv"),
                                   task["algorithm"], n)
                objective = validate(n, arcs, ranks)
                raw = json.loads((dest / "raw.json").read_text())
                reported = raw["reported_objective"]
                if abs(objective - reported) > 1e-7:
                    raise ValueError("reported objective differs from original graph")
                if task["algorithm"] == "ipsns":
                    verify_ipsns_completion(dest, n, arcs, raw)
                if task["algorithm"] == "xiong_rasstar":
                    converted = (dest / "input.w").read_text().splitlines()
                    if list(map(int, converted[0].split())) != [n, len(arcs)] or len(converted) != len(arcs) + 1:
                        raise ValueError("W conversion count mismatch")
                    if [tuple(map(int, x.split())) for x in converted[1:]] != [(u-1,v-1,w) for u,v,w in arcs]:
                        raise ValueError("W conversion changed arcs or weights")
            except Exception as exc:
                status = "INVALID"; log += "\nFidelity gate: " + repr(exc) + "\n"
                (dest / "process.log").write_text(log)
        atomic(checkpoint, {**task, "status": status, "returncode": code,
                            "process_wall_seconds": wall, "command": command,
                            "log_sha256": digest(dest / "process.log")})
        atomic(a.output / "progress.json", {"phase": "RUNNING", "complete": number,
                                            "planned": len(tasks), "last_task": task["task_id"],
                                            "last_status": status, "updated_unix": time.time()})
        if status == "INVALID":
            atomic(a.output / "fatal.json", {"task_id": task["task_id"], "error": log.splitlines()[-1],
                                              "reason": "weighted-objective or ordering fidelity failed"})
            raise SystemExit("stopped after invalid candidate output")
    atomic(a.output / "progress.json", {"phase": "COMPUTATION_COMPLETE_AUDIT_PENDING",
                                        "complete": len(tasks), "planned": len(tasks),
                                        "updated_unix": time.time()})


if __name__ == "__main__":
    main()
