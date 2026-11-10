# Reproduction instructions

This public supplementary bundle contains working independent verification code, supplied historical metadata, and evidence. No unpublished experimental implementation, private graph, private ordering, solver, token, or original virtual environment is required. The independent verifier is publicly released in benchmark-supplement-v1.0.0. A separate public-code-only replay is documented below.

Requirements: Linux shell, CPython 3.12 (tested 3.12.3), working `python3 -m venv`, TLS root certificates, DNS and anonymous HTTPS access to GitHub codeload and Hugging Face. Python standard library only; no pip packages, graph library or optimizer. On this machine `/usr/bin/python3` provided Python 3.12.3. `venv` creates a new environment with system site packages disabled. Creating it may require the OS Python venv package on another machine.

## Complete independent workflow

Copy this audit directory to any location. Set BUNDLE to that location; do not reuse a previous destination.

```bash
BUNDLE=/path/to/benchmark-supplement-v1.0.0
CLEAN=$(mktemp -d /tmp/mwfas-reproduction-XXXXXXXX)
cd "$CLEAN"
bash "$BUNDLE/INDEPENDENT_VERIFIER_SOURCE/run_clean.sh" "$BUNDLE"
```

The launcher copies only verifier source and `supplied_manifests/` into the fresh root, creates a new venv, empties the execution environment, downloads all three pinned public resources anew, verifies all release files, performs independent graph/order/objective checks, runs the test suite and smoke example, and runs the downloaded historical public replay. It never copies downloaded graphs from the bundle or another environment. Expected terminal output: `COMPLETED_SUCCESS`.

The launcher records `download.log`, `PUBLIC_DOWNLOAD_MANIFEST.tsv`, `verification.log`, `SUMMARY.json`, `GRAPH_IDENTITY_VERIFICATION.tsv`, `OBJECTIVE_RECOMPUTATION_RESULTS.tsv`, `NUMERICAL_REFERENCE_CHECKS.tsv`, `PACKAGE_COMPLETENESS.json`, `VERIFIER_TEST_RESULTS.txt`, `BENCHMARK_USAGE_RESULT.json`, `public_replay/report.json`, and access logs in the fresh root. The scripts fail on missing downloads, checksum differences, invalid inputs or failed verification. Keep all files for review.

## Interface for a candidate algorithm

```bash
python3 -I -B "$BUNDLE/BENCHMARK_USAGE_EXAMPLE.py" "$CLEAN/table45"
```

The example actually evaluates increasing vertex IDs on a real downloaded graph. Its gap is an interface demonstration, not a scientific performance result.

For Python integration, put `INDEPENDENT_VERIFIER_SOURCE` on your import path:

```python
from mwfas_benchmark import Benchmark, compare
benchmark = Benchmark("/path/to/downloaded/table45")
key = benchmark.instances()[0]
graph = benchmark.load(key)
# graph.vertices: immutable complete vertex tuple; graph.arcs: (u, v, w) tuples.
order = list(graph.vertices)  # Replace with your algorithm's complete ordering.
reference = benchmark.saved_reference(key)
result = compare(graph, order, reference["objective"], reference["kind"])
print(result)
```

Use `load_graph(path)`, `load_order(path, graph)`, `evaluate(graph, order)` and `identities(graph)` directly if desired. Order CSV columns must be `Node ID,Order`, with ranks exactly 0 through n−1. The list API accepts vertex IDs in ordering sequence. Invalid candidates raise `ValueError`; they are never repaired. A best saved feasible reference is not asserted optimal. Absolute gap is candidate minus reference; relative gap is that difference divided by reference. For reference zero, relative gap is zero only if candidate is also zero, otherwise `None`.

## Public-code-only reproduction

This path needs no newly supplied verifier or historical ledger. The immutable public source URL below is derived from the code archive URL and member path in the documented release, not an invented dataset address.

```bash
PUBLIC=$(mktemp -d /tmp/mwfas-public-source-XXXXXXXX)
cd "$PUBLIC"
env -i PATH=/usr/bin:/bin HOME="$PUBLIC" /usr/bin/python3 -m venv venv
env -i PATH=/usr/bin:/bin HOME="$PUBLIC" venv/bin/python -I -c 'import urllib.request; urllib.request.urlretrieve("https://codeload.github.com/SoroushVahidi/mwfas-heuristic-metrics/tar.gz/d5fb6c885a6ae55b3d4d9c8acec98442f535a8b8", "code.tar.gz")'
# Verify before extraction:
printf '%s  %s\n' 6d2a65e8a2f0b6b1505b06fe75e42823c8d2f4295547c7c9db2c364a6af6d4c8 code.tar.gz | sha256sum -c -
tar -xzf code.tar.gz
env -i PATH=/usr/bin:/bin HOME="$PUBLIC" venv/bin/python -I -B \
  mwfas-heuristic-metrics-d5fb6c885a6ae55b3d4d9c8acec98442f535a8b8/release/public_reproducibility/anonymous_replay.py \
  --code-revision d5fb6c885a6ae55b3d4d9c8acec98442f535a8b8 \
  --data-revision 33902c7cc409794a43c17fc5428cf022f440da48 \
  --directory "$PUBLIC/replay"
```

## Scope and numerical rules

The independent interface intentionally supports the table45 simple directed, positive-integer, 1-based vertex contract. Self-loops and duplicate arcs are forbidden and rejected, not merged or removed. Empty and edgeless graphs and declared isolated vertices are supported. Noninteger, nonpositive, NaN and infinite weights are rejected. Other cohorts with label, annotation, multiplicity or loop-constant contracts require separate adapters.

Raw-file hashes, canonical weighted hashes and topology hashes are distinct. Canonical payloads use compact sorted-key JSON and the historical `mwfas-exp03-graph-v1` / `exp04-topology-v1` format markers, including every declared vertex. Raw integer objectives use zero tolerance. Existing numerical solver evidence uses the published criteria: bound difference < 0.5 integer unit, objective/bound decompositions < 1e−5, and MIP gap between 0 and 1e−7. These are not exact-arithmetic optimality proofs.

The official public replay additionally reproduces saved aggregate statistics and uses its own published numerical tolerances. No heuristic or solver is rerun by either workflow.
