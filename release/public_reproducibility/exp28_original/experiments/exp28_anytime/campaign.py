"""EXP28 pilot controller with end-to-end strict method deadlines."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from .audit import expected_tasks, graph, sha

HERE = Path(__file__).resolve().parent


def revision(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def atomic(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    os.replace(tmp, path)


def source_check(path: Path, expected: str) -> None:
    if revision(path) != expected:
        raise ValueError("frozen source revision mismatch")
    if subprocess.check_output(["git", "-C", str(path), "status", "--porcelain"], text=True).strip():
        raise ValueError("frozen source checkout is modified")


def source_archive_sha(path: Path) -> str:
    process = subprocess.Popen(["git", "-C", str(path), "archive", "--format=tar", "HEAD"],
                               stdout=subprocess.PIPE)
    digest = hashlib.sha256()
    assert process.stdout is not None
    for block in iter(lambda: process.stdout.read(1024 * 1024), b""):
        digest.update(block)
    if process.wait() != 0:
        raise ValueError("cannot archive Xiong source")
    return digest.hexdigest()


def preflight(a: argparse.Namespace) -> tuple[dict, list[dict], dict]:
    protocol = json.loads(a.protocol.read_text())
    source_check(a.baseline_source, protocol["baseline_revision"])
    source_check(a.xiong_source, protocol["xiong_revision"])
    if source_archive_sha(a.xiong_source) != protocol["xiong_source_archive_sha256"]:
        raise ValueError("original-author Xiong source archive hash differs")
    if sha(a.baseline_source / "src/mwfas/ipsns.py") != protocol["ipsns_file_sha256"]:
        raise ValueError("IPSNS source file hash differs")
    if sha(a.xiong_binary) != protocol["xiong_binary_sha256"]:
        raise ValueError("Xiong executable hash differs")
    if (a.adapter_release / "RELEASE_REVISION").read_text().strip() != protocol["adapter_release_revision"]:
        raise ValueError("adapter source release revision differs")
    import igraph
    import networkx
    if igraph.__version__ != "1.0.0" or networkx.__version__ != "3.6.1":
        raise ValueError("frozen adapter dependency version differs")
    paths = {gid: Path(path) for gid, path in json.loads(a.graph_paths.read_text()).items()}
    if set(paths) != set(protocol["graphs"]):
        raise ValueError("graph path roster differs from protocol")
    candidate_file = a.release / "experiments/exp25_preflight/candidate_graphs.csv"
    candidates = {row["instance_id"]: row for row in csv.DictReader(candidate_file.open(newline=""))}
    inputs = {}
    for gid, cfg in protocol["graphs"].items():
        candidate = candidates[gid]
        if (candidate["dimacs_sha256"], candidate["canonical_graph_sha256"],
                int(candidate["original_loop_weight_constant"])) != (
                cfg["dimacs_sha256"], cfg["canonical_graph_sha256"], cfg["source_loop_constant"]):
            raise ValueError("EXP25 selection and EXP27 protocol differ")
        path = paths[gid]
        n, arcs, digest = graph(path)
        if (sha(path), digest, n, len(arcs), sum(w for _, _, w in arcs)) != (
                cfg["dimacs_sha256"], cfg["canonical_graph_sha256"], cfg["n"], cfg["m"], cfg["total_weight"]):
            raise ValueError("frozen graph bytes or canonical identity differ")
        inputs[gid] = {"path": str(path), "dimacs_sha256": sha(path), "graph_sha256": digest,
                       "n": n, "m": len(arcs), "total_weight": sum(w for _, _, w in arcs)}
    tasks = expected_tasks(protocol)
    if len(tasks) != protocol["max_tasks"] or sum(t["cap_seconds"] for t in tasks) != protocol["nominal_cap_seconds"]:
        raise ValueError("pilot task/cap ceiling changed")
    if len({t["task_id"] for t in tasks}) != len(tasks):
        raise ValueError("duplicate task identity")
    if os.environ.get("SLURM_JOB_ID"):
        if len(os.sched_getaffinity(0)) != 1 or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) != 1:
            raise ValueError("Slurm CPU allocation/affinity differs from one CPU")
        if int(os.environ.get("SLURM_MEM_PER_NODE", "0")) < 8000:
            raise ValueError("Slurm memory allocation below 8 GB")
    return protocol, tasks, inputs


def run(a: argparse.Namespace) -> None:
    protocol, tasks, inputs = preflight(a)
    if a.preflight_only:
        print(json.dumps({"status": "PASS", "graphs": len(inputs), "tasks": len(tasks),
                          "nominal_cap_seconds": sum(t["cap_seconds"] for t in tasks),
                          "input_hashes": {gid: {k: row[k] for k in ("dimacs_sha256", "graph_sha256")}
                                           for gid, row in inputs.items()}}, sort_keys=True))
        return
    if a.task_index is None:
        if a.output.exists():
            raise ValueError("refusing to overwrite any prior output")
        a.output.mkdir(parents=True)
        for child in ("tasks", "checkpoints", "heartbeats"):
            (a.output / child).mkdir()
    elif not (a.output / "manifest.json").exists():
        raise ValueError("array task requires a preinitialized manifest")
    release_revision = (a.release / "RELEASE_REVISION").read_text().strip()
    if release_revision != a.release_revision:
        raise ValueError("release revision argument/file mismatch")
    manifest = {"format": "exp28-anytime-manifest-v1", "release": str(a.release),
                "release_revision": release_revision,
                "protocol_path": str(a.protocol), "protocol_sha256": sha(a.protocol),
                "graph_paths_file": str(a.graph_paths), "graph_paths_sha256": sha(a.graph_paths),
                "candidate_graphs_sha256": sha(a.release / "experiments/exp25_preflight/candidate_graphs.csv"),
                "controller_sha256": sha(HERE / "campaign.py"),
                "worker_sha256": sha(HERE / "worker.py"),
                "instrumented_ipsns_sha256": sha(HERE / "ipsns_pinned_instrumented.py"),
                "independent_auditor_sha256": sha(HERE / "audit.py"),
                "adapter_release_revision": protocol["adapter_release_revision"],
                "baseline_revision": protocol["baseline_revision"],
                "ipsns_file_sha256": protocol["ipsns_file_sha256"],
                "xiong_revision": protocol["xiong_revision"],
                "xiong_source_archive_sha256": protocol["xiong_source_archive_sha256"],
                "xiong_binary_sha256": protocol["xiong_binary_sha256"],
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "slurm_node": os.environ.get("SLURMD_NODENAME"),
                "slurm_cpus_per_task": os.environ.get("SLURM_CPUS_PER_TASK"),
                "slurm_mem_per_node": os.environ.get("SLURM_MEM_PER_NODE"),
                "node": platform.node(), "cpu_affinity": sorted(os.sched_getaffinity(0)),
                "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                                   if line.startswith("model name")), "unknown"),
                "python": sys.version,
                "thread_env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
                "inputs": inputs, "tasks": tasks, "started_unix_ns": time.time_ns()}
    if a.task_index is None:
        atomic(a.output / "manifest.json", manifest)
    else:
        existing = json.loads((a.output / "manifest.json").read_text())
        if (existing["release_revision"] != release_revision or existing["protocol_sha256"] != sha(a.protocol)
                or existing["graph_paths_sha256"] != sha(a.graph_paths)
                or existing["tasks"] != tasks or existing["inputs"] != inputs):
            raise ValueError("array task manifest differs")
    if a.initialize_only:
        return
    selected = list(enumerate(tasks, 1)) if a.task_index is None else [(a.task_index + 1, tasks[a.task_index])]
    progress = {"phase": "RUNNING", "done": 0, "planned": len(selected), "active_task": None, "updated_unix_ns": time.time_ns()}
    lock = threading.Lock()
    def save_progress(path: Path) -> None:
        with lock:
            progress["updated_unix_ns"] = time.time_ns()
            atomic(path, progress)
    progress_path = a.output / ("progress.json" if a.task_index is None else f"heartbeats/{tasks[a.task_index]['task_id']}.json")
    save_progress(progress_path)
    for ordinal, task in selected:
        folder = a.output / "tasks" / task["task_id"]
        folder.mkdir()
        progress["active_task"] = task["task_id"]
        save_progress(progress_path)
        start = time.monotonic(); start_ns = time.time_ns()
        deadline = start + task["cap_seconds"]
        command = [sys.executable, "-m", "experiments.exp28_anytime.worker",
                   "--graph", inputs[task["graph_id"]]["path"], "--arm", task["arm"],
                   "--task-id", task["task_id"], "--folder", str(folder),
                   "--graph-sha256", task["graph_sha256"],
                   "--baseline-source", str(a.baseline_source), "--xiong-binary", str(a.xiong_binary),
                   "--start-monotonic", repr(start), "--deadline-monotonic", repr(deadline),
                   "--internal-reserve-seconds", str(protocol["worker_internal_reserve_seconds"])]
        if task["seed"] is not None:
            command += ["--seed", str(task["seed"])]
        stop = threading.Event()
        def heartbeat() -> None:
            while not stop.wait(5):
                save_progress(progress_path)
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        timed_out = False
        with (folder / "process.log").open("wb") as log:
            proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                    cwd=a.release, start_new_session=True)
            try:
                proc.wait(timeout=max(0.001, deadline - time.monotonic() - protocol["controller_shutdown_reserve_seconds"]))
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        stop.set(); thread.join(timeout=1)
        end = time.monotonic(); end_ns = time.time_ns()
        ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        wall = end - start
        event_count = len(list(folder.glob("event_*.json")))
        status = ("INVALID" if wall > task["cap_seconds"] else
                  "TIMEOUT" if timed_out else
                  "FAILED" if proc.returncode not in (0, 124) else
                  "TIMEOUT" if proc.returncode == 124 or task["arm"] == "xiong_restarts" else
                  "PASS")
        checkpoint = {**task, "status": status, "returncode": proc.returncode,
                      "terminated_by_controller": timed_out,
                      "start_monotonic": start, "deadline_monotonic": deadline,
                      "start_unix_ns": start_ns, "end_unix_ns": end_ns,
                      "task_wall_seconds": wall, "wall_budget_compliant": wall <= task["cap_seconds"],
                      "child_cpu_seconds": (ru1.ru_utime + ru1.ru_stime - ru0.ru_utime - ru0.ru_stime),
                      "child_user_cpu_seconds": ru1.ru_utime - ru0.ru_utime,
                      "child_system_cpu_seconds": ru1.ru_stime - ru0.ru_stime,
                      "cumulative_child_peak_rss_kib": ru1.ru_maxrss,
                      "event_count": event_count, "command": command,
                      "log_sha256": sha(folder / "process.log")}
        atomic(a.output / "checkpoints" / (task["task_id"] + ".json"), checkpoint)
        progress.update(done=1 if a.task_index is not None else ordinal, active_task=None, last_task=task["task_id"], last_status=status)
        save_progress(progress_path)
        if status == "INVALID":
            atomic(a.output / "fatal.json", {"task_id": task["task_id"], "reason": "strict wall cap exceeded"})
            raise SystemExit("strict wall cap exceeded; stopped pilot")
        if status == "FAILED":
            text = (folder / "process.log").read_text(errors="replace")
            if any(s in text for s in ("mismatch", "differs", "malformed", "incomplete", "changed integer weights")):
                atomic(a.output / "fatal.json", {"task_id": task["task_id"], "reason": "method contract failure"})
                raise SystemExit("method contract failure; stopped pilot")
    progress.update(phase="COMPUTATION_COMPLETE_AUDIT_PENDING", active_task=None)
    save_progress(progress_path)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("release", "output", "graph_paths", "protocol", "baseline_source",
                 "xiong_source", "xiong_binary", "adapter_release", "release_revision"):
        p.add_argument("--" + name.replace("_", "-"), required=True)
    p.add_argument("--preflight-only", action="store_true")
    p.add_argument("--initialize-only", action="store_true")
    p.add_argument("--task-index", type=int)
    args = p.parse_args()
    for name in ("release", "output", "graph_paths", "protocol", "baseline_source",
                 "xiong_source", "xiong_binary", "adapter_release"):
        setattr(args, name, Path(getattr(args, name)))
    run(args)
