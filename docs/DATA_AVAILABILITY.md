# Data availability and objective reproduction

## Public now

1. The [pinned original Hugging Face release](https://huggingface.co/datasets/SoroushVahidi/mwfas-heuristic-metrics/tree/5b6cd5620ca0a1c9b3be5e8d996bf8e3c467e79f) contains 7,371 historical rows in 14 configurations. This repository has hash manifests, retrieval code and baseline checks for those files, without copying the files.
2. [Ali's pinned collection](https://github.com/alidasdan/graph-benchmarks/tree/77e5b8b4f1e1a1b8e80cfb9430f90492ffee3675) provides 20 exact source graph references. Their redistribution rights remain unverified.
3. The author's [historical Wikimedia workspace](https://github.com/SoroushVahidi/feedback-arc-set-paper-workspace/tree/975b287feb77e14340af99ba391f6b3e1656d5be/datasets) provides three derived graph references and ten saved order references. These 13 files belong to one clickstream source parent. Their hashes are recorded, but this repository does not redistribute them.

Use `python release/verify_public_refs.py --offline` for structural checks; select an `--artifact-id` for independent network retrieval and byte verification. The script checks size and SHA-256 in memory and does not save source bytes.

## Limits

The original Hugging Face release does not contain the historical graph or order inputs needed to recompute every original objective. The baseline auditor can check row counts, metadata, duplicate patterns, arithmetic and aggregate construction where public table fields permit; it reports `NOT_VERIFIABLE` where inputs are missing. Existing `FAIL` findings and original incomplete or timed-out statuses are retained.

The later audited benchmark extension and its private metadata candidate are **not in this repository**. In particular, this repository does not provide a public route to every graph/order witness behind the central manuscript results. Some source-derived objectives can be checked from their independently accessible pinned bytes and contracts; full objective reproduction remains limited until exact source or rights-cleared derived graphs, saved orders, schemas and a durable public or reviewer route are released. No missing original input is reconstructed by substituting a newer file.

The three historical Wikimedia graph bytes are pinned derived artifacts. The pre-May 2026 monthly TSV snapshots used to construct them have not been recovered; objective rescoring from the derived graph is a different claim from reproducing its source transformation. Solver-certified optima are numerical certificates under recorded settings, not exact-arithmetic proofs. Time-limited bounded cases stay bounded. The audited 442 extension index rows are contract-scoped observations, not 442 globally unique graph inputs.

No extension DOI, complete public objective witness set or JDSA article DOI is asserted here.
