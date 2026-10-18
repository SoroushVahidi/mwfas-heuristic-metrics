# Reproducibility guide

## Environment and local checks

Use Python 3.12 and `uv`. The dependency versions are frozen in `uv.lock`. Run `uv run --locked pytest -q`, `python scripts/check_manifests.py`, and `python release/verify_public_refs.py --offline`. These commands use the package's included code and metadata and do not run optimization. The committed initial validation is historical evidence; a fresh audit can reach the same reported findings only when the pinned public dataset files are fetched.

## Original dataset audit

Run `uv run --locked mwfas-data fetch` to download the pinned 29 Hugging Face files into ignored `data/cache/hf/` after checking their SHA-256 values. Run `uv run --locked mwfas-data audit` to write `results/baseline_validation.json`. Read each check's `PASS`, `FAIL`, or `NOT_VERIFIABLE` status; a `FAIL` is a reported discrepancy, not an instruction to change published rows. The audit cannot validate graph/order objectives without those historical bytes.

## Public source references

`release/public_reference_manifest.csv` records artifact ID, kind, source parent, exact revision, URL, size, SHA-256, rights status and upstream reconstruction status. `python release/verify_public_refs.py --artifact-id 'ALI:core-bad/bad1.d'` independently retrieves one referenced file and checks its hash in memory. `--all` checks all 62 and may download large graph/order files; it is optional. Public availability can change after this release.

## Bounded method smoke check

The original method source is a separate [public repository](https://github.com/SoroushVahidi/minimum-weighted-fas-heuristics/tree/40209c26966247d9bf9ad34764de4ac4181f98c2). `uv run --locked python scripts/fetch_public_source.py` checks out that exact revision under ignored `data/cache/source/`. Then `uv run --locked python scripts/run_exp01_smoke.py --source data/cache/source` invokes the original implementation on the included three-node fixture, with five IPSNS iterations and a 30 second per-method timeout. The adapter records seed, source revision, input hash, command, wall time, objective and validation status under ignored `results/exp01_smoke/`. This is a small integration check, not a benchmark or a new scientific result. Record machine and software details before comparing runtimes across hosts.

For central manuscript objective reproduction, use the exact graph and order witnesses identified by the underlying audit, where publicly available and rights-cleared. This package does not claim to contain that complete witness set; see [data availability](DATA_AVAILABILITY.md).
