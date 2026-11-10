"""Second parser for source-to-DIMACS identity; imports no preparation code."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

NORMALIZATION = {"directed": True, "node_labels": "1-based-integers", "parallel_edges": "absent",
                 "self_loops": "absent", "weight_type": "positive-integer"}
STATES = {1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20,
          21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
          37, 38, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 53, 54, 55, 56}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_edges(source: Path, parent: str) -> tuple[dict[tuple[str, str], int], int, int]:
    edge = defaultdict(int)
    loop = 0
    retained = 0
    if parent == "openflights":
        countries = {}
        with (source / "openflights-airports.dat").open(newline="") as stream:
            for row in csv.reader(stream):
                if row[0].isdigit():
                    countries[int(row[0])] = row[3]
        with (source / "openflights-routes.dat").open(newline="") as stream:
            for row in csv.reader(stream):
                if not row[3].isdigit() or not row[5].isdigit():
                    continue
                start, end = int(row[3]), int(row[5])
                if countries.get(start) != "United States" or countries.get(end) != "United States" or row[7] != "0":
                    continue
                if start == end:
                    loop += 1
                else:
                    edge[(f"airport:{start}", f"airport:{end}")] += 1
                    retained += 1
    elif parent == "census_lodes":
        with gzip.open(source / "de_od_main_JT00_2022.csv.gz", "rt", newline="") as stream:
            for row in csv.DictReader(stream):
                start, end = "tract:" + row["h_geocode"][:11], "tract:" + row["w_geocode"][:11]
                value = int(row["S000"])
                if not row["h_geocode"].startswith("10") or not row["w_geocode"].startswith("10") or value < 1:
                    raise ValueError("LODES source contract failed")
                if start == end:
                    loop += value
                else:
                    edge[start, end] += value
                    retained += 1
    elif parent == "irs_soi":
        with (source / "countyoutflow2122.csv").open(encoding="latin-1", newline="") as stream:
            for row in csv.DictReader(stream):
                start_state = int(row["y1_statefips"])
                end_state = int(row["y2_statefips"])
                start_county = int(row["y1_countyfips"])
                end_county = int(row["y2_countyfips"])
                if start_state not in STATES or end_state not in STATES or start_county < 1 or end_county < 1:
                    continue
                value = int(row["n1"])
                if value == -1:
                    continue  # IRS privacy suppression, not a negative migration weight.
                if value < 1:
                    raise ValueError("unexplained IRS nonpositive count")
                start = f"county:{start_state:02d}{start_county:03d}"
                end = f"county:{end_state:02d}{end_county:03d}"
                if start == end:
                    loop += value
                else:
                    edge[start, end] += value
                    retained += 1
    else:
        raise ValueError("unapproved source parent")
    return dict(edge), loop, retained


def dimacs(path: Path) -> tuple[int, list[tuple[int, int, int]]]:
    lines = path.read_text().splitlines()
    if not lines or len(lines[0].split()) != 4 or lines[0].split()[:2] != ["p", "graph"]:
        raise ValueError("malformed normalized header")
    n, m = map(int, lines[0].split()[2:])
    if n < 2 or m != len(lines) - 1:
        raise ValueError("normalized count mismatch")
    arcs = []
    for line in lines[1:]:
        cells = line.split()
        if len(cells) != 4 or cells[0] != "a":
            raise ValueError("malformed normalized arc")
        u, v, w = map(int, cells[1:])
        if not 1 <= u <= n or not 1 <= v <= n or u == v or w <= 0:
            raise ValueError("invalid normalized arc")
        arcs.append((u, v, w))
    if len({(u, v) for u, v, _ in arcs}) != m:
        raise ValueError("duplicate normalized arc")
    if {node for u, v, _ in arcs for node in (u, v)} != set(range(1, n + 1)):
        raise ValueError("normalized isolated vertex")
    return n, arcs


def review(selection: Path, source: Path, normalized: Path, destination: Path) -> dict:
    if destination.exists():
        raise ValueError("refusing to overwrite independent input review")
    frozen = json.loads(selection.read_text())
    if frozen["format"] != "exp13-frozen-selection-v1" or len(frozen["selected"]) != 3:
        raise ValueError("selection schema or count mismatch")
    reports = []
    for graph in frozen["selected"]:
        for item in graph["source_files"]:
            if sha(source / item["name"]) != item["sha256"]:
                raise ValueError("source bytes changed")
        graph_path = normalized / graph["graph_file"]
        map_path = normalized / graph["node_map_file"]
        if sha(graph_path) != graph["dimacs_sha256"] or sha(map_path) != graph["node_map_sha256"]:
            raise ValueError("normalized graph or map bytes changed")
        labels = json.loads(map_path.read_text())["external_labels_by_vertex"]
        n, arcs = dimacs(graph_path)
        if len(labels) != n or len(set(labels)) != n:
            raise ValueError("vertex map not bijective")
        original, loop, retained = raw_edges(source, graph["source_parent"])
        if Counter((labels[u - 1], labels[v - 1], w) for u, v, w in arcs) != Counter(
                (u, v, w) for (u, v), w in original.items()):
            raise ValueError("independent raw-to-normalized weighted-arc comparison failed")
        if loop != graph["original_loop_weight_constant"] or sum(w for _, _, w in arcs) != graph["total_weight"]:
            raise ValueError("weight or loop contribution changed")
        payload = {"format": "mwfas-exp03-graph-v1", "normalization": NORMALIZATION,
                   "vertices": list(range(1, n + 1)), "arcs": sorted(arcs)}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != graph["graph_sha256"] or n != graph["n"] or len(arcs) != graph["m"]:
            raise ValueError("canonical graph identity changed")
        label_index = {label: i for i, label in enumerate(labels)}
        for rank in (list(range(n)), list(reversed(range(n)))):
            normalized_objective = sum(w for u, v, w in arcs if rank[u - 1] >= rank[v - 1])
            original_objective = loop + sum(w for (u, v), w in original.items()
                                            if rank[label_index[u]] >= rank[label_index[v]])
            if original_objective != normalized_objective + loop:
                raise ValueError("objective-preserving aggregation failed")
        reports.append({"instance_id": graph["instance_id"], "source_parent": graph["source_parent"],
                        "graph_sha256": digest, "n": n, "m": len(arcs),
                        "retained_source_records": retained, "original_loop_weight_constant": loop,
                        "status": "PASS", "objective_relation_test_orderings": 2})
    if len({r["source_parent"] for r in reports}) != 3 or len({r["graph_sha256"] for r in reports}) != 3:
        raise ValueError("source parent or graph hashes duplicate")
    result = {"format": "exp13-independent-input-review-v1", "selection_sha256": sha(selection),
              "source_parents": 3, "graph_hashes": 3, "passed": 3, "records": reports}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("selection", "source", "normalized", "destination"):
        parser.add_argument("--" + name, type=Path, required=True)
    a = parser.parse_args()
    print(json.dumps(review(a.selection, a.source, a.normalized, a.destination), sort_keys=True))
