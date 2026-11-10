"""Run only EXP11 tasks rejected by its frozen independent wall-budget audit.

This is a new, disjoint output. The original EXP11 output is read only.
The frozen EXP11 worker and independent auditor remain the source of algorithm
execution and endpoint validation; this controller only fixes deadline reserve.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

PRIOR_MANIFEST_SHA = "3d9193146d947b2aca7226c03c28b5ab421b416acc31a6b12a0f951086d1100a"
PRIOR_INVENTORY_SHA = "1297a113fa87785c729591e40f4aa4a5c1d36c0e5e467dbc5d7c4e545f76c08d"
PRIOR_AUDIT_SHA = "00f1a34a9640519b93208ab01e5b9f69a59ad05dd7ef0e5e0488fd6145e5b9f1"
EXP11_REVISION = "211d86f8370afb3eafdc0b33caf7e54a887722f1"
XIONG_REVISION = "8340e1633ba9290a567a882aff4d74f01b38102d"
IPSNS_REVISION = "40209c26966247d9bf9ad34764de4ac4181f98c2"
XIONG_BINARY_SHA = "f58c54bb41e6e896225df40fab52b4e8e747a0967aa80ea3583c8025f2b7a2a9"
IPSNS_FILE_SHA = "46a3f2b549897df1037ebe257e47b17490bddaa97effb2e31bce20a50ea54b36"
FIRST_AUDIT_SHA = "013a9f50996f20474d43856ad38843f00adfbfea5403dcea3feda1e4dd8b8828"
FIRST_INVENTORY_SHA = "1d947703548d74591246eceedb25dd2c644efe9927667d41b89b7cbe25d30f51"
FIRST_CHECKPOINT_SHA = "b66176ab3da113f202e7f683f6c72347cd5a28b3e43f905d3e53e6a75aeaaeee"
FIRST_AUDITED_TASK = "exp04_er_n120_k05_r01__b10__xiong_restarts__s1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    tmp.replace(path)


def select_tasks(manifest: dict, inventory: list[dict]) -> list[dict]:
    by_id = {r["task_id"]: r for r in inventory}
    tasks = manifest["tasks"]
    if len(tasks) != 78 or len(by_id) != 78 or {t["task_id"] for t in tasks} != set(by_id):
        raise ValueError("EXP11 task inventory mismatch")
    selected = [t for t in tasks if by_id[t["task_id"]]["status"] == "INVALID"]
    if len(selected) != 22 or sum(t["budget_seconds"] for t in selected) != 636:
        raise ValueError("EXP11 invalid-task set changed")
    if any(by_id[t["task_id"]]["error"] != "end-to-end wall budget exceeded" for t in selected):
        raise ValueError("unexpected reason for EXP11 invalid task")
    return selected


def preflight(a: argparse.Namespace) -> tuple[dict, list[dict]]:
    prior = a.prior
    for filename, digest in (("manifest.json", PRIOR_MANIFEST_SHA),
                             ("task_inventory.csv", PRIOR_INVENTORY_SHA),
                             ("audit_report.json", PRIOR_AUDIT_SHA)):
        if sha(prior / filename) != digest:
            raise ValueError(f"frozen EXP11 {filename} hash mismatch")
    manifest = json.loads((prior / "manifest.json").read_text())
    with (prior / "task_inventory.csv").open(newline="") as f:
        inventory = list(csv.DictReader(f))
    invalid = select_tasks(manifest, inventory)
    if (sha(a.first_audit / "audit_report.json") != FIRST_AUDIT_SHA
            or sha(a.first_audit / "task_inventory.csv") != FIRST_INVENTORY_SHA
            or sha(a.first_audit / "checkpoints" / (FIRST_AUDITED_TASK + ".json")) != FIRST_CHECKPOINT_SHA):
        raise ValueError("first EXP22 task independent audit hash mismatch")
    first_report = json.loads((a.first_audit / "audit_report.json").read_text())
    if (first_report["audited"] != 1 or first_report["statuses"]["TIMEOUT"] != 1
            or first_report["credited_endpoints"] != 1 or first_report["violations"]):
        raise ValueError("first EXP22 task has not passed independent audit")
    if invalid[0]["task_id"] != FIRST_AUDITED_TASK:
        raise ValueError("first EXP22 task identity changed")
    # The six one-second tasks cannot be made reliably wall-compliant under
    # observed filesystem/controller overhead. They remain INVALID evidence.
    tasks = [t for t in invalid if t["task_id"] != FIRST_AUDITED_TASK and t["budget_seconds"] > 1]
    if len(tasks) != 15 or sum(t["budget_seconds"] for t in tasks) != 620:
        raise ValueError("remaining task selection changed")
    if (a.exp11_release / "RELEASE_REVISION").read_text().strip() != EXP11_REVISION:
        raise ValueError("EXP11 release revision mismatch")
    if manifest["repo_revision"] != EXP11_REVISION:
        raise ValueError("EXP11 output revision mismatch")
    for path, expected in ((a.xiong_source, XIONG_REVISION), (a.ipsns_source, IPSNS_REVISION)):
        if subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip() != expected:
            raise ValueError("algorithm revision mismatch")
        if subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True).strip():
            raise ValueError("algorithm source checkout is modified")
    if sha(a.binary) != XIONG_BINARY_SHA or sha(a.ipsns_source / "src/mwfas/ipsns.py") != IPSNS_FILE_SHA:
        raise ValueError("algorithm file or binary hash mismatch")
    from experiments.exp10_xiong.input_contract import parse_dimacs
    for row in manifest["inputs"]:
        graph = Path(row["path"])
        if sha(graph) != row["dimacs_sha256"]:
            raise ValueError("original graph byte hash mismatch")
        _, _, info = parse_dimacs(graph, row)
        if info["graph_sha256"] != row["graph_sha256"]:
            raise ValueError("canonical weighted graph hash mismatch")
    return manifest, tasks


def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("prior", "exp11_release", "first_audit", "output", "xiong_source", "binary", "ipsns_source", "exp22_revision"):
        p.add_argument("--" + name.replace("_", "-"), required=True)
    p.add_argument("--preflight-only", action="store_true")
    a = p.parse_args()
    for name in ("prior", "exp11_release", "first_audit", "output", "xiong_source", "binary", "ipsns_source"):
        setattr(a, name, Path(getattr(a, name)))
    manifest, tasks = preflight(a)
    if a.preflight_only:
        print(json.dumps({"status": "PASS", "selected": len(tasks), "sum_budget_seconds": 620,
                          "task_ids": [t["task_id"] for t in tasks]}, sort_keys=True))
        return
    if a.output.exists():
        raise ValueError("refusing to overwrite an existing output")
    a.output.mkdir(parents=True)
    (a.output / "tasks").mkdir(); (a.output / "checkpoints").mkdir()
    run_manifest = {**manifest, "format": "exp22-exp11-recovery-manifest-v1",
                    "repo_revision": a.exp22_revision,
                    "prior_manifest_sha256": PRIOR_MANIFEST_SHA,
                    "prior_inventory_sha256": PRIOR_INVENTORY_SHA,
                    "prior_audit_sha256": PRIOR_AUDIT_SHA,
                    "first_audit_sha256": FIRST_AUDIT_SHA,
                    "exp11_worker_revision": EXP11_REVISION,
                    "tasks": tasks,
                    "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                    "node": platform.node(),
                    "cpu_affinity": sorted(os.sched_getaffinity(0)),
                    "python": sys.version,
                    "cpu_model": next((s.split(":", 1)[1].strip() for s in Path("/proc/cpuinfo").read_text().splitlines() if s.startswith("model name")), "unknown"),
                    "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")}}
    save(a.output / "manifest.json", run_manifest)
    by_id = {r["instance_id"]: r for r in manifest["inputs"]}
    save(a.output / "progress.json", {"phase": "RUNNING", "done": 0, "planned": len(tasks)})
    for index, task in enumerate(tasks, 1):
        folder = a.output / "tasks" / task["task_id"]
        folder.mkdir()
        budget = task["budget_seconds"]
        graph = by_id[task["instance_id"]]
        row = {k: graph[k] for k in ("n", "m", "total_weight", "graph_sha256", "dimacs_sha256")}
        begun = time.monotonic(); begin_unix_ns = time.time_ns(); deadline = begun + budget
        command = [sys.executable, "-m", "experiments.exp11_equal_budget.worker",
                   "--graph", graph["path"], "--row", json.dumps(row),
                   "--arm", task["arm"], "--seed", str(task["seed"]), "--folder", str(folder),
                   "--binary", str(a.binary), "--ipsns-source", str(a.ipsns_source),
                   "--start", repr(begun), "--deadline", repr(deadline)]
        ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        with (folder / "process.log").open("wb") as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                    cwd=a.exp11_release, start_new_session=True)
            terminated = False
            try:
                # Reserve shutdown and checkpoint time. The unmodified worker
                # still receives the original strict deadline.
                proc.wait(timeout=max(0.001, deadline - time.monotonic() - 3.0))
            except subprocess.TimeoutExpired:
                terminated = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        wall = time.monotonic() - begun
        ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        status = "TIMEOUT" if terminated else ("COMPLETED_UNVALIDATED" if proc.returncode == 0 else "FAILED")
        cp = {**task, "status": status, "returncode": proc.returncode,
              "terminated_by_controller": terminated, "task_wall_seconds": wall,
              "wall_budget_compliant": wall <= budget,
              "child_user_cpu_seconds": ru1.ru_utime - ru0.ru_utime,
              "child_system_cpu_seconds": ru1.ru_stime - ru0.ru_stime,
              "start_unix_ns": begin_unix_ns, "end_unix_ns": time.time_ns(),
              "event_count": len(list(folder.glob("event_*.json"))), "command": command,
              "log_sha256": sha(folder / "process.log")}
        save(a.output / "checkpoints" / (task["task_id"] + ".json"), cp)
        save(a.output / "progress.json", {"phase": "RUNNING", "done": index,
                                           "planned": len(tasks), "last_task": task["task_id"],
                                           "last_status": status, "updated_unix": time.time()})
        if not cp["wall_budget_compliant"]:
            save(a.output / "fatal.json", {"task_id": task["task_id"], "reason": "strict wall cap exceeded"})
            raise SystemExit("strict wall cap exceeded; stopped recovery")
        if status == "FAILED":
            save(a.output / "fatal.json", {"task_id": task["task_id"], "reason": "worker failed"})
            raise SystemExit("worker failed; stopped recovery")
    save(a.output / "progress.json", {"phase": "COMPUTATION_COMPLETE_AUDIT_PENDING",
                                       "done": len(tasks), "planned": len(tasks), "updated_unix": time.time()})


if __name__ == "__main__":
    main()
