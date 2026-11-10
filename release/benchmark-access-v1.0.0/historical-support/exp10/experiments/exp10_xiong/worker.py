"""One bounded comparison process; raw output is checked by a separate auditor."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from .input_contract import check_w, parse_dimacs, write_w


def main() -> None:
    p = argparse.ArgumentParser()
    for name in ("graph", "row", "algorithm", "seed", "output", "xiong_binary", "ipsns_source"):
        p.add_argument("--" + name.replace("_", "-"), required=True)
    a = p.parse_args()
    graph, output = Path(a.graph), Path(a.output)
    row = json.loads(a.row); seed = int(a.seed)
    started = time.perf_counter()
    if a.algorithm == "xiong_rasstar":
        n, arcs, info = parse_dimacs(graph, row)
        wfile = output / "input.w"
        write_w(wfile, n, arcs); check_w(wfile, n, arcs)
        result = subprocess.run([a.xiong_binary, str(wfile), "W", "RASstar", "-r", str(seed),
                                 "-p", "-o", str(output / "ranks.txt")], capture_output=True,
                                text=True, check=True)
        (output / "xiong.stdout").write_text(result.stdout)
        (output / "xiong.stderr").write_text(result.stderr)
        fields = result.stdout.strip().split(",")
        if len(fields) != 3:
            raise ValueError("unexpected Xiong CSV stdout")
        raw = {"reported_objective": int(fields[1]), "algorithm_only_ms": int(fields[2]),
               "input": info, "conversion_seconds": None,
               "rank_format": "zero_based_rank_of_each_zero_based_vertex"}
    elif a.algorithm == "ipsns":
        sys.path.insert(0, str(Path(a.ipsns_source) / "src"))
        from mwfas.ipsns import lns_merge_wmsf_lr_best_incumbent
        begin_algorithm = time.perf_counter()
        result = lns_merge_wmsf_lr_best_incumbent(
            graph, output / "order.csv", seed_ordering="L2", iters=200, topK_scc=15,
            destroy_addback_frac=0.30, destroy_remove_frac=0.02, tol=1e-12,
            rng_seed=seed, log_every=0, wmsf_seed_mode="full",
            scc_select_mode="weighted", return_info=True)
        raw = {"reported_objective": result[5]["final_bw"],
               "algorithm_only_seconds": time.perf_counter() - begin_algorithm,
               "algorithm_info": result[5], "rank_format": "Node ID,Order CSV"}
        # The frozen IPSNS parser can omit truly isolated declared vertices.
        # Preserve its raw CSV, then create a separately identified completion.
        n, arcs, info = parse_dimacs(graph, row)
        with (output / "order.csv").open(newline="") as stream:
            records = list(csv.DictReader(stream))
        observed = [int(record["Node ID"]) for record in records]
        ranks = [int(record["Order"]) for record in records]
        if len(observed) != len(set(observed)) or sorted(ranks) != list(range(len(records))):
            raise ValueError("frozen IPSNS raw order is malformed")
        if any(v < 1 or v > n for v in observed):
            raise ValueError("frozen IPSNS order contains a foreign vertex")
        incident = {u for u, _, _ in arcs} | {v for _, v, _ in arcs}
        missing = sorted(set(range(1, n + 1)) - set(observed))
        if any(v in incident for v in missing):
            raise ValueError("frozen IPSNS omitted a nonisolated vertex")
        order = [int(r["Node ID"]) for r in sorted(records, key=lambda r: int(r["Order"]))] + missing
        with (output / "complete_order.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["Node ID", "Order"])
            writer.writeheader(); writer.writerows({"Node ID": v, "Order": i} for i, v in enumerate(order))
        position = {v: i for i, v in enumerate(order)}
        recovered_objective = sum(w for u, v, w in arcs if position[u] >= position[v])
        if abs(recovered_objective - raw["reported_objective"]) > 1e-7:
            raise ValueError("isolated-vertex completion changed IPSNS objective")
        raw["ordering_provenance"] = {"raw_order_sha256": hashlib.sha256((output / "order.csv").read_bytes()).hexdigest(),
                                      "missing_isolated_vertices": missing,
                                      "derived_order_sha256": hashlib.sha256((output / "complete_order.csv").read_bytes()).hexdigest(),
                                      "derived_objective": recovered_objective,
                                      "status": "ISOLATE_ONLY_DERIVED" if missing else "UNCHANGED_COMPLETE"}
    else:
        raise ValueError("unapproved algorithm")
    raw["worker_wall_seconds"] = time.perf_counter() - started
    (output / "raw.json").write_text(json.dumps(raw, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
