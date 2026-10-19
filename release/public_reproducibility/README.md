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

The original 5,007-witness validation was **not repeated**. Packaging checked
transfer hashes against Slurm 1428278 and the accepted PR #53 corrected seal;
only the required new public replay rescored the released internal T4/T5 (printed Tables 6/7) witnesses.
Original EXP04 has 2,025 PASS records; EXP06 has 1,200 PASS and 198
CERTIFIED_OPTIMAL records, including 12 separate igraph IP cross-check tasks.
The runtime comparison reproduces original observations, with no cross-hardware
speed claim. Numerical solver evidence is not an exact mathematical proof.

## Current coverage and remaining work

Coverage is **2/10 numerical tables and 3/17 central claim groups**, counting the
previously public Wikimedia saved-objective group. [coverage.json](coverage.json)
preserves the other historical classifications. No metadata-only check is counted
as complete public graph/order replay. The manuscript availability statement was
updated only after the successful public replay.

| Priority/table | Current evidence and specific remaining delivery gap |
|---|---|
| Internal T1 / printed Table 3 inventory/joins | Public metadata reconstruction PASS: 416 weighted hashes, 317 topologies, 5,083 tasks; EXP07 matches 9 EXP03 + 36 EXP04, with no EXP06 overlap. Full byte coverage still needs 45 EXP03 inputs and 38 EXP05 inputs. Author EXP03 artifacts are in the accepted staging inventory; EXP05 needs exact SNAP/matrix-source retrieval and frozen transformations. |
| Internal T10 / printed Table 9 matched clock | Original effective 117-task archive located: 98 PASS, 19 TIMEOUT, 143,241 events; 160 first/best witnesses and 234 budget rows were already independently validated. `stage_exp28.py` archives originals and nanosecond file timestamps without rescoring. Public replay still needs this archive, the original INVALID/recovery lineage, and exact retrieval/transformation for CollegeMsg, Email-Eu-core, EXIOBASE and OpenFlights inputs. Only the nine synthetic input views are already in the new public package. No RASstar binary will be redistributed. |
| Internal T3 / printed Table 5 empirical inventory | PR #21 original 38-view inventory exists. Need the exact public source bytes/frozen transformations for four parents and graph-derived range checks. |
| Internal T6 / printed Table 8 empirical quality | PR #21 original complete-case statistics exist. Need original EXP05 orders/task records and source input retrieval to reproduce all 16 parent/comparator cells; retain incomplete pairs and separate derived recoveries. |
| Internal T9 / printed Table 12 reliability | Original 760-task inventory exists (639 PASS, 11 FAIL, 108 TIMEOUT, 2 SKIP). Need its public checkpoint/order evidence and the invalid/dependency classifications; metadata totals alone do not establish all statuses. |
| Internal T8 / printed Table 11 solver evidence | The 45 EXP07 references and original 20-certified/25-bounded classifications exist. Need public original solver/output records, historical heuristic selection witnesses, and byte-based comparisons of all regret/interval entries. Never relabel numerical certification as proof. |
| Internal T2 / printed Table 4 extension inventory | Existing public metadata provides 442 graph rows, 5,254 outcomes and 243 references. Full replay still needs the remaining cohort graph/order/source contracts; count arithmetic is not promoted to full byte replay. |
| Internal T7 / printed Table 10 additional sources | EXP12/13 audit outputs exist. Need 20 Ali inputs via pinned upstream downloads (no blanket collection redistribution grant), three empirical inputs via documented source-specific transformations, and original orders/status records. OpenFlights retains ODbL/contents terms; source-loop constants and the two IRS timeouts must remain explicit. |

These are remaining delivery/replay gaps, not evidence that the historical
experiments need replacement. **No targeted replacement experiment is proposed:**
no essential internal T4/T5 (printed Tables 6/7) evidence failed recovery, and the next original archive is
available. Any later unrecoverable source must be identified specifically before
proposing a new experiment. Historical bytes will never be regenerated and
represented as originals.

## Repository validation and orchestration

`uv run --locked pytest -q`: 17 passed, including toy-data failure checks for
invalid permutations, incomplete orders, duplicate arcs, altered summaries and
mismatched displayed cells. `python scripts/check_manifests.py`: PASS, including
paired project/provenance public revision pins and successful replay receipt.
The public implementation's release ledger also passes (42 files).

Draft PR: [#57](https://github.com/SoroushVahidi/mwfas-heuristic-metrics-data-paper/pull/57).
The manuscript repository remains private; no journal submission or unrelated
messages were sent. TMUX worker: `mwfas-public-release-20261019:0.0`. Operational
checkpoint, exact job command, private logs and subsequent archival-job status
are in the author-requested private orchestration directory. Large data, raw
orders, graphs and logs remain outside manuscript Git.

The next archival job is Slurm **1430243**, using packaging commit
`b637add351ee763b50c88e466f9726799168ca0d` on `n0093` (AMD EPYC 7763,
Python 3.12.3). It stages original EXP28 evidence privately and does not change
public Table 10 coverage. Its input manifest is
`639706bdcedcb02a89d1e145f62d65ca5072d738906bd0b1fe06d2c7d9611960`,
protocol is `c389a6ffd31b3fd66c8a868e6cf95e95a61414b3e12648655f37573c807e8310`,
and recovery provenance is
`cf4b162dea4139b4f929a581914244190466b71ef5540018dfa4ddc78f7f055c`.
The worker observes startup only and leaves completion inspection to a later
requested status turn; successful startup is not reported as completed work.

The manuscript PDF rebuilt successfully after the availability update, with
layout warnings only. Frozen internal T4/T5 (printed Tables 6/7) numerical contents are unchanged. The
public GitHub [versioned release](https://github.com/SoroushVahidi/mwfas-heuristic-metrics/releases/tag/table45-v2.0.0)
is published at the tested code revision; a subsequent metadata/documentation
commit `b530ab40d8c8d1d27054c4a992f3b4fea8bb838a` adds the replay receipt and
Table 1 metadata checker without changing the tested internal T4/T5 (printed Tables 6/7) verifier.
