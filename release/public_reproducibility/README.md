# Public reproducibility release checkpoint

Internal **T4 and T5 (printed Tables 6 and 7) are PUBLIC_REPLAYABLE**. A new clean anonymous replay on
2026-10-19 passed every displayed entry: **41 cells, including 34 numeric cells**.
It recomputed 3,423 saved ordering objectives on 333 graph files, reconstructed
all original task classifications, verified 99 EXP06 topology pairs and 210
numerical solver evidence records, and reproduced original aggregation and
2,000-replicate bootstrap statistics (seed 20261017). This is saved-output
numerical reproduction, not a stochastic optimization rerun or an exact solver
proof. No optimizer or new benchmark was run.

The historical archive path `releases/table45-v2-20261019` and filenames retain internal numbering. See [the label-verified mapping](table_number_mapping.json) and [EXP28 delivery](EXP28.md) for printed Table 9 / Figure 2.

## Immutable public delivery

- Dataset: [benchmark extension, revision 33902c7](https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/tree/33902c7cc409794a43c17fc5428cf022f440da48/releases/table45-v2-20261019), tag `table45-v2.0.0`.
- Independent code: [revision d5fb6c8](https://github.com/SoroushVahidi/mwfas-heuristic-metrics/tree/d5fb6c885a6ae55b3d4d9c8acec98442f535a8b8/release/public_reproducibility).
- Public replay receipt and every displayed-cell comparison: [revision b66ce13](https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/tree/b66ce13298467a1f0b4928d55a7440e6ab948cb6/releases/table45-v2-20261019/replay).
- Dataset tar SHA-256: `b74e37bed3a91ec986fe8526a73f5a990a144ca931ee013cc1a8fe4f882f3e2d`.
- Inner manifest SHA-256: `ab67aee168229b4ae19394732a7a3dedf4761b7e1e3ef75983e3028a56e41b51`.

The archive contains 7,476 hash-listed files; historical source files remain
byte-for-byte unchanged. Author-generated inputs,
orders and experimental metadata are CC BY 4.0; original author code is MIT.
The public package has full license texts, per-file source/checksum/license
records, original seed/budget/config/selection/runtime records, original runner
dependency closures, original statistical sources and the unchanged PR #22
28-file reference package. External software is linked/installed separately;
no unlicensed third-party implementation is bundled. Historical public releases
and original private provenance remain intact.

## Independent replay

Download `anonymous_replay.py` from the linked immutable code revision, then:

```bash
env -i PATH=/usr/bin:/bin HOME=/tmp/mwfas-anonymous \
  python3 -I -B anonymous_replay.py \
  --code-revision d5fb6c885a6ae55b3d4d9c8acec98442f535a8b8 \
  --data-revision 33902c7cc409794a43c17fc5428cf022f440da48 \
  --directory /tmp/mwfas-table45-new
```

The destination must be new. Python 3.12 standard library suffices. Expected
output: PASS; 333 graphs; 3,423 orders/tasks; 99 topology pairs; 210 solver records;
41 displayed cells; printed Tables 6 and 7 PUBLIC_REPLAYABLE. The test freshly downloads
only the pinned public GitHub/HF archives. A file-read guard rejects private
inputs and subprocesses. Original absolute paths in metadata are never opened.
The observed run took 14.03 seconds; its OS file-access trace found **zero**
private input paths outside the fresh directory among 7,732 unique absolute file
opens. Local container isolation was unavailable, so guard enforcement and the
independent system-call trace were both used. Trace/logs remain ignored/private;
a path-redacted receipt is committed and published, with its original receipt
hash retained. The trace is evidence of this run, not a general sandbox claim.

The original 5,007-witness validation was **not repeated**. EXP28 was separately replayed from newly published public evidence; that is not a repeat of the prior private audit. Packaging checked
transfer hashes against Slurm 1428278 and the accepted PR #53 corrected seal;
only the required new public replay rescored the released internal T4/T5 (printed Tables 6/7) witnesses.
Original EXP04 has 2,025 PASS records; EXP06 has 1,200 PASS and 198
CERTIFIED_OPTIMAL records, including 12 separate igraph IP cross-check tasks.
The runtime comparison reproduces original observations, with no cross-hardware
speed claim. Numerical solver evidence is not an exact mathematical proof.

## Current coverage and remaining work

Coverage is **10/10 numerical tables and 11/17 central claim groups**. All printed
numerical tables (3–12) now have complete public replay. The remaining six claim
groups retain their historical classifications in [coverage.json](coverage.json);
table coverage does not establish historical Hugging Face graph identity or all
broader research-question claims.

The [remaining-table dataset](https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/tree/667e164d0768d635a73692cd594801f10fe12382/releases/remaining-v1-20261019) and [tested verifier](https://github.com/SoroushVahidi/mwfas-heuristic-metrics/tree/4a89ffe5d0b8d9a0510ac0e715b9baef84e3c62f/release/public_reproducibility/remaining) reproduce printed
Tables 3, 4, 5, 8, 10, 11 and 12. Four fresh anonymous Slurm replays passed;
[receipts and instructions](remaining/README.md) record exact identities, original
statuses, numerical comparisons, source downloads and isolation checks. The
previously validated EXP04/06 and EXP28 immutable releases remain unchanged.

Validation outputs and receipts: [immutable dataset revision 117cd82](https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/tree/117cd82e5b863238377c5effe7430ce771062cf4/releases/remaining-v1-20261019).
