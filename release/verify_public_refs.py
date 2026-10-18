"""Verify pinned, publicly referenced files without storing their raw bytes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from pathlib import Path
from urllib.request import Request, urlopen


MANIFEST = Path(__file__).with_name("public_reference_manifest.csv")
REQUIRED = {
    "artifact_id", "kind", "source_parent", "revision", "url",
    "size_bytes", "sha256", "rights_status", "upstream_reconstruction",
}


def load_manifest(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        if set(reader.fieldnames or ()) != REQUIRED:
            raise ValueError("manifest columns differ from the release contract")
        rows = list(reader)
    entries: dict[str, dict[str, str]] = {}
    for row in rows:
        artifact_id = row["artifact_id"]
        if artifact_id in entries:
            raise ValueError(f"duplicate artifact ID: {artifact_id}")
        if not row["url"].startswith("https://") or row["revision"] not in row["url"]:
            raise ValueError(f"unpinned or non-HTTPS reference: {artifact_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", row["sha256"]):
            raise ValueError(f"invalid SHA-256: {artifact_id}")
        if int(row["size_bytes"]) < 0:
            raise ValueError(f"invalid byte size: {artifact_id}")
        entries[artifact_id] = row
    if len(entries) != 62:
        raise ValueError(f"expected 62 pinned references, found {len(entries)}")
    return entries


def verify(row: dict[str, str], timeout: int) -> None:
    request = Request(row["url"], headers={"User-Agent": "MWFAS-public-reference-verifier/1"})
    digest = hashlib.sha256()
    total = 0
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}: {row['artifact_id']}")
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            digest.update(chunk)
    if total != int(row["size_bytes"]) or digest.hexdigest() != row["sha256"]:
        raise ValueError(f"byte identity mismatch: {row['artifact_id']}")
    print(f"PASS {row['artifact_id']} {total} bytes")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-id", action="append", default=[], help="Exact ID; repeat to check several")
    parser.add_argument("--all", action="store_true", help="Download and verify all 62 public references")
    parser.add_argument("--offline", action="store_true", help="Validate the manifest without downloading")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()
    entries = load_manifest(MANIFEST)
    if args.offline:
        print(f"PASS manifest schema and identity: {len(entries)} references")
        return
    if args.all == bool(args.artifact_id):
        parser.error("choose --all or at least one --artifact-id")
    for artifact_id in sorted(entries) if args.all else args.artifact_id:
        if artifact_id not in entries:
            parser.error(f"unknown artifact ID: {artifact_id}")
        verify(entries[artifact_id], args.timeout)


if __name__ == "__main__":
    main()
