"""Strict independent DIMACS parser and objective/acyclicity checks."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path


class GraphInputError(ValueError):
    pass


@dataclass(frozen=True)
class Graph:
    vertices: tuple[str, ...]
    arcs: tuple[tuple[str, str, float], ...]


def read_dimacs(path: Path) -> Graph:
    declared_n = declared_m = None
    raw = []
    for number, line in enumerate(path.read_text().splitlines(), start=1):
        parts = line.split()
        if not parts or parts[0] == "c":
            continue
        if parts[0] == "p":
            if len(parts) < 4 or declared_n is not None:
                raise GraphInputError(f"line {number}: malformed or repeated p header")
            try:
                declared_n, declared_m = int(parts[-2]), int(parts[-1])
            except ValueError as exc:
                raise GraphInputError(f"line {number}: invalid graph size") from exc
            if declared_n < 0 or declared_m < 0:
                raise GraphInputError(f"line {number}: negative graph size")
        elif parts[0] == "a":
            if len(parts) < 4:
                raise GraphInputError(f"line {number}: malformed arc")
            try:
                weight = float(parts[3])
            except ValueError as exc:
                raise GraphInputError(f"line {number}: invalid arc weight") from exc
            if not __import__("math").isfinite(weight) or weight < 0:
                raise GraphInputError(f"line {number}: nonfinite or negative weight")
            raw.append((parts[1], parts[2], weight))
        else:
            raise GraphInputError(f"line {number}: unknown record type")
    if declared_m is not None and declared_m != len(raw):
        raise GraphInputError(f"declared {declared_m} arcs, found {len(raw)}")
    endpoints = {v for u, v, _ in raw} | {u for u, v, _ in raw}
    if declared_n is not None:
        start = 0 if "0" in endpoints else 1
        standard = {str(i) for i in range(start, start + declared_n)}
        if not endpoints <= standard:
            raise GraphInputError("nonstandard node labels need an explicit vertex map")
        vertices = standard
    else:
        vertices = endpoints
    aggregated: dict[tuple[str, str], float] = {}
    for u, v, w in raw:
        aggregated[u, v] = aggregated.get((u, v), 0.0) + w
    return Graph(tuple(sorted(vertices, key=lambda x: (0, int(x)) if x.isdigit() else (1, x))),
                 tuple((u, v, w) for (u, v), w in sorted(aggregated.items())))


def backward_weight(graph: Graph, order: list[str]) -> float:
    if len(order) != len(graph.vertices) or set(order) != set(graph.vertices):
        raise ValueError("ordering must contain every graph vertex exactly once")
    rank = {v: i for i, v in enumerate(order)}
    return sum(w for u, v, w in graph.arcs if rank[u] >= rank[v])


def acyclic_after_removal(graph: Graph, removed: set[tuple[str, str]]) -> bool:
    adjacency = {v: [] for v in graph.vertices}
    indegree = {v: 0 for v in graph.vertices}
    for u, v, _ in graph.arcs:
        if (u, v) not in removed:
            adjacency[u].append(v)
            indegree[v] += 1
    queue = deque(v for v, d in indegree.items() if d == 0)
    seen = 0
    while queue:
        u = queue.popleft()
        seen += 1
        for v in adjacency[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
    return seen == len(graph.vertices)
