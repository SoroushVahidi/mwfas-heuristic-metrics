"""Build/verify a metadata-only, post-hoc EXP10–EXP05 comparison package.

The verifier independently joins source snapshots, preserves original task
statuses, and recomputes every reported objective difference. The separate
cross_campaign_raw_review.py handles private source-byte verification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


IDS = ("exp05_college_full_count", "exp05_email_full", "exp05_wiki_vote_full_reference")
BUDGETS = (1, 3, 10, 50, 200)
FILES = {"exp05_graphs.csv": "benchmark_inventory.csv",
         "exp05_original_tasks.csv": "original_inventory.csv",
         "exp05_derived_endpoints.csv": "derived_inventory.csv",
         "exp10_graphs.csv": "inputs.csv",
         "exp10_selected_tasks.csv": "task_audit_inventory.csv"}
IDENTITY_COLUMNS = ["instance_id", "source_parent", "weight_semantics", "vertices", "directed_arcs",
                    "total_arc_weight", "excluded_self_loop_weight", "source_sha256",
                    "exp05_graph_sha256", "exp10_graph_sha256", "dimacs_sha256", "topology_sha256"]
SEED_COLUMNS = ["instance_id", "seed", "exp05_best_run_id", "exp05_best_provenance",
                "exp05_original_status", "exp05_best_objective", "xiong_objective",
                "improvement_weight", "improvement_over_total_arc_weight",
                "improvement_over_exp05_objective", "comparison", "xiong_process_wall_seconds",
                "exp05_comparator_process_wall_seconds", "exp05_comparator_initialization_inclusive_seconds"]
GRAPH_COLUMNS = ["instance_id", "source_parent", "total_arc_weight", "exp05_best_objective",
                 "exp05_best_run_id", "exp05_best_provenance", "xiong_seed1_objective",
                 "xiong_seed2_objective", "xiong_best_objective", "xiong_seed_span",
                 "best_xiong_improvement_weight", "best_xiong_improvement_over_total_arc_weight",
                 "best_xiong_improvement_over_exp05_objective", "xiong_strict_wins", "ties", "losses"]
IPSNS_COLUMNS = ["instance_id", "iteration_budget", "seeds", "original_pass", "original_fail",
                 "original_timeout", "derived_pass", "original_seed_statuses",
                 "original_seed_process_wall_seconds", "original_seed_objectives",
                 "derived_seed_objectives", "best_validated_objective", "best_endpoint_type"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path: Path) -> dict:
    return json.loads(path.read_text())


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def csv_data(rows: list[dict], fields: list[str]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def json_data(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def select(source: Path, destination_name: str) -> tuple[list[dict], list[str]]:
    with source.open(newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        records = list(reader)
    if destination_name == "exp05_derived_endpoints.csv":
        records = [r for r in records if any(r["run_id"].startswith(i + "__") for i in IDS)]
    else:
        records = [r for r in records if r["instance_id"] in IDS]
    return records, fields


def source_checksums(folder: Path) -> None:
    checksums = (folder / "checksums.sha256").read_text().splitlines()
    for line in checksums:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        assert match, line
        assert sha(folder / match[2]) == match[1], match[2]


def derive(data: dict[str, list[dict]], raw: dict) -> tuple[dict[str, bytes], dict]:
    g05 = {r["instance_id"]: r for r in data["exp05_graphs.csv"]}
    g10 = {r["instance_id"]: r for r in data["exp10_graphs.csv"]}
    originals = data["exp05_original_tasks.csv"]
    derived = data["exp05_derived_endpoints.csv"]
    tasks10 = data["exp10_selected_tasks.csv"]
    assert set(g05) == set(g10) == set(IDS) and len(originals) == 60 and len(derived) == 13 and len(tasks10) == 12
    orig_by_id = {r["run_id"]: r for r in originals}
    derived_by_id = {r["run_id"]: r for r in derived}
    task_by_key = {(r["instance_id"], r["algorithm"], int(r["seed"])): r for r in tasks10}
    assert len(orig_by_id) == 60 and len(derived_by_id) == 13 and len(task_by_key) == 12
    assert all(r["verification"] == "PASS" for r in originals)
    assert all(r["validation"] == "PASS" and r["derived_status"] == "PASS" for r in derived)
    identity, seed_rows, graph_rows, ipsns_rows = [], [], [], []
    total_original_status = Counter()
    total_derived_kind = Counter()
    for iid in IDS:
        a, b, checked = g05[iid], g10[iid], raw["graph_details"][iid]
        assert a["graph_sha256"] == b["graph_sha256"] == checked["weighted_graph_sha256"]
        assert a["dimacs_sha256"] == b["dimacs_sha256"] == checked["dimacs_sha256"]
        assert a["topology_sha256"] == b["topology_sha256"] == checked["topology_sha256"]
        assert a["source_sha256"] == b["source_sha256"] == checked["source_sha256"]
        assert a["source_parent"] == b["source_parent"] == checked["source_parent"]
        assert int(a["n"]) == int(b["n"]) == checked["vertices"]
        assert int(a["m"]) == int(b["m"]) == checked["directed_arcs"]
        assert int(a["total_weight"]) == int(b["total_weight"]) == checked["total_arc_weight"]
        assert int(a["excluded_self_loop_weight"]) == checked["excluded_self_loop_weight"]
        assert a["weight_semantics"] == checked["weight_semantics"]
        identity.append({"instance_id": iid, "source_parent": a["source_parent"],
                         "weight_semantics": a["weight_semantics"], "vertices": a["n"],
                         "directed_arcs": a["m"], "total_arc_weight": a["total_weight"],
                         "excluded_self_loop_weight": a["excluded_self_loop_weight"],
                         "source_sha256": a["source_sha256"], "exp05_graph_sha256": a["graph_sha256"],
                         "exp10_graph_sha256": b["graph_sha256"], "dimacs_sha256": a["dimacs_sha256"],
                         "topology_sha256": a["topology_sha256"]})
        group = [r for r in originals if r["instance_id"] == iid]
        assert len(group) == 20
        for r in group:
            total_original_status[r["original_status"]] += 1
            if r["original_status"] == "PASS":
                assert r["objective_weight"] and r["order_sha256"]
            else:
                assert not r["objective_weight"] and not r["order_sha256"]
        cases = []
        for r in group:
            if r["original_status"] == "PASS":
                cases.append((int(r["objective_weight"]), r["run_id"], "original_PASS", r))
        for r in derived:
            if r["run_id"].startswith(iid + "__"):
                assert r["original_status"] == orig_by_id[r["run_id"]]["original_status"]
                assert r["graph_sha256"] == a["graph_sha256"]
                assert r["original_checkpoint_sha256"] == orig_by_id[r["run_id"]]["checkpoint_sha256"]
                assert r["kind"] in ("isolated_vertex_recovery", "bounded_insertion")
                total_derived_kind[r["kind"]] += 1
                cases.append((int(r["derived_objective"]), r["run_id"], "separately_validated_" + r["kind"], r))
        assert cases
        best_value = min(item[0] for item in cases)
        tied_best = [item for item in cases if item[0] == best_value]
        assert len(tied_best) == 1, "best endpoint needs tie-aware provenance"
        _, best_id, best_type, best_record = tied_best[0]
        x_values = []
        for seed in (1, 2):
            x = task_by_key[iid, "xiong_rasstar", seed]
            i = task_by_key[iid, "ipsns", seed]
            assert x["status"] == "PASS" and x["objective"] and x["order_sha256"]
            assert i["status"] == "TIMEOUT" and not i["objective"] and not i["order_sha256"]
            value = int(x["objective"])
            assert value == raw["exp10_xiong_objectives"][iid][seed - 1]
            x_values.append(value)
            difference = best_value - value
            seed_rows.append({"instance_id": iid, "seed": seed, "exp05_best_run_id": best_id,
                "exp05_best_provenance": best_type, "exp05_original_status":
                orig_by_id[best_id]["original_status"], "exp05_best_objective": best_value,
                "xiong_objective": value, "improvement_weight": difference,
                "improvement_over_total_arc_weight": difference / int(a["total_weight"]),
                "improvement_over_exp05_objective": difference / best_value,
                "comparison": "XIONG_WIN" if difference > 0 else "TIE" if difference == 0 else "EXP05_WIN",
                "xiong_process_wall_seconds": x["process_wall_seconds"],
                "exp05_comparator_process_wall_seconds":
                    best_record["total_wall_seconds"],
                "exp05_comparator_initialization_inclusive_seconds":
                    best_record.get("initialization_inclusive_seconds", "")})
        best_x = min(x_values)
        graph_rows.append({"instance_id": iid, "source_parent": a["source_parent"],
            "total_arc_weight": a["total_weight"], "exp05_best_objective": best_value,
            "exp05_best_run_id": best_id, "exp05_best_provenance": best_type,
            "xiong_seed1_objective": x_values[0], "xiong_seed2_objective": x_values[1],
            "xiong_best_objective": best_x, "xiong_seed_span": abs(x_values[0] - x_values[1]),
            "best_xiong_improvement_weight": best_value - best_x,
            "best_xiong_improvement_over_total_arc_weight": (best_value - best_x) / int(a["total_weight"]),
            "best_xiong_improvement_over_exp05_objective": (best_value - best_x) / best_value,
            "xiong_strict_wins": sum(v < best_value for v in x_values),
            "ties": sum(v == best_value for v in x_values),
            "losses": sum(v > best_value for v in x_values)})
        for budget in BUDGETS:
            runs = [r for r in group if r["algorithm"] == "ipsns" and int(r["iteration_budget"]) == budget]
            assert len(runs) == 3 and {int(r["seed"]) for r in runs} == {1, 2, 3}
            runs.sort(key=lambda r: int(r["seed"]))
            derived_runs = [derived_by_id.get(r["run_id"]) for r in runs]
            objectives = [int(r["objective_weight"]) for r in runs if r["original_status"] == "PASS"]
            objectives += [int(r["derived_objective"]) for r in derived_runs if r]
            ipsns_rows.append({"instance_id": iid, "iteration_budget": budget, "seeds": "1;2;3",
                "original_pass": sum(r["original_status"] == "PASS" for r in runs),
                "original_fail": sum(r["original_status"] == "FAIL" for r in runs),
                "original_timeout": sum(r["original_status"] == "TIMEOUT" for r in runs),
                "derived_pass": sum(r is not None for r in derived_runs),
                "original_seed_statuses": ";".join(r["original_status"] for r in runs),
                "original_seed_process_wall_seconds": ";".join(r["total_wall_seconds"] for r in runs),
                "original_seed_objectives": ";".join(r["objective_weight"] for r in runs),
                "derived_seed_objectives": ";".join(r["derived_objective"] if r else "" for r in derived_runs),
                "best_validated_objective": min(objectives) if objectives else "",
                "best_endpoint_type": ("original_PASS" if any(r["original_status"] == "PASS" for r in runs)
                                       else "separately_validated_recovery" if objectives else "censored")})
    assert len(identity) == 3 and len(seed_rows) == 6 and len(graph_rows) == 3 and len(ipsns_rows) == 15
    assert dict(total_original_status) == raw["exp05_original_task_counts"]
    assert dict(total_derived_kind) == raw["exp05_derived_counts"]
    assert raw["exp05_original_pass_orders_rescored"] == 26 and raw["exp05_derived_orders_rescored"] == 13
    assert raw["exp10_xiong_orderings_rescored"] == 6 and raw["exp10_ipsns_timeouts_verified"] == 6
    historical_best = {}
    for iid in IDS:
        completed = [r for r in ipsns_rows if r["instance_id"] == iid and r["best_validated_objective"]]
        assert completed
        minimum = min(int(r["best_validated_objective"]) for r in completed)
        historical_best[iid] = {"objective": minimum,
            "first_budget_at_minimum": min(int(r["iteration_budget"]) for r in completed
                                           if int(r["best_validated_objective"]) == minimum),
            "largest_budget_with_validated_result": max(int(r["iteration_budget"]) for r in completed)}
    summary = {"format": "exp10-exp05-cross-summary-v1", "analysis_type": "post_hoc_descriptive",
        "source_parent_units": 3, "xiong_seed_runs": 6,
        "xiong_seed_comparisons": dict(Counter(r["comparison"] for r in seed_rows)),
        "graph_comparisons": {"XIONG_WIN": sum(r["xiong_strict_wins"] == 2 for r in graph_rows),
                              "TIE_OR_MIXED": sum(r["xiong_strict_wins"] != 2 for r in graph_rows)},
        "exp05_original_selected_statuses": dict(total_original_status),
        "exp05_selected_derived_endpoints": dict(total_derived_kind),
        "exp10_real_ipsns_200_iteration_timeouts": 6,
        "historical_ipsns_best_shorter_budget": historical_best}
    outputs = {"graph_identity.csv": csv_data(identity, IDENTITY_COLUMNS),
               "xiong_seed_comparisons.csv": csv_data(seed_rows, SEED_COLUMNS),
               "graph_comparisons.csv": csv_data(graph_rows, GRAPH_COLUMNS),
               "historical_ipsns.csv": csv_data(ipsns_rows, IPSNS_COLUMNS),
               "summary.json": json_data(summary)}
    return outputs, summary


def build(folder: Path, exp05: Path, exp10: Path, raw_path: Path) -> None:
    source_checksums(exp05)
    source_checksums(exp10)
    raw = obj(raw_path)
    assert raw["format"] == "exp10-exp05-raw-review-v1"
    origins = {}
    data = {}
    for name, original in FILES.items():
        source = (exp05 if name.startswith("exp05_") else exp10) / original
        source_key = ("exp05_" if name.startswith("exp05_") else "exp10_") + original
        expected = raw["source_audit_sha256"].get(source_key.replace(".csv", ""))
        if expected:
            assert sha(source) == expected
        if name == "exp10_selected_tasks.csv":
            assert sha(source) == raw["source_audit_sha256"]["exp10_task_inventory"]
        records, fields = select(source, name)
        data[name] = records
        origins[name] = {"source_file": str(source.relative_to(exp05 if name.startswith("exp05_") else exp10)),
                         "full_source_sha256": sha(source), "selected_rows": len(records)}
    # The EXP10 graph source is the published review package's input inventory.
    assert sha(exp05 / "audit_report.json") == "f9418cd452c6b23aa7742cd361eed13e6f1af64d441489432e32c04b4af77449"
    review10 = obj(exp10 / "source_review.json")
    assert review10["graphs_reparsed"] == 21 and review10["successful_orderings_rescored"] == 78
    exp10_provenance = obj(exp10 / "provenance.json")
    exp10_summary = obj(exp10 / "summary.json")
    assert raw["source_audit_sha256"]["exp10_manifest"] == exp10_provenance["source_file_sha256"]["manifest.json"]
    assert raw["source_revisions"] == exp10_provenance["source_revisions"]
    assert exp10_summary["slurm_accounting"]["job_id"] == raw["execution_context"]["exp10_job_id"]
    assert exp10_summary["slurm_accounting"]["allocated_cpus"] == 1
    derived_outputs, _ = derive(data, raw)
    folder.mkdir(parents=True, exist_ok=True)
    assert (folder / "README.md").exists(), "write scientific review before building"
    for name, original in FILES.items():
        source = (exp05 if name.startswith("exp05_") else exp10) / original
        records, fields = select(source, name)
        (folder / name).write_bytes(csv_data(records, fields))
    for name, content in derived_outputs.items():
        (folder / name).write_bytes(content)
    (folder / "raw_review.json").write_bytes(json_data(raw))
    provenance = {"format": "exp10-exp05-cross-provenance-v1", "source_snapshots": origins,
        "exp05_audit_report_sha256": sha(exp05 / "audit_report.json"),
        "exp10_review_source_review_sha256": sha(exp10 / "source_review.json"),
        "exp05_original_revision": obj(exp05 / "audit_report.json")["original_revision"],
        "exp05_recovery_revision": obj(exp05 / "audit_report.json")["recovery_revision"],
        "exp10_original_revision": exp10_provenance["source_revisions"]["repo_revision"],
        "xiong_revision": exp10_provenance["source_revisions"]["xiong_revision"],
        "ipsns_revision": exp10_provenance["source_revisions"]["ipsns_revision"],
        "execution_context": {**raw["execution_context"], "exp10_allocated_cpus": 1},
        "raw_review_sha256": sha(folder / "raw_review.json"),
        "source_raw_review_sha256": sha(raw_path)}
    (folder / "provenance.json").write_bytes(json_data(provenance))
    names = sorted(path.name for path in folder.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (folder / "checksums.sha256").write_text("".join(f"{sha(folder / name)}  {name}\n" for name in names))
    verify(folder, exp05, exp10)


def verify(folder: Path, exp05: Path | None = None, exp10: Path | None = None) -> None:
    checksums = (folder / "checksums.sha256").read_text().splitlines()
    listed = {}
    for line in checksums:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        assert match, line
        listed[match[2]] = match[1]
    expected_files = {path.name for path in folder.iterdir() if path.is_file() and path.name != "checksums.sha256"}
    assert set(listed) == expected_files and len(listed) == 13
    for name, digest in listed.items():
        assert sha(folder / name) == digest, name
    raw = obj(folder / "raw_review.json")
    provenance = obj(folder / "provenance.json")
    assert sha(folder / "raw_review.json") == provenance["raw_review_sha256"]
    assert provenance["execution_context"] == {**raw["execution_context"], "exp10_allocated_cpus": 1}
    assert provenance["exp10_original_revision"] == raw["source_revisions"]["repo_revision"]
    assert provenance["xiong_revision"] == raw["source_revisions"]["xiong_revision"]
    assert provenance["ipsns_revision"] == raw["source_revisions"]["ipsns_revision"]
    for name, raw_key in (("exp05_graphs.csv", "exp05_benchmark_inventory"),
                          ("exp05_original_tasks.csv", "exp05_original_inventory"),
                          ("exp05_derived_endpoints.csv", "exp05_derived_inventory"),
                          ("exp10_selected_tasks.csv", "exp10_task_inventory")):
        assert provenance["source_snapshots"][name]["full_source_sha256"] == raw["source_audit_sha256"][raw_key]
    data = {name: csv_rows(folder / name) for name in FILES}
    outputs, _ = derive(data, raw)
    for name, content in outputs.items():
        assert (folder / name).read_bytes() == content, name
    if exp05 is not None and exp10 is not None:
        source_checksums(exp05); source_checksums(exp10)
        for name, original in FILES.items():
            root = exp05 if name.startswith("exp05_") else exp10
            source = root / original
            assert sha(source) == provenance["source_snapshots"][name]["full_source_sha256"]
            records, fields = select(source, name)
            assert (folder / name).read_bytes() == csv_data(records, fields)
        assert sha(exp05 / "audit_report.json") == provenance["exp05_audit_report_sha256"]
        assert sha(exp10 / "source_review.json") == provenance["exp10_review_source_review_sha256"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("package", type=Path)
    parser.add_argument("--exp05", type=Path)
    parser.add_argument("--exp10", type=Path)
    parser.add_argument("--raw-review", type=Path)
    args = parser.parse_args()
    if args.action == "build":
        assert args.exp05 and args.exp10 and args.raw_review
        build(args.package, args.exp05, args.exp10, args.raw_review)
    else:
        verify(args.package, args.exp05, args.exp10)
    print("EXP10–EXP05 cross-campaign package: PASS")
