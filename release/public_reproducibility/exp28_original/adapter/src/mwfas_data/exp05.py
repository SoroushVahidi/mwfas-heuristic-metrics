"""Pinned external-source normalization and selection for EXP05."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import statistics
import zipfile
from collections import Counter
from pathlib import Path

import networkx as nx

from .config import ROOT
from .exp03 import atomic_json, sha256_file, write_parquet_atomic
from .exp04 import topology_sha256
from .generation import canonical_graph_sha256, write_dimacs

CONFIG_PATH = ROOT / "configs/exp05.json"
SOURCE_MANIFEST_PATH = ROOT / "data/manifests/exp05_sources.json"
SELECTION_PATH = ROOT / "data/manifests/exp05_selection.json"


def config() -> dict:
    value = json.loads(CONFIG_PATH.read_text())
    if value["status"] not in {"PILOT_PROTOCOL", "FROZEN_PRIMARY_DESIGN"}:
        raise ValueError("unrecognized EXP05 protocol status")
    return value


def source_manifest() -> dict:
    return json.loads(SOURCE_MANIFEST_PATH.read_text())


def verify_sources(source_dir: Path) -> dict:
    manifest = source_manifest()
    for item in manifest["sources"]:
        path = source_dir / item["local_filename"]
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"source SHA-256 mismatch: {item['source_id']}")
    return manifest


def _graph_from_events(events: list[tuple[int, int, int]], *, counts: bool,
                       vertices: set[int] | None = None) -> tuple[nx.DiGraph, int]:
    original_nodes = set(vertices) if vertices is not None else {v for u, w, _ in events for v in (u, w)}
    graph = nx.DiGraph()
    graph.add_nodes_from(original_nodes)
    loop_weight = 0
    for u, v, _ in events:
        if u not in original_nodes or v not in original_nodes:
            continue
        if u == v:
            loop_weight += 1
            continue
        if graph.has_edge(u, v):
            if counts:
                graph[u][v]["weight"] += 1
        else:
            graph.add_edge(u, v, weight=1)
    return graph, loop_weight


def _read_events(path: Path, temporal: bool) -> list[tuple[int, int, int]]:
    result = []
    with gzip.open(path, "rt") as stream:
        for line in stream:
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split()
            if len(fields) != (3 if temporal else 2):
                raise ValueError(f"malformed source edge in {path.name}")
            u, v = int(fields[0]), int(fields[1])
            timestamp = int(fields[2]) if temporal else 0
            result.append((u, v, timestamp))
    return result


def _largest_cyclic_scc(graph: nx.DiGraph) -> set[int]:
    candidates = [set(component) for component in nx.strongly_connected_components(graph)
                  if len(component) > 1]
    if not candidates:
        raise ValueError("source has no nontrivial SCC")
    return min(candidates, key=lambda x: (-len(x), tuple(sorted(x))))


def sparse_specs(source_dir: Path) -> list[tuple[str, nx.DiGraph, dict]]:
    email = _read_events(source_dir / "email-Eu-core.txt.gz", temporal=False)
    college = _read_events(source_dir / "CollegeMsg.txt.gz", temporal=True)
    wiki = _read_events(source_dir / "wiki-Vote.txt.gz", temporal=False)
    email_full, email_loops = _graph_from_events(email, counts=False)
    college_full, _ = _graph_from_events(college, counts=True)
    wiki_full, _ = _graph_from_events(wiki, counts=False)
    email_scc = _largest_cyclic_scc(email_full)
    college_scc = _largest_cyclic_scc(college_full)
    wiki_scc = _largest_cyclic_scc(wiki_full)
    t0 = min(t for _, _, t in college)
    windows = {}
    for days in (30, 90):
        selected = [(u, v, t) for u, v, t in college if t <= t0 + days * 86400]
        windows[days] = _graph_from_events(selected, counts=True)[0]
    source_meta = {
        "email": ("snap_email_eu_core", "unit", "email_eu_core"),
        "college": ("snap_college_msg", "observed_message_count", "college_msg"),
        "wiki": ("snap_wiki_vote", "unit", "wiki_vote")}
    cases = [
        ("email_full", email_full, "email", "full", email_loops),
        ("email_largest_scc", email_full.subgraph(email_scc).copy(), "email", "largest_nontrivial_scc", sum(u == v and u in email_scc for u, v, _ in email)),
        ("college_full_count", college_full, "college", "full", 0),
        ("college_largest_scc_count", college_full.subgraph(college_scc).copy(), "college", "largest_nontrivial_scc", 0),
        ("college_first_30_days_count", windows[30], "college", "events_through_first_30_days_inclusive", 0),
        ("college_first_90_days_count", windows[90], "college", "events_through_first_90_days_inclusive", 0),
        ("wiki_vote_full_reference", wiki_full, "wiki", "full", 0),
        ("wiki_vote_largest_scc_reference", wiki_full.subgraph(wiki_scc).copy(), "wiki", "largest_nontrivial_scc", 0)]
    result = []
    for name, graph, family, transformation, loop_weight in cases:
        source_id, semantics, parent = source_meta[family]
        result.append((f"exp05_{name}", graph, {
            "source_id": source_id, "source_parent": parent,
            "source_category": "sparse_real_network", "weight_semantics": semantics,
            "transformation": transformation,
            "excluded_self_loop_weight": loop_weight,
            "already_in_historical_dataset": family == "wiki",
            "source_member": None, "source_member_sha256": None}))
    if [name.removeprefix("exp05_") for name, _, _ in result] != config()["sparse_selection"]:
        raise ValueError("sparse selection differs from protocol")
    return result


def _read_matrix(archive: zipfile.ZipFile, member: str) -> tuple[nx.DiGraph, dict]:
    content = archive.read(member)
    words = content.split()
    n = int(words[0])
    if len(words) != n * n + 1:
        raise ValueError(f"matrix dimensions disagree: {member}")
    weights = [int(value) for value in words[1:]]
    if any(weight < 0 for weight in weights):
        raise ValueError(f"negative EXIOBASE weight; no clipping allowed: {member}")
    graph = nx.DiGraph()
    graph.add_nodes_from(range(1, n + 1))
    diagonal = 0
    zero_offdiagonal = 0
    for i in range(n):
        for j in range(n):
            weight = weights[i * n + j]
            if i == j:
                diagonal += weight
            elif weight:
                graph.add_edge(i + 1, j + 1, weight=weight)
            else:
                zero_offdiagonal += 1
    return graph, {"source_member": member,
                   "source_member_sha256": hashlib.sha256(content).hexdigest(),
                   "excluded_self_loop_weight": diagonal,
                   "omitted_zero_offdiagonal_entries": zero_offdiagonal,
                   "matrix_total_offdiagonal_weight": sum(weights) - diagonal}


def matrix_specs(source_dir: Path) -> list[tuple[str, nx.DiGraph, dict]]:
    cfg = config()["matrix_selection"]
    result = []
    with zipfile.ZipFile(source_dir / "exiobase.zip") as archive:
        members = set(archive.namelist())
        labels = [(f"rxr_{year}", f"exiobase/rxr/rxr_{year}_n49", "rxr", str(year))
                  for year in cfg["rxr_years"]]
        for country in cfg["countries"]:
            for family in ("isic", "pxp"):
                prefix = f"exiobase/{family}/{family}_{country}_2022_n"
                matches = sorted(name for name in members if name.startswith(prefix))
                if len(matches) != 1:
                    raise ValueError(f"expected exactly one EXIOBASE member: {prefix}")
                labels.append((f"{family}_{country}_2022", matches[0], family, country))
        for country in cfg["os300_countries"]:
            labels.append((f"os300_{country}_2022", f"exiobase/os300/os300_{country}_2022_n300", "os300", country))
        for label, member, family, source_group in labels:
            if member not in members:
                raise ValueError(f"missing source archive member: {member}")
            graph, matrix_meta = _read_matrix(archive, member)
            result.append((f"exp05_{label}", graph, matrix_meta | {
                "source_id": "exiobase_lop_v001", "source_parent": "exiobase_lop_benchmark",
                "source_category": "dense_lop_matrix", "matrix_family": family,
                "source_group": source_group, "weight_semantics": "published_integer_economic_LOP_matrix",
                "transformation": "positive_offdiagonal_entries_to_arcs; zero_entries_omitted; diagonal_excluded",
                "already_in_historical_dataset": False}))
    return result


def _cv(values) -> float:
    values = list(values)
    avg = statistics.mean(values) if values else 0
    return statistics.pstdev(values) / avg if avg else 0.0


def _normalize(name: str, graph: nx.DiGraph, meta: dict, workdir: Path,
               source_by_id: dict[str, dict], config_hash: str) -> dict:
    if graph.number_of_nodes() == 0 or any(u == v for u, v in graph.edges()):
        raise ValueError(f"empty graph or unremoved self loop: {name}")
    original_nodes = sorted(int(v) for v in graph.nodes())
    mapping = {node: rank for rank, node in enumerate(original_nodes, start=1)}
    normalized = nx.relabel_nodes(graph, mapping, copy=True)
    if any(not isinstance(d["weight"], int) or d["weight"] <= 0 or not math.isfinite(d["weight"])
           for _, _, d in normalized.edges(data=True)):
        raise ValueError(f"nonpositive or invalid edge weight: {name}")
    graph_path = workdir / "graphs" / f"{name}.d"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    if graph_path.exists():
        original_sha = sha256_file(graph_path)
        write_dimacs(normalized, graph_path.with_suffix(".d.verify"))
        candidate_sha = sha256_file(graph_path.with_suffix(".d.verify"))
        graph_path.with_suffix(".d.verify").unlink()
        if original_sha != candidate_sha:
            raise ValueError(f"existing normalized graph differs: {graph_path}")
    else:
        write_dimacs(normalized, graph_path)
    map_path = workdir / "node_maps" / f"{name}.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_bytes = (json.dumps(original_nodes, separators=(",", ":")) + "\n").encode()
    if map_path.exists() and map_path.read_bytes() != map_bytes:
        raise ValueError(f"existing node map differs: {map_path}")
    if not map_path.exists():
        map_path.write_bytes(map_bytes)
    sccs = list(nx.strongly_connected_components(normalized))
    weights = [d["weight"] for _, _, d in normalized.edges(data=True)]
    source = source_by_id[meta["source_id"]]
    return {"instance_id": name, "graph_file": graph_path.name,
            "dimacs_sha256": sha256_file(graph_path),
            "node_map_file": map_path.name, "node_map_sha256": sha256_file(map_path),
            "graph_sha256": canonical_graph_sha256(normalized),
            "topology_sha256": topology_sha256(normalized),
            "n_vertices": normalized.number_of_nodes(), "n_edges": normalized.number_of_edges(),
            "density": nx.density(normalized),
            "scc_count": len(sccs), "cyclic_scc_count": sum(len(c) > 1 for c in sccs),
            "largest_scc_size": max(map(len, sccs)),
            "in_degree_cv": _cv(normalized.in_degree(v) for v in normalized),
            "out_degree_cv": _cv(normalized.out_degree(v) for v in normalized),
            "weight_min": min(weights), "weight_max": max(weights),
            "weight_mean": statistics.mean(weights), "total_graph_weight": sum(weights),
            "source_sha256": source["sha256"], "source_url": source["source_url"],
            "source_version": source["version"],
            "config_sha256": config_hash} | meta


def prepare(source_dir: Path, workdir: Path, *, freeze: bool = False) -> dict:
    sources = verify_sources(source_dir)
    cfg = config()
    config_hash = sha256_file(CONFIG_PATH)
    source_by_id = {s["source_id"]: s for s in sources["sources"]}
    specs = sparse_specs(source_dir) + matrix_specs(source_dir)
    rows = [_normalize(name, graph, meta, workdir, source_by_id, config_hash)
            for name, graph, meta in specs]
    if len(rows) != 38 or len({row["graph_sha256"] for row in rows}) != len(rows):
        raise ValueError("EXP05 count or weighted graph identity collision")
    selection = {"format": "mwfas-exp05-selection-v1", "config_sha256": config_hash,
                 "source_manifest_sha256": sha256_file(SOURCE_MANIFEST_PATH),
                 "source_revision": cfg["source_revision"],
                 "dataset_revision": cfg["dataset_revision"], "instances": rows}
    local_path = workdir / "selection.json"
    if local_path.exists() and json.loads(local_path.read_text()) != selection:
        raise ValueError("existing workdir selection differs from current protocol")
    if not local_path.exists():
        atomic_json(local_path, selection)
    if SELECTION_PATH.exists() and json.loads(SELECTION_PATH.read_text()) != selection:
        raise ValueError("frozen selection differs from generated graphs")
    if freeze:
        if cfg["status"] != "FROZEN_PRIMARY_DESIGN":
            raise ValueError("freeze requires final protocol status")
        if not SELECTION_PATH.exists():
            atomic_json(SELECTION_PATH, selection)
    atomic_json(workdir / "source_manifest.json", sources)
    atomic_json(workdir / "license_and_provenance_report.json",
                {"status": "PASS", "sources": sources["sources"],
                 "excluded": sources["investigated_not_selected"]})
    write_parquet_atomic(workdir / "instances.parquet", rows)
    write_parquet_atomic(workdir / "graph_properties.parquet", rows)
    return selection


def expected_tasks(selection: dict, cfg: dict | None = None) -> list[dict]:
    cfg = cfg or config()
    tasks = []
    for instance in selection["instances"]:
        iid = instance["instance_id"]
        for algorithm in cfg["algorithms"]:
            if algorithm == "ipsns":
                for budget in cfg["ipsns_iteration_budgets"]:
                    for seed in cfg["ipsns_seeds"]:
                        tasks.append({"run_id": f"{iid}__ipsns_b{budget:03d}_s{seed}",
                                      "instance_id": iid, "algorithm": algorithm,
                                      "budget": budget, "seed": seed})
            else:
                tasks.append({"run_id": f"{iid}__{algorithm}", "instance_id": iid,
                              "algorithm": algorithm, "budget": None, "seed": None})
    if len(tasks) != 760 or len({t["run_id"] for t in tasks}) != len(tasks):
        raise ValueError("EXP05 expected task count or duplicate ID")
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    result = prepare(args.source_dir, args.workdir, freeze=args.freeze)
    print(json.dumps({"instances": len(result["instances"]),
                      "tasks": len(expected_tasks(result)),
                      "selection_sha256": sha256_file(args.workdir / "selection.json")}))


if __name__ == "__main__":
    main()
