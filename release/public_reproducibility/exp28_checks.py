"""Independent DIMACS, complete-permutation, objective and DAG checks.

Copied unchanged from the accepted EXP28 integration checker.
"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import deque
from pathlib import Path

def need(test: bool, message: str) -> None:
    if not test:
        raise ValueError(message)

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()

def graph(path: Path, metadata: dict) -> tuple[int, list[tuple[int, int, int]]]:
    need(sha(path) == metadata["dimacs_sha256"], "graph source bytes changed")
    n = m = None
    arcs = []
    for line in path.read_text().splitlines():
        pieces = line.split()
        if not pieces or pieces[0] == "c":
            continue
        if pieces[0] == "p":
            need(n is None and pieces[1] in ("sp", "graph") and len(pieces) == 4, "bad DIMACS header")
            n, m = map(int, pieces[2:])
        else:
            need(n is not None and pieces[0] == "a" and len(pieces) in (4, 5), "bad DIMACS arc")
            arcs.append(tuple(map(int, pieces[1:4])))
    need(n == metadata["n"] and m == metadata["m"] == len(arcs), "graph dimensions changed")
    need(len({(a, b) for a, b, _ in arcs}) == m and all(1 <= a <= n and 1 <= b <= n and a != b and w > 0
             for a, b, w in arcs), "invalid active arcs")
    need(sum(w for _, _, w in arcs) == metadata["total_weight"], "graph weight sum changed")
    norm = {"directed": True, "node_labels": "1-based-integers", "parallel_edges": "absent",
            "self_loops": "absent", "weight_type": "positive-integer"}
    payload = {"format": "mwfas-exp03-graph-v1", "normalization": norm,
               "vertices": list(range(1, n + 1)), "arcs": sorted(arcs)}
    canonical = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    need(canonical == metadata["graph_sha256"], "canonical graph hash changed")
    return n, arcs

def score(path: Path, arm: str, n: int, arcs: list[tuple[int, int, int]]) -> int:
    if arm.startswith("xiong_"):
        rank = [int(value) for value in path.read_text().split()]
    else:
        rank = [-1] * n
        with path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        need(len(rows) == n, "order row count")
        for row in rows:
            vertex = int(row["Node ID"])
            need(1 <= vertex <= n and rank[vertex - 1] == -1, "order vertex repeated/foreign")
            rank[vertex - 1] = int(row["Order"])
    need(len(rank) == n and sorted(rank) == list(range(n)), "incomplete permutation")
    forward = [[] for _ in range(n)]
    indegree = [0] * n
    value = 0
    for a, b, weight in arcs:
        if rank[a - 1] > rank[b - 1]:
            value += weight
        else:
            forward[a - 1].append(b - 1)
            indegree[b - 1] += 1
    todo = deque(i for i, degree in enumerate(indegree) if degree == 0)
    visited = 0
    while todo:
        a = todo.popleft()
        visited += 1
        for b in forward[a]:
            indegree[b] -= 1
            if indegree[b] == 0:
                todo.append(b)
    need(visited == n, "retained arcs cyclic")
    return value

