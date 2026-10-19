"""Independently verify released MWFAS graph/order witnesses and metadata."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict, deque
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def feed_label(h, label: str) -> None:
    value = label.encode("utf-8")
    h.update(len(value).to_bytes(8, "big"))
    h.update(value)


def read_graph(path: Path, expected: dict[str, str]):
    assert digest(path) == expected["serialized_sha256"], path
    arcs: Counter[tuple[str, str, int]] = Counter()
    vertices: set[str] = set()
    comments = []
    with path.open(encoding="utf-8", newline="") as stream:
        for line in stream:
            if line.startswith("c "):
                comments.append(line.rstrip("\r\n"))
                continue
            fields = line.rstrip("\r\n").split(" ")
            assert len(fields) == 5 and fields[0] == "a" and fields[4] == "1"
            u, v = fields[1:3]
            weight = int(fields[3])
            assert u and v and u != v and weight > 0
            assert not any(c.isspace() for c in u + v)
            arcs[(u, v, weight)] += 1
            vertices.update((u, v))
    assert comments[:2] == ["c Converted from Wikimedia clickstream TSV", "c keep_types=('link',) min_weight=5 skip_self_loops=True"]
    assert len(comments) == 3 and comments[2].startswith("c kept_arcs=")
    assert int(comments[2].split()[1].split("=")[1]) == sum(arcs.values())
    assert len(vertices) == int(expected["vertices"])
    assert sum(arcs.values()) == int(expected["arcs"])
    assert sum(weight * count for (_, _, weight), count in arcs.items()) == int(expected["total_weight"])
    assert int(expected["loop_constant"]) == 0
    graph_hash = hashlib.sha256(b"MWFAS-WIKIMEDIA-GRAPH-v1\n")
    pairs: Counter[tuple[str, str]] = Counter()
    for (u, v, weight), multiplicity in sorted(arcs.items()):
        feed_label(graph_hash, u)
        feed_label(graph_hash, v)
        graph_hash.update(f"{weight}:{multiplicity}\n".encode("ascii"))
        pairs[(u, v)] += multiplicity
    assert graph_hash.hexdigest() == expected["canonical_sha256"]
    topology_hash = hashlib.sha256(b"MWFAS-WIKIMEDIA-TOPOLOGY-v1\n")
    for (u, v), multiplicity in sorted(pairs.items()):
        feed_label(topology_hash, u)
        feed_label(topology_hash, v)
        topology_hash.update(f"{multiplicity}\n".encode("ascii"))
    assert topology_hash.hexdigest() == expected["topology_sha256"]
    vertex_hash = hashlib.sha256(b"MWFAS-WIKIMEDIA-VERTEX-MAP-v1\n")
    for index, label in enumerate(sorted(vertices)):
        vertex_hash.update(index.to_bytes(8, "big"))
        feed_label(vertex_hash, label)
    assert vertex_hash.hexdigest() == expected["vertex_map_sha256"]
    return arcs, vertices


def score_order(path: Path, expected: dict[str, str], arcs, vertices) -> None:
    assert digest(path) == expected["ordering_byte_sha256"], path
    positions: dict[str, int] = {}
    order: list[str | None] = [None] * len(vertices)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["Node ID", "Order"]
        for row in reader:
            assert None not in row and set(row) == {"Node ID", "Order"}
            label = row["Node ID"]
            rank = int(row["Order"])
            assert label in vertices and label not in positions
            assert 0 <= rank < len(vertices) and order[rank] is None
            order[rank] = label
            positions[label] = rank
    assert len(positions) == len(vertices) == int(expected["vertices"])
    assert all(label is not None for label in order)
    normalized = hashlib.sha256(b"MWFAS-WIKIMEDIA-ORDER-v1\n")
    for label in order:
        feed_label(normalized, label)
    assert normalized.hexdigest() == expected["ordering_normalized_sha256"]
    backward_weight = 0
    backward_arcs = 0
    indegree = {v: 0 for v in vertices}
    forward = defaultdict(list)
    for (u, v, weight), count in arcs.items():
        if positions[u] > positions[v]:
            backward_weight += weight * count
            backward_arcs += count
        else:
            indegree[v] += count
            forward[u].append((v, count))
    queue = deque(v for v, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        u = queue.popleft()
        visited += 1
        for v, count in forward[u]:
            indegree[v] -= count
            if indegree[v] == 0:
                queue.append(v)
    assert visited == len(vertices), "retained forward arcs are cyclic"
    assert backward_weight == int(expected["expected_objective_active"])
    assert backward_arcs == int(expected["expected_backward_arcs"])
    assert expected["status"] == "PASS" and expected["retained_dag"] == "True"
    assert expected["timing_status"] == "NOT_VERIFIABLE"


def verify_metadata(root: Path, witness_rows: list[dict[str, str]], graph_rows: list[dict[str, str]]) -> None:
    schema = json.loads((root / "metadata/schema.json").read_text())
    tables = {}
    for name, spec in schema["tables"].items():
        path = root / "metadata" / f"{name}.csv"
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames == spec["columns"], name
            data = list(reader)
        assert len(data) == spec["row_count"], name
        for field in spec["required"]:
            assert all(row[field] for row in data), (name, field)
        for row in data:
            for field in spec.get("sha256", []):
                assert not row[field] or (len(row[field]) == 64 and all(c in "0123456789abcdef" for c in row[field])), (name, field)
            for field in spec.get("integer", []):
                assert not row[field] or (row[field].isdigit() and int(row[field]) >= 0), (name, field)
            for field in spec.get("number", []):
                assert not row[field] or float(row[field]) >= 0, (name, field)
        for field in spec["unique"]:
            assert len({row[field] for row in data}) == len(data), (name, field)
        tables[name] = data
    for name, spec in schema["tables"].items():
        for field, target in spec.get("foreign_keys", {}).items():
            other, key = target.split(".")
            valid = {row[key] for row in tables[other]}
            assert all(not row[field] or row[field] in valid for row in tables[name]), (name, field)
    for qualified, choices in schema["enums"].items():
        name, field = qualified.split(".")
        assert all(row[field] in choices for row in tables[name]), qualified
    graph = {row["graph_id"]: row for row in tables["graphs"]}
    parents = {row["parent_id"]: row for row in tables["source_parents"]}
    artifacts = {row["artifact_id"]: row for row in tables["artifact_availability"]}
    assert len(graph) == 442
    assert len({(row["normalization_contract"], row["canonical_graph_sha256"]) for row in graph.values()}) == 442
    assert len({row["topology_sha256"] for row in graph.values() if row["cohort"] in ("EXP03", "EXP04", "EXP05", "EXP06")}) == 317
    assert len(parents) == 288 and len(artifacts) == 2607
    for row in graph.values():
        assert row["parent_id"] in parents
        assert artifacts[row["graph_artifact_id"]]["sha256"] == row["serialized_graph_sha256"]
        assert row["global_distinctness"] == "NOT_VERIFIABLE_ACROSS_CONTRACTS"
    for public_graph in graph_rows:
        record = graph[public_graph["graph_id"]]
        assert record["cohort"] == "EXP14_EXP15"
        assert record["serialized_graph_sha256"] == public_graph["serialized_sha256"]
        assert record["canonical_graph_sha256"] == public_graph["canonical_sha256"]
        assert record["parent_id"] == public_graph["source_parent"]
    outcomes = tables["run_outcomes"]
    assert len(outcomes) == 5254
    assert Counter(row["status"] for row in outcomes) == {"PASS": 4933, "CERTIFIED_OPTIMAL": 198, "TIMEOUT": 110, "FAIL": 11, "SKIPPED_DEPENDENCY": 2}
    by_id = {row["outcome_id"]: row for row in outcomes}
    for row in outcomes:
        g = graph[row["graph_id"]]
        feasible = row["status"] in ("PASS", "CERTIFIED_OPTIMAL")
        if feasible:
            assert row["objective_active"] and row["ordering_byte_sha256"]
            assert int(row["objective_original"]) == int(row["objective_active"]) + int(g["objective_loop_constant"])
            assert artifacts[row["ordering_artifact_id"]]["sha256"] == row["ordering_byte_sha256"]
        else:
            assert not row["objective_active"] and not row["objective_original"] and not row["ordering_byte_sha256"]
    assert {g["parent_id"]: int(g["objective_loop_constant"]) for g in graph.values() if g["cohort"] == "EXP13"} == {"openflights": 0, "census_lodes": 18628, "irs_soi": 124358925}
    for witness in witness_rows:
        row = by_id[witness["witness_id"]]
        assert row["graph_id"] == witness["graph_id"]
        assert row["ordering_byte_sha256"] == witness["ordering_byte_sha256"]
        assert row["ordering_sha256"] == witness["ordering_normalized_sha256"]
        assert row["objective_active"] == witness["expected_objective_active"]
        assert row["status"] == witness["status"]
    refs = tables["numerical_references"]
    assert len(refs) == 243 and Counter(row["reference_cohort"] for row in refs) == {"EXP06": 198, "EXP07": 45}
    assert Counter(row["certificate_class"] for row in refs if row["reference_cohort"] == "EXP07") == {"NUMERICAL_SOLVER_CERTIFIED": 20, "FEASIBLE_WITH_BOUND": 25}
    for row in refs:
        lower, upper = int(row["lower_bound"]), int(row["upper_bound"])
        assert lower <= upper and row["proof_class"] == "NOT_EXACT_ARITHMETIC"
        if row["certificate_class"] == "NUMERICAL_SOLVER_CERTIFIED":
            assert lower == upper == int(row["certified_optimum"])
        else:
            assert not row["certified_optimum"]
        if row["reference_cohort"] == "EXP07":
            assert graph[row["graph_id"]]["cohort"] in ("EXP03", "EXP04")
    assert len({row["graph_id"] for row in refs if row["reference_cohort"] == "EXP07"}) == 45
    # Reconstruct the manuscript inventory, empirical-summary, and reliability
    # table inputs from released rows. Other tables need frozen selection or
    # bootstrap contracts and, for byte-level checking, withheld witnesses.
    cohorts = Counter(row["cohort"] for row in graph.values())
    outcome_cohorts = Counter(row["cohort"] for row in outcomes)
    assert {c: cohorts[c] for c in ("EXP03", "EXP04", "EXP05", "EXP06", "EXP12", "EXP13", "EXP14_EXP15")} == {
        "EXP03": 45, "EXP04": 135, "EXP05": 38, "EXP06": 198,
        "EXP12": 20, "EXP13": 3, "EXP14_EXP15": 3,
    }
    assert {c: outcome_cohorts[c] for c in ("EXP03", "EXP04", "EXP05", "EXP06", "EXP12", "EXP13", "EXP14")} == {
        "EXP03": 900, "EXP04": 2025, "EXP05": 760, "EXP06": 1398,
        "EXP12": 140, "EXP13": 21, "EXP14": 10,
    }
    assert len({g["topology_sha256"] for g in graph.values() if g["cohort"] == "EXP06"}) == 99
    assert Counter(graph[r["graph_id"]]["cohort"] for r in refs if r["reference_cohort"] == "EXP07") == {"EXP03": 9, "EXP04": 36}
    assert Counter(row["status"] for row in outcomes if row["cohort"] == "EXP05") == {
        "PASS": 639, "FAIL": 11, "TIMEOUT": 108, "SKIPPED_DEPENDENCY": 2,
    }
    exp13 = [r for r in outcomes if r["cohort"] == "EXP13"]
    assert Counter(r["status"] for r in exp13) == {"PASS": 19, "TIMEOUT": 2}
    assert {parent: min(int(r["objective_active"]) for r in exp13 if graph[r["graph_id"]]["parent_id"] == parent and r["status"] == "PASS") for parent in ("openflights", "census_lodes", "irs_soi")} == {
        "openflights": 5099, "census_lodes": 65397, "irs_soi": 2770227,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_dir", type=Path, help="Downloaded MWFAS benchmark extension dataset root")
    args = parser.parse_args()
    root = args.dataset_dir
    checksums = rows(root / "CHECKSUMS.csv")
    for row in checksums:
        path = root / row["path"]
        assert path.is_file() and path.stat().st_size == int(row["size_bytes"])
        assert digest(path) == row["sha256"], path
    graph_rows = rows(root / "graph_inventory.csv")
    witness_rows = rows(root / "witnesses.csv")
    assert len(graph_rows) == 3 and len(witness_rows) == 10
    assert len({row["source_parent"] for row in graph_rows}) == 1
    assert len({row["serialized_sha256"] for row in graph_rows}) == 3
    assert len({row["ordering_byte_sha256"] for row in witness_rows}) == 10
    for graph_row in graph_rows:
        arcs, vertices = read_graph(root / graph_row["path"], graph_row)
        for witness in (row for row in witness_rows if row["graph_id"] == graph_row["graph_id"]):
            assert witness["source_parent"] == graph_row["source_parent"]
            score_order(root / witness["path"], witness, arcs, vertices)
    verify_metadata(root, witness_rows, graph_rows)
    print("PASS 3 graph bytes, 10 complete orders/objectives and retained DAGs; 5 metadata tables, 5,254 statuses, 243 numerical references; inventory, empirical, and reliability table inputs")


if __name__ == "__main__":
    main()
