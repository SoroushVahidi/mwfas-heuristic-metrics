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
