"""Strict independent input contract for the pinned EXP04/05 weighted graphs."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path

MAX64 = (1 << 63) - 1


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected(repo: Path) -> list[dict]:
    cfg = json.loads((repo / "experiments/exp10_xiong/plan.json").read_text())
    with gzip.open(repo / cfg["canonical_inventory"], "rt", newline="") as stream:
        rows = list(csv.DictReader(stream))
    synthetic = [r for r in rows if r["campaign"] == "EXP04"
                 and int(r["target_degree"]) == cfg["synthetic"]["target_degree"]
                 and int(r["n"]) in cfg["synthetic"]["sizes"]
                 and int(r["instance_id"].split("_r")[-1]) in cfg["synthetic"]["replicates"]]
    real = [r for r in rows if r["campaign"] == "EXP05"
            and r["instance_id"] in cfg["real_world_ids"]]
    if len(synthetic) != 18 or len(real) != 3 or {r["instance_id"] for r in real} != set(cfg["real_world_ids"]):
        raise ValueError("prespecified input selection mismatch")
    out = sorted(synthetic + real, key=lambda r: r["instance_id"])
    if len({r["graph_sha256"] for r in out}) != 21:
        raise ValueError("duplicate weighted graph")
    return out


def graph_path(root: Path, row: dict) -> Path:
    folder = "mwfas-exp04" if row["campaign"] == "EXP04" else "mwfas-exp05"
    return root / folder / "production-output/graphs" / (row["instance_id"] + ".d")


def parse_dimacs(path: Path, row: dict | None = None) -> tuple[int, list[tuple[int, int, int]], dict]:
    header = None
    arcs = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        words = line.split()
        if not words or words[0] == "c":
            continue
        if words[0] == "p" and header is None and len(words) == 4 and words[1] == "sp":
            n, m = map(int, words[2:]); header = (n, m)
            if n < 1 or m < 0: raise ValueError("invalid DIMACS size")
        elif words[0] == "a" and header is not None and len(words) == 4:
            u, v, w = map(int, words[1:]); n = header[0]
            if not (1 <= u <= n and 1 <= v <= n and u != v and 1 <= w <= MAX64):
                raise ValueError(f"invalid vertex/weight at line {lineno}")
            arcs.append((u, v, w))
        else:
            raise ValueError(f"malformed DIMACS at line {lineno}")
    if header is None or len(arcs) != header[1] or len({(u, v) for u, v, _ in arcs}) != len(arcs):
        raise ValueError("missing header, arc count mismatch, or parallel arcs")
    n, m = header
    weight = sum(w for _, _, w in arcs)
    incident = [0] * n
    opposing = {(u, v) for u, v, _ in arcs}
    for u, v, w in arcs:
        incident[u - 1] += w; incident[v - 1] += w
    max_degree_weight = max(incident, default=0)
    if weight > MAX64 or 2 * max_degree_weight + 1 > MAX64:
        raise ValueError("signed-64-bit objective or heap range overflow")
    from mwfas_data.generation import canonical_graph_bytes
    import networkx as nx
    g = nx.DiGraph(); g.add_nodes_from(range(1, n + 1))
    g.add_weighted_edges_from(arcs)
    canonical = hashlib.sha256(canonical_graph_bytes(g)).hexdigest()
    info = {"n": n, "m": m, "total_weight": weight, "graph_sha256": canonical,
            "dimacs_sha256": digest(path), "max_incident_weight": max_degree_weight,
            "isolated_vertices": n - len({u for u, _, _ in arcs} | {v for _, v, _ in arcs}),
            "opposing_pairs": sum((v, u) in opposing for u, v, _ in arcs) // 2}
    if row:
        for key in ("n", "m", "total_weight"):
            if int(row[key]) != info[key]: raise ValueError(f"{key} mismatch: {path}")
        for key in ("graph_sha256", "dimacs_sha256"):
            if row[key] != info[key]: raise ValueError(f"{key} mismatch: {path}")
    return n, arcs, info


def write_w(path: Path, n: int, arcs: list[tuple[int, int, int]]) -> None:
    path.write_text(f"{n} {len(arcs)}\n" + "".join(f"{u-1} {v-1} {w}\n" for u, v, w in arcs))


def check_w(path: Path, n: int, arcs: list[tuple[int, int, int]]) -> None:
    words = [line.split() for line in path.read_text().splitlines()]
    if list(map(int, words[0])) != [n, len(arcs)]: raise ValueError("W header mismatch")
    converted = [tuple(map(int, line)) for line in words[1:]]
    if converted != [(u - 1, v - 1, w) for u, v, w in arcs]:
        raise ValueError("W conversion changed arcs or weights")
