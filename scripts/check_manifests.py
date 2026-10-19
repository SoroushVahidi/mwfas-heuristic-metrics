"""Validate committed configuration and provenance manifests without network access."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
loaded = {}
for relative in ("configs/project.json", "configs/exp01.json", "configs/exp03.json", "data/manifests/provenance.json", "data/manifests/baseline_audit.json", "data/manifests/initial_validation.json"):
    data = json.loads((root / relative).read_text())
    if not data:
        raise ValueError(f"empty JSON: {relative}")
    loaded[relative] = data
    print(f"valid: {relative}")
config = loaded["configs/project.json"]
manifest = loaded["data/manifests/provenance.json"]
audit = loaded["data/manifests/baseline_audit.json"]
assert config["dataset_revision"] == manifest["dataset_revision"]
assert config["source_revision"] == manifest["source_revision"]
assert set(manifest["configs"]) == set(audit["configs"])
assert all(manifest["configs"][name]["rows"] == audit["configs"][name]["rows"] for name in manifest["configs"])
assert sum(item["rows"] for item in manifest["configs"].values()) == 7371
assert all(len(digest) == 64 for digest in manifest["files"].values())
validation = loaded["data/manifests/initial_validation.json"]
assert validation["dataset_revision"] == config["dataset_revision"]
assert validation["rows_loaded"] == {name: item["rows"] for name, item in manifest["configs"].items()}
if "public_reproducibility" in config or "public_reproducibility" in manifest:
    public = config["public_reproducibility"]
    assert public == manifest["public_reproducibility"]
    assert public["dataset_repo"] == "SoroushVahidi/mwfas-benchmark-extension"
    assert public["code_repo"] == "SoroushVahidi/mwfas-heuristic-metrics"
    assert all(len(public[k]) == 40 and set(public[k]) <= set("0123456789abcdef")
               for k in ("dataset_revision", "code_revision"))
    assert all(len(public[k]) == 64 for k in ("archive_sha256", "manifest_sha256"))
    receipt = json.loads((root / "release/public_reproducibility/public_replay_receipt.json").read_text())
    assert receipt["status"] == "PASS" and receipt["anonymous"] and receipt["fresh_directory"]
    assert receipt["code_revision"] == public["code_revision"]
    assert receipt["data_revision"] == public["dataset_revision"]
    assert receipt["download_sha256"]["data"] == public["archive_sha256"]
    assert public["fully_replayable_tables"] == [4, 5]
    assert receipt["replay"]["tables"] == {"4": "PUBLIC_REPLAYABLE", "5": "PUBLIC_REPLAYABLE"}
    assert public.get("fully_replayable_printed_tables", [6, 7]) == [6, 7]
    print("valid: public internal T4/T5 (printed Tables 6/7) immutable pins and anonymous replay receipt")
if "exp28_public_reproducibility" in config or "exp28_public_reproducibility" in manifest:
    public = config["exp28_public_reproducibility"]
    assert public == manifest["exp28_public_reproducibility"]
    assert public["dataset_repo"] == "SoroushVahidi/mwfas-benchmark-extension"
    assert public["code_repo"] == "SoroushVahidi/mwfas-heuristic-metrics"
    assert all(len(public[k]) == 40 and set(public[k]) <= set("0123456789abcdef")
               for k in ("dataset_revision", "code_revision"))
    receipt = json.loads((root / "release/public_reproducibility/exp28_public_replay_receipt.json").read_text())
    assert receipt["status"] == "PASS" and receipt["classification"] == "PUBLIC_REPLAYABLE"
    assert receipt["anonymous"] and receipt["fresh_directory"] and receipt["read_guard"] == "PASS"
    assert receipt["code_revision"] == public["code_revision"] and receipt["data_revision"] == public["dataset_revision"]
    assert receipt["download_sha256"]["data"] == public["light_archive_sha256"]
    assert receipt["download_sha256"]["exp28-full.tar.gz"] == public["full_archive_sha256"]
    assert receipt["replay"]["full_archive"]["status"] == "PASS"
    assert receipt["replay"]["full_archive"]["orders"] == receipt["replay"]["events"] == 143241
    assert receipt["replay"]["statuses"] == {"PASS": 98, "TIMEOUT": 19}
    assert (receipt["replay"]["graphs"], receipt["replay"]["tasks"], receipt["replay"]["selected_orders"],
            receipt["replay"]["budget_rows"], receipt["replay"]["paired_rows"],
            receipt["replay"]["table9_displayed_numeric_cells"], receipt["replay"]["figure2_points"]) == (13,117,160,234,182,20,26)
    trace = json.loads((root / "release/public_reproducibility/exp28_trace_receipt.json").read_text())
    assert trace["status"] == "PASS" and trace["private_input_reads_outside_fresh_directory"] == 0
    assert public["printed_table"] == 9 and public["printed_figure"] == 2
    print("valid: printed Table 9 / Figure 2 full anonymous replay, hashes, counts and isolation trace")
