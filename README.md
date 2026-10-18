# MWFAS Heuristic Metrics: public reference and validation package

**Research author: Soroush Vahidi.** This independent repository provides original validation code, baseline audit metadata, schemas and hash-checked references for the MWFAS Heuristic Metrics research program. It has a new Git history and contains no private experimental evidence or raw historical research graphs.

## What is available

- A pinned [Hugging Face dataset](https://huggingface.co/datasets/SoroushVahidi/mwfas-heuristic-metrics/tree/5b6cd5620ca0a1c9b3be5e8d996bf8e3c467e79f) with 7,371 historical rows in 14 configurations. Its own license covers creator-controlled metrics and metadata. Original historical graph and ordering inputs are absent from that release.
- `src/mwfas_data/` contains a DIMACS reader, backward-arc and acyclicity checks, pinned retrieval and dataset audit code. The audit reports `PASS`, `FAIL`, or `NOT_VERIFIABLE` without changing rows or filling missing inputs. The committed baseline validation includes its original failures and unavailable checks.
- `release/public_reference_manifest.csv` names 62 pinned, public byte references: 29 original dataset files, 20 Ali graph files, and 13 historical Wikimedia-derived files (three graphs and ten saved orderings). These are references, not 62 independent graphs or a copy of their bytes. `release/verify_public_refs.py` validates the list offline or checks remotely retrieved bytes in memory.
- `configs/`, `data/manifests/`, and `docs/` describe the original baseline, source parents, provenance, rights and access limits.

## Quick checks

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/). From the repository root:

```sh
uv run --locked pytest -q
python scripts/check_manifests.py
python release/verify_public_refs.py --offline
python release/verify_public_refs.py --artifact-id 'ALI:core-bad/bad1.d'
```

To audit the original public dataset, run `uv run --locked mwfas-data fetch` and then `uv run --locked mwfas-data audit`. Downloads go to ignored `data/cache/`; the audit report goes to ignored `results/`. The audit retains original failed and incomplete statuses. It does not rerun optimization. The small `scripts/run_exp01_smoke.py` adapter can check a pinned upstream implementation on the included synthetic test graph, with five IPSNS iterations and a 30 second timeout per method; see [reproducibility](docs/REPRODUCIBILITY.md).

## Scientific limits

The audited later extension indexed 442 graph rows under specific contracts; this is **not** a count of globally unique graph inputs. Views, paired weights and runs can share a topology or source parent. The later numerical solver certificates are numerical, not exact-arithmetic proofs; time-limited cases remain bounded rather than certified. This repository does not publish the later extension tables, raw solver logs, or a complete central objective witness set. Historical Wikimedia-derived graph and order bytes are pinned in a separate public workspace, but their pre-May 2026 monthly source TSV snapshots remain unavailable. See [data availability](docs/DATA_AVAILABILITY.md) for the exact reproduction boundary.

## Sources, rights and citation

The pinned [algorithm source repository](https://github.com/SoroushVahidi/minimum-weighted-fas-heuristics/tree/40209c26966247d9bf9ad34764de4ac4181f98c2), [Ali benchmark source](https://github.com/alidasdan/graph-benchmarks/tree/77e5b8b4f1e1a1b8e80cfb9430f90492ffee3675), and [historical Wikimedia-derived artifact workspace](https://github.com/SoroushVahidi/feedback-arc-set-paper-workspace/tree/975b287feb77e14340af99ba391f6b3e1656d5be/datasets) are external links, each with its own rights. [Source attribution](docs/SOURCE_ATTRIBUTION.md) records their roles. [License scope](LICENSE_SCOPE.md) assigns MIT to verified original code and CC BY 4.0 to verified author-controlled metadata and documentation; third-party bytes keep their own terms.

Cite Soroush Vahidi's original **MWFAS Heuristic Metrics** dataset at its pinned Hugging Face revision when using those data, and cite this repository's versioned release for its software and reference checks. [CITATION.cff](CITATION.cff) supplies machine-readable details. The eventual JDSA benchmark paper should be cited **only after it is published**; no manuscript DOI is assigned here. The prior [ranking article](https://doi.org/10.1007/s11227-026-08852-4) establishes related ranking–MWFAS results and is distinct from this benchmark package.

The local release ledger can be checked with `python release/verify_package.py` and `sha256sum -c release/CHECKSUMS.sha256`.
