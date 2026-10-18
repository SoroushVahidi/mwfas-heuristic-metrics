"""Fetch pinned public release files and verify local bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from .config import ROOT, load_project


def load_manifest(path: Path | None = None) -> dict:
    manifest = json.loads((path or ROOT / "data/manifests/provenance.json").read_text())
    config = load_project()
    if manifest["dataset_revision"] != config["dataset_revision"]:
        raise ValueError("dataset revision differs between config and manifest")
    return manifest


def verify_file(path: Path, expected_sha256: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == expected_sha256


def fetch_release(cache: Path | None = None, only: set[str] | None = None) -> dict[str, str]:
    config = load_project()
    manifest = load_manifest()
    cache = cache or ROOT / config["cache_dir"]
    status = {}
    for relative, sha256 in manifest["files"].items():
        if only is not None and relative not in only:
            continue
        target = cache / relative
        if verify_file(target, sha256):
            status[relative] = "cached_verified"
            continue
        url = f'https://huggingface.co/datasets/{config["dataset_repo"]}/resolve/{config["dataset_revision"]}/{relative}'
        try:
            with urlopen(url, timeout=30) as response:
                payload = response.read()
        except Exception as exc:
            raise RuntimeError(f"could not fetch {relative}: {exc}") from exc
        if hashlib.sha256(payload).hexdigest() != sha256:
            raise ValueError(f"SHA-256 mismatch for {relative}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        status[relative] = "downloaded_verified"
    return status
