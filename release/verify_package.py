"""Verify the staged release ledger and local file identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release/manifest.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    entries = manifest["files"]
    expected = {entry["path"] for entry in entries}
    if len(expected) != len(entries):
        raise ValueError("duplicate release path")
    actual = {str(path.relative_to(ROOT)) for path in ROOT.rglob("*")
              if path.is_file() and ".git" not in path.parts and ".venv" not in path.parts
              and "__pycache__" not in path.parts and "data/cache" not in str(path.relative_to(ROOT))
              and "results" not in path.parts and ".pytest_cache" not in path.parts}
    excluded = {"release/manifest.json", "release/CHECKSUMS.sha256"}
    if actual - excluded != expected:
        raise ValueError(f"file list mismatch: missing={sorted(expected - actual)}, extra={sorted(actual - excluded - expected)}")
    for entry in entries:
        path = ROOT / entry["path"]
        data = path.read_bytes()
        if len(data) != entry["size_bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError(f"checksum mismatch: {entry['path']}")
    print(f"PASS {len(entries)} release files")


if __name__ == "__main__":
    main()
