"""Deterministic, size/degree-balanced EXP03 graph generation and identity."""
from __future__ import annotations

import hashlib
import json
import random
from statistics import mean, pstdev

import networkx as nx

FAMILIES = ("erdos_renyi_directed", "directed_scale_free", "directed_community")
NORMALIZATION = {"directed": True, "node_labels": "1-based-integers", "parallel_edges": "absent",
                 "self_loops": "absent", "weight_type": "positive-integer"}


def _ensure_edge_count(graph: nx.DiGraph, target: int, rng: random.Random, family: str) -> None:
    while graph.number_of_edges() > target:
        candidates = [(u, v) for u, v in graph.edges()
                      if graph.degree(u) > 1 and graph.degree(v) > 1]
        if not candidates:
            raise ValueError("cannot trim graph without isolating vertices")
        graph.remove_edge(*candidates[rng.randrange(len(candidates))])
    vertices = sorted(graph.nodes())
    while graph.number_of_edges() < target:
        if family == "directed_scale_free":
            out_weights = [graph.out_degree(v) + 1 for v in vertices]
            in_weights = [graph.in_degree(v) + 1 for v in vertices]
            u = rng.choices(vertices, weights=out_weights, k=1)[0]
            v = rng.choices(vertices, weights=in_weights, k=1)[0]
        elif family == "directed_community":
            u = rng.choice(vertices)
            same = rng.random() < 0.8
            pool = [v for v in vertices if (v <= len(vertices) // 2) == (u <= len(vertices) // 2)] if same else vertices
            v = rng.choice(pool)
        else:
            u, v = rng.sample(vertices, 2)
        if u != v and not graph.has_edge(u, v):
            graph.add_edge(u, v)
    for u in vertices:
        if graph.degree(u):
            continue
        target_node = vertices[(vertices.index(u) + 1) % len(vertices)]
        replacement = next(((a, b) for a, b in sorted(graph.edges())
                            if graph.degree(a) > 1 and graph.degree(b) > 1
                            and (u, target_node) != (a, b)), None)
        if replacement is None:
            raise ValueError("cannot repair isolated vertex")
        graph.remove_edge(*replacement)
        graph.add_edge(u, target_node)


def generate_candidate(family: str, n: int, seed: int, avg_out_degree: int = 4,
                       weight_seed: int | None = None) -> nx.DiGraph:
    if family not in FAMILIES or n < 4 or not 1 <= avg_out_degree < n - 1:
        raise ValueError("invalid family, size, or mean out-degree")
    target = n * avg_out_degree
    rng = random.Random(seed)
    if family == "erdos_renyi_directed":
        graph = nx.gnm_random_graph(n, target, seed=seed, directed=True)
    elif family == "directed_scale_free":
        graph = nx.DiGraph(nx.scale_free_graph(n, seed=seed))
        graph.remove_edges_from(nx.selfloop_edges(graph))
    else:
        half = n // 2
        within = min(0.95, 1.6 * avg_out_degree / n)
        between = min(0.95, 0.4 * avg_out_degree / n)
        graph = nx.stochastic_block_model([half, n - half],
                                          [[within, between], [between, within]],
                                          seed=seed, directed=True)
        graph.remove_edges_from(nx.selfloop_edges(graph))
    graph = nx.relabel_nodes(graph, {u: u + 1 for u in range(n)}, copy=True)
    graph.add_nodes_from(range(1, n + 1))
    _ensure_edge_count(graph, target, rng, family)
    weights = random.Random(weight_seed if weight_seed is not None else seed ^ 0x5A17)
    for u, v in sorted(graph.edges()):
        graph[u][v]["weight"] = weights.randint(1, 100)
    return graph


def canonical_graph_bytes(graph: nx.DiGraph) -> bytes:
    if not graph.is_directed() or isinstance(graph, nx.MultiDiGraph):
        raise ValueError("simple directed graph required")
    vertices = sorted(int(v) for v in graph.nodes())
    arcs = sorted((int(u), int(v), graph[u][v]["weight"]) for u, v in graph.edges())
    if any(u == v or not isinstance(w, int) or w <= 0 for u, v, w in arcs):
        raise ValueError("self-loop or nonpositive/noninteger weight")
    payload = {"format": "mwfas-exp03-graph-v1", "normalization": NORMALIZATION,
               "vertices": vertices, "arcs": arcs}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def canonical_graph_sha256(graph: nx.DiGraph) -> str:
    return hashlib.sha256(canonical_graph_bytes(graph)).hexdigest()


def structural_properties(graph: nx.DiGraph) -> dict:
    canonical_graph_bytes(graph)  # validate contract
    weights = [graph[u][v]["weight"] for u, v in graph.edges()]
    sccs = list(nx.strongly_connected_components(graph))
    return {"n_vertices": graph.number_of_nodes(), "n_edges": graph.number_of_edges(),
            "density": nx.density(graph), "scc_count": len(sccs),
            "largest_scc_size": max(map(len, sccs), default=0),
            "weight_min": min(weights, default=None), "weight_max": max(weights, default=None),
            "weight_mean": mean(weights) if weights else None,
            "weight_std": pstdev(weights) if weights else None,
            "isolated_vertices": sum(graph.degree(v) == 0 for v in graph.nodes()),
            "graph_sha256": canonical_graph_sha256(graph)}


def write_dimacs(graph: nx.DiGraph, path) -> None:
    n = graph.number_of_nodes()
    if sorted(graph.nodes()) != list(range(1, n + 1)):
        raise ValueError("DIMACS writer requires vertices 1..n")
    lines = ["c generated by mwfas_data.generation", f"p sp {n} {graph.number_of_edges()}"]
    lines.extend(f"a {u} {v} {graph[u][v]['weight']}" for u, v in sorted(graph.edges()))
    path.write_text("\n".join(lines) + "\n")
