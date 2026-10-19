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
    print("valid: public Table 4/5 immutable pins and anonymous replay receipt")
