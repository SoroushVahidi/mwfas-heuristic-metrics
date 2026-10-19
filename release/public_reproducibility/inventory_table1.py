"""Reconstruct Table 1 inventory/joins from public metadata, not private inputs.

A PASS here is metadata arithmetic only. It does NOT make Table 1 completely
publicly replayable: the 45 EXP03 and 38 EXP05 graph bytes are not in this package.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from replay_table45 import read_csv, read_json, require, sha


def verify(package, output):
    reference = package / "statistical_reference"
    names = ("wulver__canonical_graphs.csv.gz", "wulver__canonical_runs.csv.gz", "wulver__exp07_hash_overlap.csv")
    manifest = {r["path"]: r for r in read_json(package / "manifest.json")["entries"]}
    for name in names:
        require(sha(reference / name) == manifest["statistical_reference/" + name]["sha256"], "reference checksum mismatch")
    graphs = read_csv(reference / names[0])
    runs = read_csv(reference / names[1])
    reused = read_csv(reference / names[2])
    mapping = {(r["campaign"], r["instance_id"]): r for r in graphs}
    require(len(mapping) == len(graphs) == 416, "duplicate/missing graph records")
    require(len({(r["campaign"], r["run_id"]) for r in runs}) == len(runs) == 5083, "task identity mismatch")
    rows = []
    expected = {"EXP03": (45, 45, 900), "EXP04": (135, 135, 2025),
                "EXP05": (38, 38, 760), "EXP06": (198, 99, 1398)}
    for campaign, counts in expected.items():
        gs = [r for r in graphs if r["campaign"] == campaign]
        rs = [r for r in runs if r["campaign"] == campaign]
        actual = (len({r["graph_sha256"] for r in gs}), len({r["topology_sha256"] for r in gs}), len(rs))
        require(actual == counts, f"Table 1 count mismatch: {campaign}")
        for r in rs:
            require(r["graph_sha256"] == mapping[(campaign, r["instance_id"])]["graph_sha256"], "task/graph hash join mismatch")
        rows.append({"campaign": campaign, "weighted_inputs": actual[0], "topologies": actual[1], "tasks": actual[2], "status": "PASS"})
    require(len({r["graph_sha256"] for r in graphs}) == 416 and len({r["topology_sha256"] for r in graphs}) == 317,
            "cross-campaign distinct totals mismatch")
    require(len({r["source_parent"] for r in graphs if r["campaign"] == "EXP05"}) == 4, "EXP05 parent count")
    require(len(reused) == len({r["graph_sha256"] for r in reused}) == len({r["topology_sha256"] for r in reused}) == 45,
            "EXP07 inventory mismatch")
    require(Counter(r["source_experiment"] for r in reused) == {"EXP03": 9, "EXP04": 36}, "EXP07 9+36 overlap")
    for r in reused:
        source = mapping[(r["source_experiment"], r["instance_id"])]
        require(all(r[k] == source[k] for k in ("graph_sha256", "topology_sha256")), "EXP07 source identity join")
    exp06 = [r for r in graphs if r["campaign"] == "EXP06"]
    for k in ("graph_sha256", "topology_sha256"):
        require(not ({r[k] for r in exp06} & {r[k] for r in reused}), "unexpected EXP06/07 overlap")
    result = {"status": "PASS", "classification": "PUBLIC_METADATA_ONLY", "table": 1,
              "rows": rows, "total": {"weighted_inputs": 416, "topologies": 317, "tasks": 5083},
              "exp07_reused": {"weighted_inputs": 45, "topologies": 45, "EXP03": 9, "EXP04": 36},
              "complete_public_table": False,
              "remaining": "Exact 45 EXP03 and 38 EXP05 inputs and their complete public byte-based joins/replay are not supplied by this release."}
    output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("package", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    verify(a.package, a.output)
