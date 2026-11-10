"""Sequential fixed-budget controller with source and input preflight."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import time
from pathlib import Path

from experiments.exp10_xiong.input_contract import graph_path, parse_dimacs

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def save(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    tmp.replace(path)


def setup(a: argparse.Namespace) -> tuple[dict, list[dict], list[dict]]:
    cfg = json.loads((HERE / "protocol.json").read_text())
    if revision(a.xiong_source) != cfg["xiong_revision"] or revision(a.ipsns_source) != cfg["ipsns_revision"]:
        raise ValueError("frozen source revision mismatch")
    if subprocess.check_output(["git", "-C", str(a.xiong_source), "status", "--porcelain"], text=True).strip():
        raise ValueError("Xiong checkout modified")
    if subprocess.check_output(["git", "-C", str(a.ipsns_source), "status", "--porcelain"], text=True).strip():
        raise ValueError("IPSNS checkout modified")
    if sha(a.binary) != "f58c54bb41e6e896225df40fab52b4e8e747a0967aa80ea3583c8025f2b7a2a9":
        raise ValueError("Xiong binary differs from audited EXP10 build")
    with gzip.open(a.repo / cfg["canonical_inventory"], "rt", newline="") as f:
        inventory = {r["instance_id"]: r for r in csv.DictReader(f)}
    ids = cfg["synthetic_ids"] + cfg["real_world_ids"]
    if len(set(ids)) != 5 or any(i not in inventory for i in ids):
        raise ValueError("input selection missing or duplicated")
    inputs = []
    for iid in ids:
        row = inventory[iid]
        if row["campaign"] != ("EXP04" if iid in cfg["synthetic_ids"] else "EXP05"):
            raise ValueError("campaign mismatch")
        path = graph_path(a.source_root, row)
        _, _, info = parse_dimacs(path, row)
        inputs.append({"instance_id": iid, "path": str(path), **info})
    tasks = []
    for iid in ids:
        budgets = cfg["synthetic_budgets_seconds"] if iid in cfg["synthetic_ids"] else cfg["real_world_budgets_seconds"]
        for budget in budgets:
            for arm in cfg["arms"]:
                for seed in cfg["top_level_seeds"]:
                    tasks.append({"task_id": f"{iid}__b{budget}__{arm}__s{seed}",
                                  "instance_id": iid, "budget_seconds": budget,
                                  "arm": arm, "seed": seed,
                                  "graph_sha256": inventory[iid]["graph_sha256"]})
    if len(tasks) != cfg["maximum_tasks"] or sum(t["budget_seconds"] for t in tasks) != cfg["maximum_sum_task_budgets_seconds"]:
        raise ValueError("task ceiling mismatch")
    return cfg, inputs, tasks


def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("repo", "source_root", "output", "xiong_source", "binary", "ipsns_source"):
        p.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    p.add_argument("--preflight-only", action="store_true")
    a = p.parse_args()
    cfg, inputs, tasks = setup(a)
    if a.preflight_only:
        print(json.dumps({"status": "PASS", "inputs": inputs, "tasks": len(tasks),
                          "sum_task_budgets_seconds": sum(t["budget_seconds"] for t in tasks)}, sort_keys=True))
        return
    if a.output.exists():
        raise ValueError("refusing to reuse evidence directory")
    a.output.mkdir(parents=True)
    (a.output / "tasks").mkdir(); (a.output / "checkpoints").mkdir()
    repo_revision = revision(a.repo) if (a.repo / ".git").exists() else (a.repo / "RELEASE_REVISION").read_text().strip()
    manifest = {"format": "exp11-run-manifest-v1", "protocol_sha256": sha(HERE / "protocol.json"),
                "canonical_inventory_sha256": sha(a.repo / cfg["canonical_inventory"]),
                "repo_revision": repo_revision, "xiong_revision": cfg["xiong_revision"],
                "ipsns_revision": cfg["ipsns_revision"], "xiong_binary_sha256": sha(a.binary),
                "ipsns_source_file_sha256": sha(a.ipsns_source / "src/mwfas/ipsns.py"),
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "node": platform.node(),
                "cpu_model": next((s.split(":", 1)[1].strip() for s in Path("/proc/cpuinfo").read_text().splitlines() if s.startswith("model name")), "unknown"),
                "python": sys.version, "platform": platform.platform(),
                "cpu_affinity": sorted(os.sched_getaffinity(0)),
                "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
                "inputs": inputs, "tasks": tasks}
    save(a.output / "manifest.json", manifest)
    by_id = {r["instance_id"]: r for r in inputs}
    save(a.output / "progress.json", {"phase": "RUNNING", "done": 0, "planned": len(tasks)})
    # The input contract preflight reads each file once, making cache state explicit.
    for number, task in enumerate(tasks, 1):
        folder = a.output / "tasks" / task["task_id"]
        folder.mkdir()
        budget = task["budget_seconds"]
        graph_info = by_id[task["instance_id"]]
        source_row = {k: graph_info[k] for k in ("n", "m", "total_weight", "graph_sha256", "dimacs_sha256")}
        begun = time.monotonic(); begin_unix_ns = time.time_ns(); deadline = begun + budget
        command = [sys.executable, "-m", "experiments.exp11_equal_budget.worker",
                   "--graph", graph_info["path"], "--row", json.dumps(source_row),
                   "--arm", task["arm"], "--seed", str(task["seed"]), "--folder", str(folder),
                   "--binary", str(a.binary), "--ipsns-source", str(a.ipsns_source),
                   "--start", repr(begun), "--deadline", repr(deadline)]
        ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        with (folder / "process.log").open("wb") as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, cwd=a.repo,
                                    start_new_session=True)
            terminated = False
            try:
                proc.wait(timeout=max(0.001, budget - 0.05))
            except subprocess.TimeoutExpired:
                terminated = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        wall = time.monotonic() - begun
        ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        events = sorted(folder.glob("event_*.json"))
        status = "TIMEOUT" if terminated else ("COMPLETED_UNVALIDATED" if proc.returncode == 0 else "FAILED")
        cp = {**task, "status": status, "returncode": proc.returncode,
              "terminated_by_controller": terminated, "task_wall_seconds": wall,
              "wall_budget_compliant": wall <= budget,
              "child_user_cpu_seconds": ru1.ru_utime - ru0.ru_utime,
              "child_system_cpu_seconds": ru1.ru_stime - ru0.ru_stime,
              "start_unix_ns": begin_unix_ns, "end_unix_ns": time.time_ns(),
              "event_count": len(events), "command": command,
              "log_sha256": sha(folder / "process.log")}
        save(a.output / "checkpoints" / (task["task_id"] + ".json"), cp)
        save(a.output / "progress.json", {"phase": "RUNNING", "done": number,
                                           "planned": len(tasks), "last_task": task["task_id"],
                                           "last_status": status, "updated_unix": time.time()})
        if status == "FAILED":
            log_text = (folder / "process.log").read_text(errors="replace")
            if any(s in log_text for s in ("mismatch", "malformed", "omitted nonisolated", "not a complete permutation", "retained graph is cyclic")):
                save(a.output / "fatal.json", {"task_id": task["task_id"], "reason": "fidelity validation failure"})
                raise SystemExit("fidelity validation failed; campaign stopped")
    save(a.output / "progress.json", {"phase": "COMPUTATION_COMPLETE_AUDIT_PENDING",
                                       "done": len(tasks), "planned": len(tasks), "updated_unix": time.time()})


if __name__ == "__main__":
    main()
