# Independent table45 verifier

Python 3.12 standard library only. Start with `../REPRODUCTION_INSTRUCTIONS.md` and `run_clean.sh`. The graph/order/objective library is `mwfas_benchmark.py`; it does not import any original benchmark code or need a private path. `usage_example.py` evaluates a trivial candidate on a public graph.

- `download.py`: anonymous immutable archive downloads, checksums, safe extraction, file-access guard.
- `verify_release.py`: complete manifest/identity/outcome/reference audit against supplied historical metadata.
- `test_verifier.py`: 19 tests, including 384 exhaustive small-graph/order combinations.
- `run_guarded.py`: isolated script execution with an allowed-file receipt.
- `run_clean.sh`: fresh-environment end-to-end execution.

Exact objective arithmetic is Python integer arithmetic. Canonical hash serialization follows the historical public contract. Numerical solver consistency is not an exact optimality proof. Scope is table45; incompatible graph contracts are rejected, not normalized silently.

The code is public under MIT in benchmark-supplement-v1.0.0.
