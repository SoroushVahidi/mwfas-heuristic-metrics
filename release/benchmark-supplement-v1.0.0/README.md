# MWFAS benchmark supplementary release — benchmark-supplement-v1.0.0

Public verification code, optional benchmark profiles, diversity metadata and saved-output witnesses supporting *An Audited Benchmark Dataset for Reproducible Evaluation of Minimum Weighted Feedback Arc Set Heuristics*. This release does not assert journal acceptance or publication. No new optimization campaign was run and no manuscript result was changed.

* [Public code and instructions](https://github.com/SoroushVahidi/mwfas-heuristic-metrics/tree/benchmark-supplement-v1.0.0/release/benchmark-supplement-v1.0.0)
* [Data, checksums and downloadable packages](https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/tree/benchmark-supplement-v1.0.0/releases/benchmark-supplement-v1.0.0)
* Full archive: `benchmark-supplement-v1.0.0.tar.gz`; code/metadata archive: `benchmark-supplement-v1.0.0-code.tar.gz`.
* `PUBLIC_FILE_INVENTORY.tsv` lists every payload file and SHA-256. `supplementary-evidence/FILE_DISPOSITIONS.tsv` additionally identifies every logical original witness, storage hash, original hash, license and release category. `EXTERNAL_REFERENCE_FILES.tsv` and `WITHHELD_FILES.tsv` identify exact exceptions.

## What is released

1. Candidate-order interface, command line, 19 tests, public example input/order and independent full table45 audit. It verifies complete permutations and exact integer backward weight; the default reference is best saved feasible, not an optimality certificate.
2. Original 34-record `table45_core` and 47-record `existing_source_diverse` manifests, deterministic selection logic, hashes, parents, weights and source recipes. Profile selection is optional; it does not redefine the scientific experiments.
3. All 442 structural/weight descriptor rows, methods and independent validation evidence. New `metadata/graphs-v1.1.csv` fills 23 previously blank topology hashes (20 EXP12, three EXP13); all were recomputed from original graph bytes with two parsers. Historical metadata is preserved.
4. EXP29's 90 selected original-v1 task witnesses (45 pairs), EXP30's 12 selected observations/24 horizon values, full original and selected status histories, controllers, checkpoints and complete event orders. 203 EXP29 and 17,860 EXP30 event-order checks reproduce the existing findings. The failed full EXP29 campaign remains failed, and EXP30's v1/v2 provenance remains separate.
5. The 37-view EXP05 deterministic cohort's 185 orders and source evidence, reproducing supplementary S3 together with EXP29 S1 and EXP30 S2. All 77 eligible graph identities from the 84-graph witness package are included; seven SNAP graph views and associated source representations are reconstructed upstream.
6. An attributed OpenFlights graph view under its separate ODbL/DbCL license, in addition to the EXIOBASE-derived CC BY and U.S. government-source views. The 47-record profile can resolve all inputs; its 8 upstream-only entries are three SNAP views and five Ali collection inputs.

## Local reproduction

Requires Python 3.12; supplementary replay additionally requires NumPy. No optimizer, original-author binary, proprietary solver, hosted CI or private file is needed. Internet is needed only for explicit downloads; full supplementary verification then runs with network/process creation denied.

Download the archives and compare them with `ARCHIVE_SHA256SUMS` in the release directory before extracting. Extract into a fresh working directory. Verify distributed bytes with `sha256sum -c SHA256SUMS`.

### Candidate order and table45

```sh
BUNDLE=/absolute/path/to/benchmark-supplement-v1.0.0
REPLAY=$(mktemp -d)
cd "$REPLAY"
bash "$BUNDLE/INDEPENDENT_VERIFIER_SOURCE/run_clean.sh" "$BUNDLE"
python "$BUNDLE/INDEPENDENT_VERIFIER_SOURCE/check_candidate.py" "$REPLAY/table45" exp04/exp04_cm_n120_k03_r01 "$BUNDLE/examples/candidate.csv"
```

The last command uses the example's matching instance (see examples/README.md); replace the CSV with your algorithm's complete permutation. `REPRODUCTION_INSTRUCTIONS.md` documents the Python API, format, numerical rules and all outputs. `run_clean.sh` independently checks all 333 graphs and 3,423 saved outcomes with zero-tolerance integer rescoring. It does not rerun an algorithm.

### Profiles

```sh
python profile_tools/resolve_profiles.py /fresh/profile-output
```

Each of the 47 distinct inputs must match raw, weighted and labeled-topology hashes, n and m. Reuse existing public inputs; source-only rows use exact upstream URLs/commits/checksums/transformations. The candidate-order interface supports table45's contract only; the resolver separately handles Ali annotations and Wikimedia UTF-8 labels.

To reproduce selection, copy `diversity/` and run `python scripts/analyze_coverage.py .` from the copy. Both manifests, profile weights, bins and assessments reproduce byte for byte. Full feature recomputation needs the per-record graph input map; descriptors are published for all 442 rows, while the profile resolver intentionally resolves the 47 selected inputs, not every broader input. Historical local evidence paths are descriptive custody identifiers, not runtime dependencies.

### Supplementary Tables S1–S3

```sh
cd supplementary-evidence
python protocol/hydrate_external.py /absolute/path/outside-package/snap-cache
python -B verification/guarded_verify.py > ../supplementary-verification.json
python -B verification/verify.py --tables-dir /absolute/path/outside-package/regenerated-tables > ../table-verification.json
```

Hydration anonymously downloads three SNAP sources, checks source hashes, and recreates seven graphs, seven node maps and two logical converted inputs (15 unique objects). It changes only the extracted working copy by adding explicitly listed external objects. It cannot change an already published payload or silently substitute a graph. `guarded_verify.py` verifies the entire payload, all selected event orders/status/lineage, all 185 EXP05 orders and exact S1–S3 rows. A PASS is saved-output reproduction, not cryptographic timestamp authentication or a successful full-campaign rerun.

## License and availability boundaries

Author code is MIT and author data/documentation CC BY 4.0; see LICENSES.md for exact component scope, attribution and the ODbL exception. SNAP and Ali input bytes without established redistribution grants remain upstream references. RASstar original-author source/executable and proprietary solvers are not redistributed; binary/source identities are retained where relevant. No credentials, correspondence or unpublished personal microdata are included. Historical sanitized receipts retain their original-vs-storage hash bridges and dated private/pending labels.

This release does not recover unavailable original 7,371-row historical graph/order bytes or pre-May-2026 Wikimedia source snapshots. It does not change the old 11/17 claim-group denominator. Full nonselected EXP29 event trees are not certified by the selected-arm replay; their status history is preserved. The manuscript itself is unchanged; proposed availability updates are listed in MANUSCRIPT_AVAILABILITY_MAPPING.md.

## Code-only checkout

This GitHub directory contains code, profile metadata, small licensed examples and table expectations. Download the full Hugging Face archive for the content-addressed supplementary witnesses and execute the supplementary replay from that full extraction. The profile resolver works from either distribution, using upstream reconstruction when a graph object is not bundled.
