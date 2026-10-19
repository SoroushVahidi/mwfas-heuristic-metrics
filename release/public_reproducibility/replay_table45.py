"""Public-only, standard-library reproduction of every frozen Table 4/5 cell.

The input is the extracted versioned public HF table45 package. No historical
absolute path in metadata is opened. This independently scores all saved orders;
it does not run an optimizer or claim exact-arithmetic solver certification.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
import random
import re
import statistics as st
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def read_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def digest_object(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def graph(path):
    n = m = None
    edges = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts or parts[0] == "c":
            continue
        if parts[0] == "p" and len(parts) == 4 and n is None:
            n, m = map(int, parts[2:])
            require(n > 0 and m >= 0, "invalid DIMACS size")
        elif parts[0] == "a" and len(parts) == 4 and n is not None:
            u, v, w = map(int, parts[1:])
            require(1 <= u <= n and 1 <= v <= n and u != v and w > 0, "invalid arc")
            edges.append((u, v, w))
        else:
            raise ValueError(f"malformed DIMACS: {path.name}")
    require(n is not None and len(edges) == m and len({(u, v) for u, v, _ in edges}) == m,
            "missing/duplicate DIMACS arcs")
    normalization = {"directed": True, "node_labels": "1-based-integers",
                     "parallel_edges": "absent", "self_loops": "absent", "weight_type": "positive-integer"}
    weighted = digest_object({"format": "mwfas-exp03-graph-v1", "normalization": normalization,
                              "vertices": list(range(1, n + 1)), "arcs": sorted(edges)})
    topology = digest_object({"format": "exp04-topology-v1", "directed": True,
                              "vertices": list(range(1, n + 1)), "arcs": sorted((u, v) for u, v, _ in edges)})
    return {"n": n, "m": m, "edges": edges, "total": sum(w for _, _, w in edges),
            "weighted": weighted, "topology": topology}


def objective(path, g):
    rows = read_csv(path)
    require(len(rows) == g["n"], f"incomplete ordering: {path.name}")
    nodes = [int(r["Node ID"]) for r in rows]
    ranks = [int(r["Order"]) for r in rows]
    require(sorted(nodes) == list(range(1, g["n"] + 1)) and sorted(ranks) == list(range(g["n"])),
            f"ordering is not a full permutation: {path.name}")
    position = dict(zip(nodes, ranks))
    cost = 0
    # Also independently check that retained forward arcs form a DAG.
    adjacency = [[] for _ in range(g["n"] + 1)]
    indegree = [0] * (g["n"] + 1)
    for u, v, w in g["edges"]:
        if position[u] > position[v]:
            cost += w
        else:
            adjacency[u].append(v)
            indegree[v] += 1
    ready = deque(v for v in nodes if indegree[v] == 0)
    visited = 0
    while ready:
        u = ready.popleft()
        visited += 1
        for v in adjacency[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                ready.append(v)
    require(visited == g["n"], "retained arcs are cyclic")
    return cost, [str(v) for v in sorted(nodes, key=position.get)]


def quantile(values, p):
    values = sorted(values)
    k = p * (len(values) - 1)
    low, high = int(k), math.ceil(k)
    return values[low] + (values[high] - values[low]) * (k - low)


def bootstrap(rows, cell_key, value_key):
    # Preserve original sorted graph/topology insertion order, including strata.
    cells = defaultdict(list)
    for row in rows:
        cells[cell_key(row)].append(row[value_key])
    rng = random.Random(20261017)
    draws = [st.median([rng.choice(cell) for cell in cells.values() for _ in cell])
             for _ in range(2000)]
    return quantile(draws, .025), quantile(draws, .975)


def compare_reference(actual, expected, fields, identity):
    for key in fields:
        a, e = actual[key], expected[key]
        if isinstance(a, (float, int)):
            require(e != "" and math.isclose(a, float(e), rel_tol=1e-12, abs_tol=1e-12),
                    f"original numerical summary mismatch {identity}/{key}: {a} != {e}")
        else:
            require(str(a) == e, f"original summary mismatch {identity}/{key}")


FAMILIES = {"Erd\\H{o}s--R\\'enyi": "erdos_renyi_directed", "Community": "directed_community",
            "Scale-free": "directed_scale_free", "Planted order": "planted_order"}


def displayed_cells(frozen, results):
    checks = []
    for table, latex in frozen["tables"].items():
        body = latex.split("\\midrule", 1)[1].split("\\bottomrule", 1)[0]
        rows = [line.strip().removesuffix("\\\\") for line in body.splitlines() if "&" in line]
        require(len(rows) == (3 if table == "4" else 4), f"frozen Table {table} row count")
        seen = set()
        for row in rows:
            fields = [x.strip() for x in row.split("&")]
            family = FAMILIES[fields[0]]
            require(family not in seen, "duplicate frozen family")
            seen.add(family)
            values = results[table][family]
            require(len(fields) == len(values) + 1, "displayed column count mismatch")
            checks.append({"table": table, "family": family, "column": 0,
                           "expected": fields[0], "actual": fields[0], "status": "PASS"})
            for column, (cell, actual) in enumerate(zip(fields[1:], values), 1):
                expected = re.findall(r"[+-]?\d+(?:\.\d+)?", cell)
                require(len(expected) == len(actual), f"cell arity {table}/{family}/{column}")
                rendered = []
                for token, value in zip(expected, actual):
                    precision = len(token.split(".")[1]) if "." in token else 0
                    formatted = format(value, f".{precision}f")
                    if token.startswith("+"):
                        formatted = "+" + formatted
                    # Zero and all integer counts must agree exactly, not round to zero.
                    valid = (value == float(token)) if precision == 0 else (formatted == token)
                    rendered.append(formatted)
                    require(valid, f"FAIL Table {table}/{family}/column {column}: {value} versus {token}")
                checks.append({"table": table, "family": family, "column": column,
                               "expected": cell, "actual": "/".join(rendered), "status": "PASS"})
        require(seen == set(results[table]), "unexpected/missing computed family")
    return checks


def replay(root, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = read_json(root / "manifest.json")
    expected_files = set()
    for entry in manifest["entries"]:
        path = root / entry["path"]
        require(path.resolve().is_relative_to(root.resolve()), "path escapes release")
        require(entry["path"] not in expected_files, "duplicate manifest path")
        expected_files.add(entry["path"])
        require(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"],
                f"file hash mismatch: {entry['path']}")
    require({str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} == expected_files | {"manifest.json"},
            "extra/missing package files")
    receipts = {(r["campaign"], r["run_id"]): r for r in read_csv(root / "prior_replay/run_replay_receipts.csv")}
    all_graphs, all_runs, objectives, status_rows, solver_rows = {}, {}, [], [], []
    topology_pairs = defaultdict(list)
    for exp, expected_graphs, expected_runs in (("04", 135, 2025), ("06", 198, 1398)):
        campaign = "EXP" + exp
        production = root / f"mwfas-exp{exp}/production-output"
        execution = root / f"execution/exp{exp}"
        selection_path = execution / f"data/manifests/exp{exp}_selection.json"
        selection = read_json(selection_path)
        run_manifest = read_json(production / "run_manifest.json")
        require(sha(selection_path) == run_manifest["selection_sha256"], "selection hash mismatch")
        require(sha(execution / f"configs/exp{exp}.json") == run_manifest["config_sha256"], "config hash mismatch")
        require(len(selection["instances"]) == expected_graphs, "graph inventory mismatch")
        graphs = {}
        for item in sorted(selection["instances"], key=lambda r: r["instance_id"]):
            iid = item["instance_id"]
            path = production / "graphs" / item["graph_file"]
            require(iid not in graphs and sha(path) == item["dimacs_sha256"], "graph file identity mismatch")
            g = graph(path)
            require((g["weighted"], g["topology"], g["n"], g["m"]) ==
                    (item["graph_sha256"], item["topology_sha256"], item["n_vertices"], item["n_edges"]),
                    "canonical graph/topology identity mismatch")
            if item.get("total_graph_weight") is not None:
                require(g["total"] == item["total_graph_weight"], "total weight mismatch")
            graphs[iid] = {**g, "design": item}
            if exp == "06":
                topology_pairs[g["topology"]].append(item)
        require({p.name for p in (production / "graphs").iterdir()} ==
                {r["graph_file"] for r in selection["instances"]}, "graph file-set mismatch")
        ids = run_manifest["expected_run_ids"]
        require(len(ids) == len(set(ids)) == expected_runs, "task identity count mismatch")
        require({p.stem for p in (production / "runs").glob("*.json")} == set(ids), "task file-set mismatch")
        records = defaultdict(list)
        order_ids = set()
        status = Counter()
        for rid in sorted(ids):
            p = production / "runs" / (rid + ".json")
            r = read_json(p)
            prior = receipts[(campaign, rid)]
            require(sha(p) == prior["run_sha256"] and r["status"] == prior["status"], "prior task receipt mismatch")
            require(r["run_id"] == rid and r["instance_id"] in graphs, "task graph association mismatch")
            g = graphs[r["instance_id"]]
            require(r["graph_sha256"] == g["weighted"] and r["topology_sha256"] == g["topology"], "task graph hash mismatch")
            for key in ("code_revision", "source_revision", "config_sha256"):
                require(r[key] == run_manifest[key], f"task provenance mismatch {key}")
            status[r["status"]] += 1
            status_rows.append({"campaign": campaign, "run_id": rid, "status": r["status"],
                                "algorithm": r["algorithm"], "seed": r.get("seed"),
                                "iteration_budget": r.get("iteration_budget"),
                                "total_wall_seconds": r.get("total_wall_seconds"),
                                "termination_reason": r.get("termination_reason")})
            order_file = production / "orders" / (rid + ".csv")
            if order_file.exists():
                order_ids.add(rid)
                require(sha(order_file) == r["order_sha256"] == prior["order_sha256"], "order hash mismatch")
                score, order = objective(order_file, g)
                require(score == r["objective_weight"] == float(prior["replayed_objective"]), f"objective mismatch {rid}")
                if r.get("normalized_objective") is not None:
                    require(math.isclose(score / g["total"], r["normalized_objective"], abs_tol=1e-8), "normalized objective mismatch")
                r = {**r, "recomputed": score}
                objectives.append({"campaign": campaign, "run_id": rid, "objective": score, "status": "PASS"})
                evidence = production / "solver_evidence" / (rid + ".json")
                if evidence.exists():
                    require(sha(evidence) == r["raw_evidence_sha256"], "solver evidence hash mismatch")
                    raw = read_json(evidence)
                    require(raw["order"] == order and raw["objective_weight"] == score, "solver saved-order mismatch")
                    if r["algorithm"] == "scipy_highs_ordering_milp":
                        require(r["status"] == raw["status"] == "CERTIFIED_OPTIMAL" and
                                r["solver_status_code"] == raw["solver_status_code"] == 0 and
                                0 <= r["solver_mip_gap"] <= 1e-7, "numerical solver termination mismatch")
                        for key in ("lower_bound", "objective_constant", "solver_fun", "solver_dual_bound", "solver_mip_gap"):
                            require(r[key] == raw[key], f"solver field mismatch {key}")
                        require(abs(score - r["lower_bound"]) < .5 and
                                abs(score - r["objective_constant"] - r["solver_fun"]) < 1e-5 and
                                abs(r["lower_bound"] - r["objective_constant"] - r["solver_dual_bound"]) < 1e-5,
                                "numerical objective/bound mismatch")
                    solver_rows.append({"run_id": rid, "algorithm": r["algorithm"], "objective": score,
                                        "status": "PASS", "qualification": "NUMERICAL_EVIDENCE_NOT_EXACT_PROOF"})
            else:
                require(r["status"] not in ("PASS", "CERTIFIED_OPTIMAL"), "missing successful order")
            records[r["instance_id"]].append(r)
        require({p.stem for p in (production / "orders").glob("*.csv")} == order_ids, "unaccounted saved orders")
        require(status == ({"PASS": 2025} if exp == "04" else {"PASS": 1200, "CERTIFIED_OPTIMAL": 198}),
                "original status/missingness counts differ")
        all_graphs[exp], all_runs[exp] = graphs, records
    require(len(topology_pairs) == 99, "EXP06 topology pair count")
    require(len(solver_rows) == 210 and Counter(r["algorithm"] for r in solver_rows) ==
            {"scipy_highs_ordering_milp": 198, "igraph_ip": 12}, "missing solver evidence records")
    for pair in topology_pairs.values():
        require(len(pair) == 2 and {x["weight_distribution"] for x in pair} == {"uniform_1_100", "capped_lognormal"},
                "EXP06 topology pairing mismatch")
        require(len({x["topology_id"] for x in pair}) == 1, "topology name identity mismatch")
    reference = root / "statistical_reference"
    ref_graph = {(r["campaign"], r["instance_id"]): r for r in read_csv(reference / "derived__refinement_by_graph.csv.gz")}
    ref_summary = {(r["campaign"], r["family"]): r for r in read_csv(reference / "derived__refinement_summary.csv")}
    ref_quality = {r["family"]: r for r in read_csv(reference / "wulver__quality_summary.csv")
                   if r["campaign"] == "EXP04" and r["comparator"] == "ipsns_b200_median3"}
    refinement = []
    for iid, g in all_graphs["04"].items():
        runs = all_runs["04"][iid]
        initials = [r for r in runs if r["algorithm"] in ("lrta", "wmsf_l2")]
        selected = [r for r in runs if r["algorithm"] == "ipsns" and r["iteration_budget"] == 200]
        require(len(initials) == 2 and {r["seed"] for r in selected} == {1, 2, 3} and len(selected) == 3,
                "EXP04 primary comparison design")
        require(all(r["status"] == "PASS" for r in initials + selected), "incomplete primary comparison")
        base = min(initials, key=lambda r: (r["recomputed"], r["total_wall_seconds"]))
        outcome = st.median(r["recomputed"] for r in selected)
        wall = st.median(r["total_wall_seconds"] for r in selected)
        delta = outcome - base["recomputed"]
        row = {"instance_id": iid, "family": g["design"]["family"], "n": g["n"],
               "degree": g["design"]["target_mean_out_degree"], "initializer": base["algorithm"],
               "initializer_objective": base["recomputed"], "ipsns_median_objective": outcome,
               "delta_div_total_weight": delta / g["total"],
               "baseline_relative_improvement": -delta / base["recomputed"],
               "initializer_wall_seconds": base["total_wall_seconds"], "ipsns_median_wall_seconds": wall,
               "wall_ratio_ipsns_over_initializer": wall / base["total_wall_seconds"],
               "strict_improvement": int(delta < 0), "tie": int(delta == 0), "loss": int(delta > 0)}
        compare_reference(row, ref_graph[("EXP04", iid)], [k for k in row if k not in ("n", "degree", "loss")], iid)
        refinement.append(row)
    table4 = {}
    summaries4 = []
    for family in sorted({r["family"] for r in refinement}):
        rows = [r for r in refinement if r["family"] == family]
        low, high = bootstrap(rows, lambda r: (r["n"], r["degree"]), "delta_div_total_weight")
        summary = {"family": family, "eligible_graphs": len(rows), "complete_graphs": len(rows),
                   "wins": sum(r["strict_improvement"] for r in rows), "ties": sum(r["tie"] for r in rows),
                   "losses": sum(r["loss"] for r in rows),
                   "median_delta_div_total_weight": st.median(r["delta_div_total_weight"] for r in rows),
                   "topology_bootstrap_ci_low": low, "topology_bootstrap_ci_high": high,
                   "median_baseline_relative_improvement": st.median(r["baseline_relative_improvement"] for r in rows),
                   "median_process_wall_ratio": st.median(r["wall_ratio_ipsns_over_initializer"] for r in rows)}
        compare_reference(summary, ref_quality[family], [k for k in summary if k not in
                          ("median_baseline_relative_improvement", "median_process_wall_ratio")], family)
        compare_reference(summary, ref_summary[("EXP04", family)],
                          ("median_baseline_relative_improvement", "median_process_wall_ratio"), family)
        summaries4.append(summary)
        table4[family] = [[len(rows), len(rows)], [summary[k] for k in ("wins", "ties", "losses")],
                          [summary["median_delta_div_total_weight"]], [low, high],
                          [100 * summary["median_baseline_relative_improvement"]], [summary["median_process_wall_ratio"]]]
    gaps = {}
    for iid, g in all_graphs["06"].items():
        records = all_runs["06"][iid]
        exact = [r for r in records if r["algorithm"] == "scipy_highs_ordering_milp"]
        require(len(exact) == 1, "missing exact task")
        optimum = exact[0]["recomputed"]
        require(optimum > 0, "undefined relative solver gap")
        for r in records:
            require(r["recomputed"] >= optimum, "objective below numerical reference")
            if r["algorithm"] == "igraph_ip":
                require(r["recomputed"] == optimum, "igraph IP cross-check differs")
        for method in ("lrta", "wmsf_l2", "igraph_eades_weighted", "ipsns"):
            rs = [r for r in records if r["algorithm"] == method]
            require(len(rs) == (3 if method == "ipsns" else 1), "EXP06 method count")
            if method == "ipsns":
                require({r["seed"] for r in rs} == {1, 2, 3}, "EXP06 stochastic seeds")
            h = st.median(r["recomputed"] for r in rs)
            gaps[(g["topology"], method, g["design"]["weight_distribution"])] = ((h - optimum) / optimum, iid)
    pairs = []
    for topology, method in sorted({(t, m) for t, m, _ in gaps}):
        uniform, ui = gaps[(topology, method, "uniform_1_100")]
        heavy, hi = gaps[(topology, method, "capped_lognormal")]
        d = all_graphs["06"][ui]["design"]
        pairs.append({"topology_sha256": topology, "family": d["family"], "algorithm": method,
                      "n": d["n_vertices"], "target_degree": d["target_mean_out_degree"],
                      "contamination_target": d.get("backward_contamination_target"),
                      "uniform_instance_id": ui, "capped_lognormal_instance_id": hi,
                      "uniform_relative_certified_gap": uniform, "capped_lognormal_relative_certified_gap": heavy,
                      "heavy_minus_uniform_gap": heavy - uniform})
    ref_pairs = {(r["topology_sha256"], r["algorithm"]): r for r in read_csv(reference / "derived__exp06_weight_pairs.csv")}
    require(len(pairs) == len(ref_pairs) == 396, "EXP06 paired method count")
    for r in pairs:
        compare_reference(r, ref_pairs[(r["topology_sha256"], r["algorithm"])],
                          [k for k in r if k != "contamination_target"], r["topology_sha256"])
    table5, summaries5 = {}, []
    ref_weights = {(r["family"], r["algorithm"]): r for r in read_csv(reference / "derived__exp06_weight_summary.csv")}
    for family, method in sorted({(r["family"], r["algorithm"]) for r in pairs}):
        rows = [r for r in pairs if (r["family"], r["algorithm"]) == (family, method)]
        cell = lambda r: (r["n"], r["target_degree"], r["contamination_target"])
        low, high = bootstrap(rows, cell, "heavy_minus_uniform_gap")
        values = [r["heavy_minus_uniform_gap"] for r in rows]
        summary = {"family": family, "algorithm": method, "paired_topologies": len(rows),
                   "matched_design_cells": len({cell(r) for r in rows}),
                   "median_heavy_minus_uniform_relative_gap": st.median(values),
                   "heavy_higher_gap": sum(x > 0 for x in values), "equal_gap": sum(x == 0 for x in values),
                   "heavy_lower_gap": sum(x < 0 for x in values),
                   "stratified_topology_bootstrap_low": low, "stratified_topology_bootstrap_high": high}
        compare_reference(summary, ref_weights[(family, method)], list(summary), f"{family}/{method}")
        summaries5.append(summary)
        if method == "igraph_eades_weighted":
            table5[family] = [[len(rows)], [summary[k] for k in ("heavy_higher_gap", "equal_gap", "heavy_lower_gap")],
                              [st.median(values)], [low, high]]
    cells = displayed_cells(read_json(root / "frozen_tables.json"), {"4": table4, "5": table5})
    for name, rows in (("objectives", objectives), ("task_statuses", status_rows), ("solver_evidence", solver_rows),
                       ("exp04_refinement", refinement), ("exp04_summary", summaries4),
                       ("exp06_weight_pairs", pairs), ("exp06_weight_summary", summaries5), ("displayed_cells", cells)):
        write_csv(output / (name + ".csv"), rows)
    report = {"status": "PASS", "tables": {"4": "PUBLIC_REPLAYABLE", "5": "PUBLIC_REPLAYABLE"},
              "displayed_cells": len(cells), "numeric_displayed_cells": sum(r["column"] > 0 for r in cells),
              "graphs": 333, "orders": len(objectives), "tasks": len(status_rows),
              "exp06_topology_pairs": len(topology_pairs), "solver_evidence_records": len(solver_rows),
              "original_statuses": {exp: dict(Counter(r["status"] for r in status_rows if r["campaign"] == exp))
                                    for exp in ("EXP04", "EXP06")},
              "bootstrap_seed": 20261017, "bootstrap_replicates": 2000, "python": sys.version,
              "platform": platform.platform(), "processor": platform.processor(),
              "package_manifest_sha256": sha(root / "manifest.json"),
              "verifier_sha256": sha(Path(__file__)), "optimization_rerun": False,
              "solver_qualification": "Numerical status/bound consistency, not exact mathematical proof"}
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        replay(args.package, args.output)
    except Exception as error:
        if args.output.is_dir():
            (args.output / "failure.json").write_text(json.dumps({"status": "FAIL", "error": str(error)}) + "\n")
        raise
