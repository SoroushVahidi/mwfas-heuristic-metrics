"""Read-only, independently implemented EXP10 frozen-output review.

Run with ``python - <output-dir>`` after streaming this file to Wulver stdin.
The only output is a metadata-only JSON report on stdout; the frozen directory
is never opened for writing. This deliberately does not import the run/audit
implementation.
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def dimacs(path: Path) -> tuple[int, list[tuple[int, int, int]], str, str]:
    lines = [line.split() for line in path.read_text().splitlines()]
    records = [x for x in lines if x and x[0] != "c"]
    require(records and records[0][:2] == ["p", "sp"] and len(records[0]) == 4,
            f"invalid graph header: {path}")
    n, m = map(int, records[0][2:])
    require(len(records) == m + 1, f"graph arc count: {path}")
    arcs = []
    for fields in records[1:]:
        require(len(fields) == 4 and fields[0] == "a", f"invalid arc: {path}")
        u, v, weight = map(int, fields[1:])
        require(1 <= u <= n and 1 <= v <= n and u != v and weight > 0,
                f"invalid weighted arc: {path}")
        arcs.append((u, v, weight))
    require(len({(u, v) for u, v, _ in arcs}) == m, f"duplicate arc: {path}")
    weighted = {"format": "mwfas-exp03-graph-v1", "normalization": {
        "directed": True, "node_labels": "1-based-integers", "parallel_edges": "absent",
        "self_loops": "absent", "weight_type": "positive-integer"},
        "vertices": list(range(1, n + 1)), "arcs": sorted(arcs)}
    topology = {"format": "exp04-topology-v1", "directed": True,
                "vertices": list(range(1, n + 1)),
                "arcs": sorted((u, v) for u, v, _ in arcs)}
    encode = lambda obj: json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return n, arcs, hashlib.sha256(encode(weighted)).hexdigest(), hashlib.sha256(encode(topology)).hexdigest()


def csv_order(path: Path) -> list[int]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    vertices = [int(row["Node ID"]) for row in rows]
    positions = [int(row["Order"]) for row in rows]
    require(len(vertices) == len(set(vertices)) and sorted(positions) == list(range(len(rows))),
            f"invalid CSV order: {path}")
    return [vertex for _, vertex in sorted(zip(positions, vertices))]


def score(order: list[int], n: int, arcs: list[tuple[int, int, int]]) -> int:
    require(len(order) == n and set(order) == set(range(1, n + 1)), "incomplete permutation")
    place = {vertex: i for i, vertex in enumerate(order)}
    removed = 0
    successors = [[] for _ in range(n + 1)]
    indegree = [0] * (n + 1)
    for u, v, weight in arcs:
        if place[u] >= place[v]:
            removed += weight
        else:
            successors[u].append(v)
            indegree[v] += 1
    queue = deque(v for v in range(1, n + 1) if indegree[v] == 0)
    seen = 0
    while queue:
        seen += 1
        for v in successors[queue.popleft()]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    require(seen == n, "retained graph contains a cycle")
    return removed


def table(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def check(output: Path) -> dict:
    manifest = json.loads((output / "manifest.json").read_text())
    audit = json.loads((output / "audit_report.json").read_text())
    inventory = table(output / "audit_inventory.csv")
    pairs = table(output / "paired_results.csv")
    listed = {name: sha for sha, name in
              (line.split(maxsplit=1) for line in (output / "checksums.sha256").read_text().splitlines())}
    for name in ("manifest.json", "audit_inventory.csv", "paired_results.csv", "audit_report.json"):
        require(listed.get(name) == digest(output / name), f"source checksum mismatch: {name}")
    require(manifest["task_count"] == 84 and len(manifest["tasks"]) == 84, "task manifest count")
    require(len(manifest["input_inventory"]) == 21 and len(pairs) == 42 and len(inventory) == 84,
            "source table count")
    require(manifest["task_wall_cap_seconds"] == 120, "wall cap changed")
    require(manifest["repo_revision"] == "459f2f586d70367878a47d9ea938f2589ef158ae", "run revision")
    require(manifest["xiong_revision"] == "8340e1633ba9290a567a882aff4d74f01b38102d", "Xiong revision")
    require(manifest["ipsns_revision"] == "40209c26966247d9bf9ad34764de4ac4181f98c2", "IPSNS revision")
    first_command = json.loads((output / "checkpoints" /
                                (manifest["tasks"][0]["task_id"] + ".json")).read_text())["command"]
    option = lambda name: first_command[first_command.index(name) + 1]
    binary = Path(option("--xiong-binary"))
    ipsns_source = Path(option("--ipsns-source"))
    xiong_source = binary.parent.parent / "source" / "xiong"
    require(digest(binary) == manifest["xiong_binary_sha256"], "Xiong binary hash mismatch")
    for label, checkout, revision in (("Xiong", xiong_source, manifest["xiong_revision"]),
                                      ("IPSNS", ipsns_source, manifest["ipsns_revision"])):
        actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        require(actual == revision, f"{label} source checkout revision")
        dirty = subprocess.check_output(["git", "-C", str(checkout), "status", "--porcelain"], text=True).strip()
        require(not dirty, f"{label} source checkout changed")
    by_id = {row["instance_id"]: row for row in manifest["input_inventory"]}
    require(len(by_id) == 21, "duplicate instance ID")
    graphs = {}
    for instance_id, row in by_id.items():
        source = Path(row["path"])
        require(digest(source) == row["dimacs_sha256"], f"DIMACS hash: {instance_id}")
        n, arcs, weighted_sha, topo_sha = dimacs(source)
        require((n, len(arcs), sum(w for _, _, w in arcs), weighted_sha) ==
                (row["n"], row["m"], row["total_weight"], row["graph_sha256"]),
                f"weighted graph identity: {instance_id}")
        graphs[instance_id] = (n, arcs, topo_sha)
    audited = {row["task_id"]: row for row in inventory}
    require(len(audited) == 84, "duplicate audit task")
    statuses: Counter = Counter()
    by_method: dict[str, Counter] = defaultdict(Counter)
    objectives = {}
    task_walls = {}
    algorithm_ms = []
    ipsns_algorithm_seconds = []
    synthetic_algorithm_ms = []
    isolate_recoveries = 0
    for task in manifest["tasks"]:
        tid = task["task_id"]
        cp = json.loads((output / "checkpoints" / (tid + ".json")).read_text())
        row = audited[tid]
        iid, method, seed = task["instance_id"], task["algorithm"], task["seed"]
        n, arcs, topo_sha = graphs[iid]
        require(all(cp[key] == task[key] for key in ("task_id", "instance_id", "algorithm", "seed",
                                                    "graph_sha256", "topology_sha256")), f"checkpoint identity: {tid}")
        require(task["topology_sha256"] == topo_sha and task["graph_sha256"] == by_id[iid]["graph_sha256"],
                f"graph/task hash: {tid}")
        require(row["instance_id"] == iid and row["algorithm"] == method and int(row["seed"]) == seed,
                f"audit row identity: {tid}")
        command = cp["command"]
        require(command[command.index("--algorithm") + 1] == method and
                int(command[command.index("--seed") + 1]) == seed and
                command[command.index("--xiong-binary") + 1] == str(binary) and
                command[command.index("--ipsns-source") + 1] == str(ipsns_source) and
                command[command.index("--graph") + 1] == by_id[iid]["path"],
                f"task command mismatch: {tid}")
        command_row = json.loads(command[command.index("--row") + 1])
        require(command_row["instance_id"] == iid and
                command_row["graph_sha256"] == task["graph_sha256"] and
                command_row["source_revision"] == manifest["ipsns_revision"],
                f"task row/source revision mismatch: {tid}")
        folder = output / "tasks" / tid
        require(digest(folder / "process.log") == cp["log_sha256"], f"process log hash: {tid}")
        require(abs(float(row["process_wall_seconds"]) - cp["process_wall_seconds"]) < 1e-9,
                f"process wall mismatch: {tid}")
        task_walls[tid] = cp["process_wall_seconds"]
        if cp["status"] == "TIMEOUT":
            require(method == "ipsns" and cp["returncode"] == -9 and cp["process_wall_seconds"] >= 120,
                    f"unexpected timeout: {tid}")
            require(row["status"] == "TIMEOUT" and not row["objective"] and not row["order_sha256"],
                    f"timeout given objective: {tid}")
            require(not (folder / "raw.json").exists(), f"timeout raw result exists: {tid}")
            statuses["TIMEOUT"] += 1; by_method[method]["TIMEOUT"] += 1
            continue
        require(cp["status"] == "COMPLETED_UNVALIDATED" and cp["returncode"] == 0,
                f"nonterminal or failed checkpoint: {tid}")
        raw = json.loads((folder / "raw.json").read_text())
        if method == "xiong_rasstar":
            stdout_fields = (folder / "xiong.stdout").read_text().strip().split(",")
            require(len(stdout_fields) == 3 and int(stdout_fields[1]) == raw["reported_objective"] and
                    int(stdout_fields[2]) == raw["algorithm_only_ms"] and
                    not (folder / "xiong.stderr").read_text().strip(),
                    f"Xiong executable output: {tid}")
            for field in ("dimacs_sha256", "graph_sha256", "n", "m", "total_weight"):
                require(raw["input"][field] == by_id[iid][field], f"Xiong input metadata: {tid}, {field}")
            ranks = [int(value) for value in (folder / "ranks.txt").read_text().split()]
            require(len(ranks) == n and set(ranks) == set(range(n)), f"Xiong rank permutation: {tid}")
            order = [vertex for _, vertex in sorted((rank, vertex) for vertex, rank in enumerate(ranks, 1))]
            order_path = folder / "ranks.txt"
            converted = [list(map(int, line.split())) for line in (folder / "input.w").read_text().splitlines()]
            require(converted[0] == [n, len(arcs)] and converted[1:] ==
                    [[u - 1, v - 1, w] for u, v, w in arcs], f"W conversion: {tid}")
            require(int(raw["algorithm_only_ms"]) == int(row["algorithm_only_ms"]), f"Xiong time: {tid}")
            algorithm_ms.append(int(raw["algorithm_only_ms"]))
            if iid.startswith("exp04_"):
                synthetic_algorithm_ms.append(int(raw["algorithm_only_ms"]))
        else:
            raw_order = csv_order(folder / "order.csv")
            order_path = folder / "complete_order.csv"
            order = csv_order(order_path)
            missing = sorted(set(range(1, n + 1)) - set(raw_order))
            incident = {u for u, _, _ in arcs} | {v for _, v, _ in arcs}
            require(not (set(missing) & incident) and order == raw_order + missing,
                    f"IPSNS isolate completion: {tid}")
            provenance = raw["ordering_provenance"]
            require(provenance["missing_isolated_vertices"] == missing and
                    provenance["raw_order_sha256"] == digest(folder / "order.csv") and
                    provenance["derived_order_sha256"] == digest(order_path) and
                    int(raw["algorithm_info"]["n_iters"]) <= 200,
                    f"IPSNS source/provenance: {tid}")
            require((row["raw_order_status"] == "INCOMPLETE_ISOLATES") == bool(missing),
                    f"IPSNS isolate label: {tid}")
            raw_place = {vertex: position for position, vertex in enumerate(raw_order)}
            require(abs(float(raw["reported_objective"]) -
                        sum(w for u, v, w in arcs if raw_place[u] >= raw_place[v])) < 1e-7,
                    f"raw IPSNS objective: {tid}")
            ipsns_algorithm_seconds.append(float(raw["algorithm_only_seconds"]))
            if missing:
                isolate_recoveries += 1
        value = score(order, n, arcs)
        require(abs(value - float(raw["reported_objective"])) < 1e-7 and
                value == int(row["objective"]) and digest(order_path) == row["order_sha256"],
                f"objective or order hash: {tid}")
        expected_status = "PASS_DERIVED_ISOLATES" if method == "ipsns" and missing else "PASS"
        require(row["status"] == expected_status, f"audit status: {tid}")
        objectives[iid, seed, method] = value
        statuses[expected_status] += 1; by_method[method][expected_status] += 1
    computed_pairs: Counter = Counter()
    for pair in pairs:
        iid, seed = pair["instance_id"], int(pair["seed"])
        x = objectives.get((iid, seed, "xiong_rasstar"))
        i = objectives.get((iid, seed, "ipsns"))
        require(str(x) == pair["xiong_objective"] and
                (str(i) if i is not None else "") == pair["ipsns_objective"],
                f"pair objective: {iid}, seed {seed}")
        comparison = "NOT_COMPARABLE" if i is None else ("IPSNS_WIN" if i < x else "XIONG_WIN" if x < i else "TIE")
        require(pair["comparison"] == comparison, f"pair comparison: {iid}, seed {seed}")
        computed_pairs[comparison] += 1
    require(sum(statuses.values()) == 84 and dict(statuses) == {k: v for k, v in audit["statuses"].items() if v},
            "aggregate status discrepancy")
    require(dict(computed_pairs) == {k: v for k, v in audit["comparisons"].items() if v},
            "aggregate comparison discrepancy")
    require(not audit["violations"] and audit["audited"] == 84, "source audit violations")
    return {"format": "exp10-final-independent-review-v1", "source_output": output.name,
            "graphs_reparsed": len(graphs), "checkpoints_reparsed": len(manifest["tasks"]),
            "successful_orderings_rescored": len(objectives), "retained_dags_verified": len(objectives),
            "source_checksum_files_verified": 4, "statuses": dict(statuses),
            "xiong_binary_sha256_verified": manifest["xiong_binary_sha256"],
            "source_checkouts_verified_clean": ["xiong", "ipsns"],
            "method_statuses": {key: dict(value) for key, value in by_method.items()},
            "seed_pair_comparisons": dict(computed_pairs), "isolate_completions": isolate_recoveries,
            "source_revisions": {key: manifest[key] for key in ("repo_revision", "xiong_revision", "ipsns_revision")},
            "source_sha256": {name: digest(output / name) for name in
                              ("manifest.json", "audit_inventory.csv", "paired_results.csv", "audit_report.json")},
            "xiong_algorithm_only_ms_median": statistics.median(algorithm_ms),
            "synthetic_xiong_algorithm_only_ms_median": statistics.median(synthetic_algorithm_ms),
            "synthetic_ipsns_algorithm_only_seconds_median": statistics.median(ipsns_algorithm_seconds),
            "total_task_process_wall_seconds": sum(task_walls.values())}


if __name__ == "__main__":
    print(json.dumps(check(Path(sys.argv[1])), indent=2, sort_keys=True))
