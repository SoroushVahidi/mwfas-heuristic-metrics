"""Deterministic checks of the EXP25 candidate metadata and resource arithmetic.

This reads no graph/order bytes and launches no experiment.
"""

import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ROWS = list(csv.DictReader((ROOT / "candidate_graphs.csv").open(newline="")))
METHODS = {"lrta": 1, "wmsf_l2": 1, "weighted_eades": 1,
           "insertion_lrta": 1, "insertion_wmsf_l2": 1,
           "ipsns": 2, "xiong_single": 2, "xiong_restarts": 2}
CORE_CAPS = (10, 30, 120)
WEIGHT_DIAGNOSTIC_CAPS = (10,)


def main() -> None:
    assert len(ROWS) == 25
    assert Counter(r["cohort"] for r in ROWS) == {"EXP04": 12, "EXP06": 6, "EXP05": 4, "EXP13": 3}
    assert len({r["instance_id"] for r in ROWS}) == len({r["canonical_graph_sha256"] for r in ROWS}) == 25
    assert len({r["source_parent_or_topology"] for r in ROWS if not r["source_parent_or_topology"].startswith("GENERATED:")}) == 7
    assert len({r["topology_sha256"] for r in ROWS if r["cohort"] in {"EXP04", "EXP06"}}) == 15
    assert all(sum(r["cohort"] == "EXP06" and r["topology_sha256"] == h for r in ROWS) == 2
               for h in {r["topology_sha256"] for r in ROWS if r["cohort"] == "EXP06"})
    assert sum(METHODS.values()) == 11
    assert 19 * sum(METHODS.values()) * len(CORE_CAPS) + 6 * sum(METHODS.values()) == 693
    assert 19 * sum(METHODS.values()) * sum(CORE_CAPS) + 6 * sum(METHODS.values()) * sum(WEIGHT_DIAGNOSTIC_CAPS) == 34100
    assert 7 * sum(METHODS.values()) * 300 == 23100
    for r in ROWS:
        n, m, total = (int(r[k]) for k in ("n", "m", "total_weight"))
        assert 0 < m <= n * (n - 1) and total >= m
        assert abs(float(r["density"]) - m / (n * (n - 1))) < 5.1e-10
        assert 1 <= int(r["largest_scc"]) <= n
        assert 1 <= int(r["scc_count"]) <= n
        assert 0 < int(r["weight_min"]) <= int(r["weight_max"])
        assert len(r["canonical_graph_sha256"]) == len(r["dimacs_sha256"]) == 64
        assert r["source_byte_sha256"] == "GENERATED_NO_UPSTREAM_SOURCE" or all(
            len(h) == 64 and all(c in "0123456789abcdef" for c in h)
            for h in r["source_byte_sha256"].split(";"))
        assert r["redistribution"] in {"AUTHOR_GENERATED_RIGHTS_REVIEW", "SOURCE_SPECIFIC_REVIEW_REQUIRED"}
    print("PASS: 25 unique views; 7 empirical parents; 693 core tasks; 34,100 cap seconds")
    print("PASS: optional seven-parent 300-second stratum = 77 tasks; 23,100 cap seconds")


if __name__ == "__main__":
    main()
