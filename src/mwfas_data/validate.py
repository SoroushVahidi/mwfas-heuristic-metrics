"""Evidence-based release checks. Findings are never silently repaired."""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq

from .config import ROOT, load_project
from .retrieval import load_manifest, verify_file


def finding(name: str, status: str, detail: str, count: int | None = None) -> dict:
    result = {"name": name, "status": status, "detail": detail}
    if count is not None:
        result["count"] = count
    return result


def close(a: object, b: object, tolerance: float = 1e-7) -> bool:
    return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def check_objective(rows: list[dict], config: str) -> dict:
    candidates = [r for r in rows if all(k in r and r[k] is not None for k in ("total_weight", "forward_weight", "backward_weight"))]
    if not candidates:
        return finding(f"{config}.objective_arithmetic", "NOT_VERIFIABLE", "No complete total/forward/backward triples")
    failures = sum(not close(r["total_weight"], r["forward_weight"] + r["backward_weight"]) for r in candidates)
    return finding(f"{config}.objective_arithmetic", "FAIL" if failures else "PASS", f"Checked {len(candidates)} complete rows", failures)


def check_required_metadata(rows: list[dict], config: str) -> dict:
    required = ["benchmark_resource"] if config == "aggregate_summary" else ["source_experiment", "source_commit", "benchmark_resource"]
    if "instance_id" in rows[0]:
        required.append("instance_id")
    missing = sum(any(not r.get(k) for k in required) for r in rows)
    return finding(f"{config}.required_metadata", "FAIL" if missing else "PASS", ", ".join(required), missing)


def check_key_uniqueness(rows: list[dict], config: str) -> dict:
    special = {"core_benchmark": ["benchmark_resource", "instance_id", "algorithm"],
               "external_baselines": ["benchmark_resource", "instance_id", "algorithm"],
               "ablation": ["benchmark_resource", "instance_id", "algorithm_variant"]}
    keys = special.get(config)
    if keys is None:
        return finding(f"{config}.key_uniqueness", "NOT_VERIFIABLE", "No unique run key defined for this config")
    seen = set()
    repeated = 0
    for row in rows:
        key = tuple(row.get(k) for k in keys)
        if key in seen:
            repeated += 1
        seen.add(key)
    return finding(f"{config}.key_uniqueness", "FAIL" if repeated else "PASS", f"Key: {keys}; duplicate rows beyond first", repeated)


def check_full_duplicates(rows: list[dict], config: str) -> dict:
    signatures = [json.dumps(row, sort_keys=True, default=str) for row in rows]
    repeated = len(signatures) - len(set(signatures))
    return finding(f"{config}.full_row_duplicates", "FAIL" if repeated else "PASS", "Byte-equivalent field values across complete rows", repeated)


def check_split_leakage(rows: list[dict]) -> dict:
    split_by_instance = defaultdict(set)
    for row in rows:
        split_by_instance[(row.get("benchmark_resource"), row.get("instance_id"))].add(row.get("split"))
    overlap = {str(k): sorted(v) for k, v in split_by_instance.items() if len(v - {None}) > 1}
    return finding("run_metrics.tuning_holdout_overlap", "FAIL" if overlap else "PASS", f"Instances in multiple splits: {list(overlap)[:10]}", len(overlap))


def check_cross_configuration(tables: dict[str, list[dict]]) -> dict:
    aliases = {"lrta": "lrta_full", "wmsf": "wmsf_seed", "ipsns": "ipsns_full"}
    left = defaultdict(set)
    right = defaultdict(set)
    for row in tables["core_benchmark"]:
        left[row["instance_id"], aliases[row["algorithm"]]].add(row["backward_weight"])
    for row in tables["external_baselines"]:
        if row["algorithm"] in aliases.values() and row["backward_weight"] is not None:
            right[row["instance_id"], row["algorithm"]].add(row["backward_weight"])
    comparable = left.keys() & right.keys()
    mismatches = [k for k in comparable if left[k] != right[k]]
    return finding("core_external_objective_agreement", "FAIL" if mismatches else "PASS", f"Compared {len(comparable)} instance/algorithm keys; mismatches: {mismatches[:10]}", len(mismatches))


def check_aggregates(tables: dict[str, list[dict]]) -> dict:
    keycols = ("experiment_family", "algorithm", "configuration_id", "split", "instance_family", "benchmark_resource")
    failures = []
    checked = 0
    for index, row in enumerate(tables["aggregate_summary"]):
        source = tables.get(row["source_config"], [])
        selected = [item for item in source if all(item.get(k) == row.get(k) for k in keycols)]
        if not selected:
            failures.append((index, "no source rows")); continue
        checked += 1
        if len(selected) != row["n_runs"] or len({x["instance_id"] for x in selected}) != row["n_instances"]:
            failures.append((index, "count mismatch")); continue
        for source_col, summary_col in (("objective_weight", "objective_weight_mean"), ("runtime_seconds", "runtime_seconds_mean")):
            values = [x[source_col] for x in selected if x.get(source_col) is not None]
            if not values or not close(sum(values) / len(values), row[summary_col], 1e-5):
                failures.append((index, summary_col))
        for source_col, summary_col in (("objective_weight", "objective_weight_median"), ("runtime_seconds", "runtime_seconds_median")):
            values = [x[source_col] for x in selected if x.get(source_col) is not None]
            if not values or not close(statistics.median(values), row[summary_col], 1e-5):
                failures.append((index, summary_col))
        if not close(sum(x.get("status") == "ok" for x in selected) / len(selected), row["success_rate"], 1e-5):
            failures.append((index, "success_rate"))
        if not close(sum(x.get("validated") is True for x in selected) / len(selected), row["validation_rate"], 1e-5):
            failures.append((index, "validation_rate"))
    return finding("aggregate_summary.recalculation", "FAIL" if failures else "PASS", f"Checked {checked} of {len(tables['aggregate_summary'])} rows; first failures: {failures[:10]}", len(failures))


def audit_release(cache: Path | None = None) -> dict:
    config = load_project()
    manifest = load_manifest()
    cache = cache or ROOT / config["cache_dir"]
    checks = []
    tables = {}
    schemas = {}
    for name, meta in manifest["configs"].items():
        relative = f"data/{name}/train.parquet"
        path = cache / relative
        if not verify_file(path, manifest["files"][relative]):
            checks.append(finding(f"{name}.integrity", "FAIL", "Missing or SHA-256 mismatch"))
            continue
        table = pq.read_table(path)
        rows = table.to_pylist()
        tables[name] = rows
        schemas[name] = {field.name: {"arrow_type": str(field.type), "null_count": table[field.name].null_count} for field in table.schema}
        checks.append(finding(f"{name}.integrity", "PASS" if len(rows) == meta["rows"] else "FAIL", f"SHA-256 verified; {len(rows)} rows vs {meta['rows']} expected"))
        checks.append(check_required_metadata(rows, name))
        checks.append(check_key_uniqueness(rows, name))
        checks.append(check_full_duplicates(rows, name))
        checks.append(check_objective(rows, name))
    if "run_metrics" in tables:
        checks.append(check_split_leakage(tables["run_metrics"]))
    if "core_benchmark" in tables and "external_baselines" in tables:
        checks.append(check_cross_configuration(tables))
    if all(k in tables for k in ("aggregate_summary", "run_metrics", "sensitivity", "robustness")):
        checks.append(check_aggregates(tables))
    checks.append(finding("graph_and_order_artifacts", "NOT_VERIFIABLE", "Release contains metrics but no graph edge lists, orderings, or feedback-arc sets; independent objective and acyclicity recomputation requires fetched source artifacts"))
    checksum_path = cache / "CHECKSUMS.sha256"
    if checksum_path.exists():
        mismatches = []
        for line in checksum_path.read_text().splitlines():
            digest, relative = line.split(maxsplit=1)
            if not verify_file(cache / relative.strip().lstrip("*"), digest):
                mismatches.append(relative.strip())
        checks.append(finding("upstream_CHECKSUMS", "FAIL" if mismatches else "PASS", f"Mismatched entries: {mismatches}", len(mismatches)))
    return {"dataset_revision": config["dataset_revision"], "checks": checks, "schemas": schemas,
            "rows_loaded": {name: len(rows) for name, rows in tables.items()}}


def write_report(path: Path, cache: Path | None = None) -> dict:
    report = audit_release(cache)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
