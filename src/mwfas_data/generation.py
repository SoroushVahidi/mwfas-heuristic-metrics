"""Deterministic candidate graphs for EXP03 design smoke tests."""
from __future__ import annotations

import hashlib
import random
from statistics import mean, pstdev

import networkx as nx


def generate_candidate(family: str, n: int, seed: int) -> nx.DiGraph:
    if n < 4:
        raise ValueError("at least four vertices required")
    if family == "erdos_renyi_directed":
        graph = nx.gnp_random_graph(n, min(0.15, 4 / (n - 1)), seed=seed, directed=True)
    elif family == "directed_scale_free":
        source = nx.scale_free_graph(n, seed=seed)
        graph = nx.DiGraph(source)
        graph.remove_edges_from(nx.selfloop_edges(graph))
    elif family == "directed_community":
        left = n // 2
        sizes = [left, n - left]
        graph = nx.stochastic_block_model(sizes, [[0.22, 0.025], [0.025, 0.22]], seed=seed, directed=True)
        graph.remove_edges_from(nx.selfloop_edges(graph))
    else:
        raise ValueError(f"unknown generated family: {family}")
    rng = random.Random(seed)
    for u, v in sorted(graph.edges()):
        graph[u][v]["weight"] = rng.randint(1, 100)
    return graph


def structural_properties(graph: nx.DiGraph) -> dict:
    if not graph.is_directed():
        raise ValueError("directed graph required")
    weights = [data["weight"] for _, _, data in graph.edges(data=True)]
    if any(w < 0 for w in weights):
        raise ValueError("negative weight outside benchmark contract")
    arcs = sorted((str(u), str(v), float(data["weight"])) for u, v, data in graph.edges(data=True))
    digest = hashlib.sha256(repr(arcs).encode()).hexdigest()
    sccs = list(nx.strongly_connected_components(graph))
    return {"n_vertices": graph.number_of_nodes(), "n_edges": graph.number_of_edges(),
            "density": nx.density(graph), "scc_count": len(sccs),
            "largest_scc_size": max(map(len, sccs), default=0),
            "weight_min": min(weights, default=None), "weight_max": max(weights, default=None),
            "weight_mean": mean(weights) if weights else None,
            "weight_std": pstdev(weights) if weights else None, "graph_sha256": digest}
