# Printed Table 9 and Figure 2: EXP28 public replay

The release preserves 117 effective task identities on 13 reused graph views:
98 PASS and 19 TIMEOUT, with 143,241 original event/order references. Both IPSNS
seeds and the separate RASstar single-run and restart arms remain distinguishable.
The two horizons are observations of the same task, not independent experiments.
Public-only replay status and immutable pins are recorded in `exp28_publication.json`.
Publication or transfer integrity alone does not establish numerical reproduction.

## Numbering

Internal T4 = printed Table 6; internal T5 = printed Table 7; internal T10_EXP28 =
printed Table 9 (`tab:exp28-matched`). Figure 2 is `fig:exp28-anytime`.
`table_number_mapping.json` maps all ten numerical tables by manuscript labels.
The two preceding provenance tables explain part of the historical numbering
shift. The existing `releases/table45-v2-20261019` path is deliberately retained.

## Public artifacts and extraction

The existing Hugging Face dataset is `SoroushVahidi/mwfas-benchmark-extension`;
the new path is `releases/exp28-v1-20261019`. Use the full immutable revisions in
the publication receipt, not a moving branch. Existing releases are unchanged.

* `exp28-light.tar.gz`: all event metadata and nanosecond publication evidence,
  160 distinct first/best complete orders covering all 234 task/horizon rows,
  nine synthetic inputs, original checkpoints, protocol, original and effective
  selection evidence, frozen numerical references, and a SHA-256 file manifest.
* `exp28-full.tar.gz`: 286,750 original permitted files, including every original
  event and complete order. The four empirical graph files are intentionally
  retrieved and transformed from pinned upstream bytes by executable code.
* `full_inventory.csv.gz`: exact member names, byte hashes/sizes, source nanosecond
  timestamps, artifact kinds and release scope. It omits the private transfer
  inventory's redundant storage-location column. Archived bytes are unchanged.
* `package_receipt.json`: hashes for both archives and the compressed inventory.

Verify the receipt hashes before extraction. The lightweight archive extracts to
`exp28/`; extract the full archive into a separate new directory. The anonymous
runner validates paths and refuses symlinks, devices, and directory escapes.
Full replay streams the larger archive; it need not create 286,750 local files.
Original absolute paths in frozen metadata are inert provenance, never inputs.
No process logs, credentials, correspondence, RASstar binary, or empirical graph
bytes are included. Full original private staging is retained unchanged; its hash
is `1332cbacf81ad954dff853810687f4bb4a469966ca5639a913f104b8f80fe7f3`.

## Anonymous verification

Download `anonymous_exp28.py` from the pinned public GitHub verifier revision.
Run with Python 3.12, replacing the two revision placeholders from the receipt:

```bash
env -i PATH=/usr/bin:/bin HOME=/tmp/mwfas-exp28-anonymous \
  python3 -I -B anonymous_exp28.py \
  --code-revision FULL_PUBLIC_CODE_COMMIT \
  --data-revision FULL_PUBLIC_DATASET_COMMIT \
  --directory /tmp/mwfas-exp28-new --full
```

The destination must not exist. No private inputs, credentials, old data cache,
or optimization software are used. The runner freshly downloads public code,
data, and upstream inputs, rejects file access outside its clean directory and
system libraries, and forbids subprocesses. The recorded validation additionally
uses an independent OS file-access trace. Those are evidence of that execution,
not a claim of container isolation or universally secure sandboxing.

The full mode checks all 143,241 order references, complete permutations,
weighted backward-arc objectives and DAGs, every original file hash, all 117
statuses, deterministic restart seeds, source graph identities and both horizon
eligibility tests. Identical graph/order encodings may share a cached independent
score; every reference is still checked. The lightweight mode rescans all events
and scores the 160 first/best witnesses used by the manuscript. It reproduces
all 234 budget rows and 182 paired rows, exact wins/ties/losses and normalized
effects, the frozen integration statistics (10,000 bootstrap draws, seed 28),
20 displayed numerical Table 9 cells, and all 26 Figure 2 coordinates.

Table 9's W/T/L triplet is one displayed cell containing three counts. Slash
budgets are checked separately and combined only if every paired objective agrees.
Figure data retain graph/family identity, both horizons, integer objectives and
total weights. The frozen figure PDF and original generator are included for
comparison; recreating its rendering additionally needs Matplotlib 3.10.9.

## Exact empirical sources and attribution

`exp28_sources.json` lists every upstream URL and SHA-256. All four reconstructed
graphs must match the exact historical DIMACS byte hashes; changed upstream bytes
cause NOT VERIFIABLE, with no fallback to a newer source or different instance.

| Parent | Original transformation and public access boundary |
|---|---|
| CollegeMsg | SNAP temporal file; inclusive first 90 days from its minimum timestamp; sum directed message multiplicities; sorted integer labels. Credit Panzarasa, Opsahl and Carley (2009) and SNAP's parsed Opsahl source. [Publisher](https://snap.stanford.edu/data/CollegeMsg.html) supplies citations but no explicit redistribution grant was established. Download upstream only. |
| Email-Eu-core | SNAP static file; unit-weight distinct arcs, remove loops, largest nontrivial SCC with deterministic tie-breaking, sorted integer labels. Credit Yin, Benson, Leskovec and Gleich (2017) and the [SNAP publisher](https://snap.stanford.edu/data/email-Eu-core.html). Software BSD terms do not license the dataset; download upstream only. |
| EXIOBASE LOP benchmark | Exact `exiobase.zip`, record 20554376 version 0.0.1, member `exiobase/os300/os300_us_2022_n300`; positive row-major off-diagonal integers become arcs, omit zeros and diagonal. Credit Fagiolo, Baioletti and Santucci's benchmark; the [Zenodo record](https://zenodo.org/records/20554376) lists depositor `2F` and CC BY 4.0. This is a specific LOP benchmark, not an interchangeable EXIOBASE release. Retrieve the archive upstream and indicate the graph conversion. |
| OpenFlights | `routes.dat` and `airports.dat` at Git commit `56a3cce4d50309cb79948103a48c7f87d09b3056`; known U.S. domestic nonstop endpoints; count directed route records, remove loops; lexicographically sort `airport:<integer>` labels exactly as original. Credit OpenFlights/contributors and Airline Route Mapper. [Publisher terms](https://openflights.org/data#license) specify ODbL and Database Contents License; no raw/derived graph is mirrored here. |

Source terms were checked on 2026-10-19. Executable transformations are shared
building blocks for later printed Tables 5/8/12; this release makes no claim to
have recovered all of EXP05. Author-owned outputs/metadata are CC BY 4.0 and
author-written code is MIT. These grants do not extend to upstream material.

## Historical recovery and execution context

The source revision is `a9aaa322b7d2446796e6b13406a67554661ca144`, with unchanged
protocol `c389a6ffd31b3fd66c8a868e6cf95e95a61414b3e12648655f37573c807e8310`.
Original task 35 exceeded its 120-second cap by 0.04519767698366 seconds and
remains INVALID in the preserved original checkpoint/audit. Selection uses 116
original valid tasks and the explicitly declared replacement, a TIMEOUT with a
valid predeadline incumbent. Its exact identity and both checkpoint hashes are
verified; no historical status is rewritten. Completed archival job 1430243 is
not resubmitted, and the earlier 5,007-order audit is not repeated.

Publication time is reconstructed from original filesystem `mtime_ns`, captured
by that completed archival job, as well as event/controller clocks. Those times
are historical filesystem evidence, not independent cryptographic timestamps.
All records must satisfy the original monotonic cap and actual publication cap.
The original array ran on n0042/n0043/n0038/n0052 and recovery on n0012. The
manifest's login-node CPU is not verified per-task compute hardware. Runtime
values remain original observations and establish no cross-hardware speed claim.

`exp28_original/source_manifest.json` seals unchanged controller, worker,
instrumented IPSNS, protocol, independent auditor and adapter dependency source
files, each tied to its original revision. These are execution-provenance
snapshots; saved-output replay does not execute them. Baseline IPSNS is separately
pinned at `40209c26966247d9bf9ad34764de4ac4181f98c2`.

The original-author RASstar executable is excluded. Obtain the [pinned original
source](https://github.com/forgottencsc/FindingSmallFeedbackArcSetOnLargeGraphs/tree/8340e1633ba9290a567a882aff4d74f01b38102d)
separately, retaining its terms. Its readme documents compilation from `src` with
`g++ -O3 -Iinclude fas_alg.cpp -o fas_alg` and the compatible invocation
`fas_alg input.w W RASstar -r 1 -p -o rank.txt`. The `W` input has header `n m`
and zero-based `u v weight` records; original weights are preserved (no `-w`).
Output is a zero-based rank per vertex. Restart index i>0 uses
`1 + ((seed*1000003 + i*104729) % 2147483646)`. This documents compatibility;
no new algorithm run, benchmark, or journal submission is part of this release.
