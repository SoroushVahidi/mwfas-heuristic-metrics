"""Load the pinned public input configuration."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_project(path: Path | None = None) -> dict:
    data = json.loads((path or ROOT / "configs/project.json").read_text())
    for key in ("dataset_repo", "dataset_revision", "source_repo", "source_revision", "cache_dir"):
        if not data.get(key):
            raise ValueError(f"missing project setting: {key}")
    for key in ("dataset_revision", "source_revision", "benchmark_revision"):
        value = data[key]
        if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"invalid immutable revision: {key}")
    return data
