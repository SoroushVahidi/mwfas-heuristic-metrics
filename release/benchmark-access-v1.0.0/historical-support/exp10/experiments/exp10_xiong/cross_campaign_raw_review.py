"""Read-only EXP05/EXP10 source-byte review for three selected real graphs.

This script uses only the Python standard library and does not import either
campaign's writer or auditor. It prints metadata JSON and never writes files.
Run by streaming it to ``python - EXP05_BASE EXP10_OUTPUT EXP05_AUDIT`` on
Wulver; the source archives, graphs, orders, and checkpoints stay private.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
from collections import Counter, deque
from pathlib import Path


IDS = ("exp05_college_full_count", "exp05_email_full", "exp05_wiki_vote_full_reference")
ARCHIVES = {"exp05_college_full_count": ("CollegeMsg.txt.gz", True),
            "exp05_email_full": ("email-Eu-core.txt.gz", False),
            "exp05_wiki_vote_full_reference": ("wiki-Vote.txt.gz", False)}
NORMALIZATION = {"directed": True, "node_labels": "1-based-integers",
                 "parallel_edges": "absent", "self_loops": "absent", "weight_type": "positive-integer"}


def insist(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def graph(path: Path):
    records = [line.split() for line in path.read_text().splitlines()
               if line.strip() and not line.startswith("c")]
    insist(records and records[0][:2] == ["p", "sp"] and len(records[0]) == 4,
           "malformed graph header: " + str(path))
    n, m = map(int, records[0][2:])
    arcs = []
    for fields in records[1:]:
        insist(fields[0] == "a" and len(fields) == 4, "malformed arc")
        u, v, w = map(int, fields[1:])
        insist(1 <= u <= n and 1 <= v <= n and u != v and w > 0, "invalid weighted arc")
        arcs.append((u, v, w))
    insist(len(arcs) == m and len({(u, v) for u, v, _ in arcs}) == m, "arc count/uniqueness")
    encode = lambda data: json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    graph_hash = hashlib.sha256(encode({"format": "mwfas-exp03-graph-v1",
        "normalization": NORMALIZATION, "vertices": list(range(1, n + 1)),
        "arcs": sorted(arcs)})).hexdigest()
    topology_hash = hashlib.sha256(encode({"format": "exp04-topology-v1", "directed": True,
        "vertices": list(range(1, n + 1)), "arcs": sorted((u, v) for u, v, _ in arcs)})).hexdigest()
    return n, arcs, graph_hash, topology_hash


def source_graph(path: Path, count_events: bool):
    source_nodes = set()
    edge_weights = Counter()
    loops = 0
    with gzip.open(path, "rt") as stream:
        for line in stream:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split()
            insist(len(fields) == (3 if count_events else 2), "source archive format")
            u, v = map(int, fields[:2])
            source_nodes.update((u, v))
            if u == v:
                loops += 1
            elif count_events:
                edge_weights[u, v] += 1
            else:
                edge_weights[u, v] = 1
    rename = {vertex: index for index, vertex in enumerate(sorted(source_nodes), 1)}
    normalized = {(rename[u], rename[v]): weight for (u, v), weight in edge_weights.items()}
    return len(source_nodes), normalized, loops


def csv_order(path: Path) -> list[int]:
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        insist(reader.fieldnames == ["Node ID", "Order"], "order header: " + str(path))
        pairs = [(int(row["Node ID"]), int(row["Order"])) for row in reader]
    insist(len({v for v, _ in pairs}) == len(pairs) and
           sorted(position for _, position in pairs) == list(range(len(pairs))), "order permutation")
    return [v for v, _ in sorted(pairs, key=lambda pair: pair[1])]


def score(n: int, arcs: list[tuple[int, int, int]], order: list[int], complete: bool = True) -> int:
    insist(len(order) == len(set(order)) and all(1 <= v <= n for v in order), "foreign/duplicate vertex")
    if complete:
        insist(len(order) == n, "incomplete order")
    position = {v: i for i, v in enumerate(order)}
    successors = [[] for _ in range(n + 1)]
    indegree = [0] * (n + 1)
    objective = 0
    for u, v, weight in arcs:
        insist(u in position and v in position, "missing nonisolated vertex")
        if position[u] > position[v]:
            objective += weight
        else:
            successors[u].append(v)
            indegree[v] += 1
    queue = deque(v for v in range(1, n + 1) if indegree[v] == 0)
    seen = 0
    while queue:
        seen += 1
        for successor in successors[queue.popleft()]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
    insist(seen == n, "retained graph cyclic")
    return objective


def review(exp05: Path, exp10: Path, audit05: Path) -> dict:
    bench = {r["instance_id"]: r for r in rows(audit05 / "benchmark_inventory.csv") if r["instance_id"] in IDS}
    originals = [r for r in rows(audit05 / "original_inventory.csv") if r["instance_id"] in IDS]
    derived = [r for r in rows(audit05 / "derived_inventory.csv") if any(r["run_id"].startswith(i + "__") for i in IDS)]
    manifest10 = json.loads((exp10 / "manifest.json").read_text())
    insist(manifest10["repo_revision"] == "459f2f586d70367878a47d9ea938f2589ef158ae" and
           manifest10["xiong_revision"] == "8340e1633ba9290a567a882aff4d74f01b38102d" and
           manifest10["ipsns_revision"] == "40209c26966247d9bf9ad34764de4ac4181f98c2",
           "EXP10 source revisions")
    input10 = {r["instance_id"]: r for r in manifest10["input_inventory"] if r["instance_id"] in IDS}
    tasks10 = {r["task_id"]: r for r in rows(exp10 / "audit_inventory.csv")}
    insist(len(bench) == len(input10) == 3 and len(originals) == 60 and len(derived) == 13,
           "source inventory count")
    sealed = exp05 / "recovery-v1/original-sealed"
    manifest05 = json.loads((sealed / "run_manifest.json").read_text())
    insist(manifest05["code_revision"] == "f13cbe50910a4c0fe7ed0527a448aaf0ec7e0d01" and
           manifest05["source_revision"] == manifest10["ipsns_revision"] and
           manifest05["environment"]["slurm_job_id"] == "1423922" and
           manifest05["environment"]["cpu_model"] == manifest10["cpu"],
           "EXP05 execution/source manifest")
    recovery = exp05 / "recovery-v1/campaign-0a404f4a66a9a3e9fbdf6dab8d30654b34fb62c9"
    graph_details = {}
    graph_data = {}
    for iid in IDS:
        b, x = bench[iid], input10[iid]
        original_path = sealed / "graphs" / (iid + ".d")
        production_path = exp05 / "production-output/graphs" / (iid + ".d")
        xiong_path = Path(x["path"])
        expected_dimacs = b["dimacs_sha256"]
        insist(all(sha(path) == expected_dimacs for path in (original_path, production_path, xiong_path)),
               "EXP05/EXP10 graph bytes differ: " + iid)
        n, arcs, gh, th = graph(original_path)
        insist(gh == b["graph_sha256"] == x["graph_sha256"] and th == b["topology_sha256"] and
               n == int(b["n"]) == x["n"] and len(arcs) == int(b["m"]) == x["m"] and
               sum(w for _, _, w in arcs) == int(b["total_weight"]) == x["total_weight"],
               "EXP05/EXP10 graph identity: " + iid)
        archive_name, count_events = ARCHIVES[iid]
        archive = exp05 / "sources/input-archives" / archive_name
        insist(sha(archive) == b["source_sha256"], "source archive hash: " + iid)
        source_n, reconstructed, loops = source_graph(archive, count_events)
        insist(source_n == n and reconstructed == {(u, v): w for u, v, w in arcs} and
               loops == int(b["excluded_self_loop_weight"]), "source reconstruction/loops: " + iid)
        graph_data[iid] = (n, arcs, gh)
        graph_details[iid] = {"weighted_graph_sha256": gh, "dimacs_sha256": expected_dimacs,
            "topology_sha256": th, "source_parent": b["source_parent"],
            "source_sha256": b["source_sha256"], "vertices": n, "directed_arcs": len(arcs),
            "total_arc_weight": sum(w for _, _, w in arcs), "excluded_self_loop_weight": loops,
            "weight_semantics": b["weight_semantics"], "raw_graph_byte_copies_matched": 3}
    originals_by_id = {r["run_id"]: r for r in originals}
    insist(len(originals_by_id) == 60, "duplicate EXP05 run")
    original_counts = Counter()
    original_pass_orders = 0
    for r in originals:
        rid, iid = r["run_id"], r["instance_id"]
        n, arcs, gh = graph_data[iid]
        checkpoint = sealed / "runs" / (rid + ".json")
        record = json.loads(checkpoint.read_text())
        insist(sha(checkpoint) == r["checkpoint_sha256"] and record["run_id"] == rid and
               record["status"] == r["original_status"] and record["graph_sha256"] == gh and
               record["code_revision"] == "f13cbe50910a4c0fe7ed0527a448aaf0ec7e0d01" and
               record["source_revision"] == manifest10["ipsns_revision"],
               "EXP05 original checkpoint: " + rid)
        original_counts[r["original_status"]] += 1
        if r["original_status"] == "PASS":
            order_path = sealed / "orders" / (rid + ".csv")
            value = score(n, arcs, csv_order(order_path))
            insist(sha(order_path) == r["order_sha256"] and value == int(r["objective_weight"]) and
                   abs(value - float(record["reported_objective"])) < 1e-7,
                   "EXP05 original PASS objective: " + rid)
            original_pass_orders += 1
        else:
            insist(not r["objective_weight"] and not r["order_sha256"] and
                   not (sealed / "orders" / (rid + ".csv")).exists(),
                   "non-PASS has objective/order: " + rid)
            if r["original_status"] == "FAIL":
                insist((sealed / "orders" / (rid + ".csv.tmp")).exists(),
                       "original FAIL lacks incomplete order: " + rid)
            elif r["original_status"] == "TIMEOUT":
                insist(record.get("error") == "per-run timeout 120s" and
                       float(r["total_wall_seconds"]) >= 119, "invalid original timeout: " + rid)
    derived_counts = Counter()
    derived_orders = 0
    for r in derived:
        rid = r["run_id"]
        iid = next(i for i in IDS if rid.startswith(i + "__"))
        n, arcs, gh = graph_data[iid]
        insist(r["validation"] == "PASS" and r["derived_status"] == "PASS" and
               r["original_status"] == originals_by_id[rid]["original_status"] and
               r["graph_sha256"] == gh and
               r["original_checkpoint_sha256"] == originals_by_id[rid]["checkpoint_sha256"],
               "EXP05 derived provenance: " + rid)
        if r["kind"] == "isolated_vertex_recovery":
            raw_path = sealed / "orders" / (rid + ".csv.tmp")
            order_path = recovery / "derived" / (rid + ".csv")
            record_path = recovery / "derived" / (rid + ".json")
            record = json.loads(record_path.read_text())
            raw_order = csv_order(raw_path)
            missing = sorted(set(range(1, n + 1)) - set(raw_order))
            insist(originals_by_id[rid]["original_status"] == "FAIL" and
                   sha(raw_path) == r["original_order_sha256"] and
                   r["added_isolates"] == ";".join(map(str, missing)) and
                   score(n, arcs, raw_order, False) == int(r["original_objective"]) and
                   csv_order(order_path) == raw_order + missing,
                   "EXP05 isolated recovery: " + rid)
            insist(record["original_code_revision"] == "f13cbe50910a4c0fe7ed0527a448aaf0ec7e0d01" and
                   record["adapter_revision"] == "0a404f4a66a9a3e9fbdf6dab8d30654b34fb62c9",
                   "EXP05 recovery revision: " + rid)
        elif r["kind"] == "bounded_insertion":
            order_path = recovery / "orders" / (rid + ".csv")
            record_path = recovery / "runs" / (rid + ".json")
            record = json.loads(record_path.read_text())
            insist(originals_by_id[rid]["original_status"] == "SKIPPED_DEPENDENCY",
                   "EXP05 insertion original status: " + rid)
            insist(record["code_revision"] == "0a404f4a66a9a3e9fbdf6dab8d30654b34fb62c9" and
                   record["source_revision"] == manifest10["ipsns_revision"] and record["status"] == "PASS",
                   "EXP05 insertion revision/status: " + rid)
        else:
            raise ValueError("unexpected derived kind: " + rid)
        value = score(n, arcs, csv_order(order_path))
        insist(sha(order_path) == r["derived_order_sha256"] and
               sha(record_path) == r["record_sha256"] and value == int(r["derived_objective"]),
               "EXP05 derived objective/hash: " + rid)
        derived_counts[r["kind"]] += 1
        derived_orders += 1
    xiong_values = {}
    ipsns_timeouts = 0
    for iid in IDS:
        n, arcs, gh = graph_data[iid]
        values = []
        for seed in (1, 2):
            rid = f"{iid}__xiong_rasstar__s{seed}"
            checkpoint = json.loads((exp10 / "checkpoints" / (rid + ".json")).read_text())
            row = tasks10[rid]
            path = exp10 / "tasks" / rid / "ranks.txt"
            rank = [int(value) for value in path.read_text().split()]
            insist(len(rank) == n and set(rank) == set(range(n)), "Xiong rank permutation: " + rid)
            order = [vertex for _, vertex in sorted((position, vertex) for vertex, position in enumerate(rank, 1))]
            value = score(n, arcs, order)
            raw = json.loads((exp10 / "tasks" / rid / "raw.json").read_text())
            insist(checkpoint["status"] == "COMPLETED_UNVALIDATED" and row["status"] == "PASS" and
                   checkpoint["graph_sha256"] == gh and sha(path) == row["order_sha256"] and
                   value == int(row["objective"]) == int(raw["reported_objective"]),
                   "EXP10 Xiong objective/hash: " + rid)
            values.append(value)
            ipsns_id = f"{iid}__ipsns__s{seed}"
            ipsns_cp = json.loads((exp10 / "checkpoints" / (ipsns_id + ".json")).read_text())
            ipsns_row = tasks10[ipsns_id]
            insist(ipsns_cp["status"] == "TIMEOUT" and ipsns_row["status"] == "TIMEOUT" and
                   not ipsns_row["objective"] and ipsns_cp["process_wall_seconds"] >= 120 and
                   not (exp10 / "tasks" / ipsns_id / "raw.json").exists(),
                   "EXP10 IPSNS timeout: " + ipsns_id)
            ipsns_timeouts += 1
        xiong_values[iid] = values
    return {"format": "exp10-exp05-raw-review-v1", "graph_details": graph_details,
            "exp05_original_task_counts": dict(original_counts),
            "exp05_original_pass_orders_rescored": original_pass_orders,
            "exp05_derived_counts": dict(derived_counts),
            "exp05_derived_orders_rescored": derived_orders,
            "exp10_xiong_orderings_rescored": 6,
            "exp10_xiong_objectives": xiong_values,
            "exp10_ipsns_timeouts_verified": ipsns_timeouts,
            "source_revisions": {k: manifest10[k] for k in ("repo_revision", "xiong_revision", "ipsns_revision")},
            "execution_context": {"exp05_job_id": manifest05["environment"]["slurm_job_id"],
                "exp05_hostname": manifest05["environment"]["hostname"],
                "exp05_cpu_model": manifest05["environment"]["cpu_model"],
                "exp05_workers": int(manifest05["command"][manifest05["command"].index("--workers") + 1]),
                "exp05_slurm_cpus_per_task": manifest05["environment"]["slurm_cpus_per_task"],
                "exp05_manifest_status": manifest05["status"],
                "exp10_job_id": manifest10["slurm_job_id"],
                "exp10_hostname": manifest10["hostname"], "exp10_cpu_model": manifest10["cpu"]},
            "source_audit_sha256": {"exp05_benchmark_inventory": sha(audit05 / "benchmark_inventory.csv"),
                "exp05_original_inventory": sha(audit05 / "original_inventory.csv"),
                "exp05_derived_inventory": sha(audit05 / "derived_inventory.csv"),
                "exp05_run_manifest": sha(sealed / "run_manifest.json"),
                "exp10_manifest": sha(exp10 / "manifest.json"),
                "exp10_task_inventory": sha(exp10 / "audit_inventory.csv")}}


if __name__ == "__main__":
    print(json.dumps(review(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])),
                     indent=2, sort_keys=True))
