# EXP09 external component pilot: validated results

**External pilot job `1424474`: completed and independently validated.**
Its immutable Wulver release is
`CUSTODY_PATH/f73ecde849ef72d2928fd7de2665388cb47f62cf`.
The job ran on `n0093` (`AMD EPYC 7763`) under `ikoutis/general/low`, one
CPU, 4 GB, with a three-hour allocation limit. Slurm recorded `COMPLETED`,
exit `0:0`, elapsed 00:02:05, and batch MaxRSS 38,232 KB. Startup spent much
of that wall time waiting on Wulver's project filesystem; the worker manifest
shows its actual 24-task campaign from 18:42:29 to 18:42:44 UTC on 2026-10-17
and 0.657 child CPU-seconds. Function-level wall times that include input
preparation and C execution ranged from 0.034 to 2.025 seconds (median
0.073 seconds), with early I/O delays inflating the longest values.

The frozen [12-graph pilot manifest](../../configs/exp09.json) has SHA-256
`d5332116e5db433a1a9e95dbfb0ca30ecc70cddb2c7301e5b38fb71509ef6cd9`.
The external source is the unmodified MIT-licensed Bader-Research repository
at `c30a6ac857c44e05833a8495781d97e2829deb44`; the GCC-built driver
SHA-256 on Wulver was
`778d5f40b5b99036c4233b564903090e711c6fcc7fa9e273602d63d1fc1b1230`.
The executable ran the repository's **serial C Okubo + Toposhuffle annealing
components**, not the complete JAX Rocket-Crane method. Its authored
functions were not changed. The 12 graph files matched frozen DIMACS and
weighted-graph hashes, and all prior source validation reports showed PASS.

The output manifest reports 24/24 PASS, zero failures, zero timeouts, one
recorded seed for each run, and an independently validated first-output
startup check. A separate stdlib audit reparsed the original DIMACS arcs,
external converted CSVs, native C outputs, saved orderings, and JSON records.
It verified all numeric vertices and ranks, graph and file hashes, original
weighted backward objective, native forward score, and DAG after backward
arc removal: **24/24 PASS**. The audit report in ignored
`data/cache/exp09/pilot-f73ecde/independent_validation_report.json` has
SHA-256 `f72f8d97d7b0ac32660da5e1c0ea481070cd2ce4d44184183db5f71e13408c3b`.
Raw Wulver evidence remains separate under
`CUSTODY_PATH/pilot-f73ecde` with job log
`CUSTODY_PATH/pilot-1424474.out`.
The raw `run_manifest.json` there has SHA-256
`e972b562d05c252cb92f8db20e2b5084d07b10f7e38e05dd13e8ad2b717472ee`.

## Objective comparison with previously validated results

The external value is the **better of two prespecified seeds**; the prior
reference is the best previously validated LR-TA, WMSF/L2, weighted Eades
where available, or IPSNS run at the source experiment's largest iteration
budget (EXP03/04: 400; EXP06: 200). These comparisons are valid weighted
objectives on identical graph hashes, but the algorithms have unequal budgets.
The frozen [prior-baseline snapshot](prior_baselines.json) has SHA-256
`7359b1f5e107d218a3be4f9afab55ed0b97db5df455da4eb58820a57a2b6524f`.
[`verify_prior.py`](verify_prior.py) checked its 69 selected, validated run
records against the hash-pinned original EXP03/04/06 Parquet exports listed
in [`prior_sources.json`](prior_sources.json), including all four certified
EXP06 exact records. The source validation reports and their hashes are also
recorded there. The source files remain at their original Wulver paths.
The relative column is `(external best − prior best) / prior best`; a positive
number is worse. The selected graphs are purposive, so the table is a
diagnostic sample rather than a population estimate.

| Graph | External seeds | Prior best | Relative difference | Exact optimum, if certified |
|---|---:|---:|---:|---:|
| EXP06 ER n12/k02 uniform | 150, 150 | 150 | 0.00% | 150 |
| EXP06 scale-free n12/k02 uniform | 115, 115 | 90 | +27.78% | 90 |
| EXP06 community n12/k02 uniform | 103, 125 | 103 | 0.00% | 103 |
| EXP06 ER n20/k04 capped lognormal | 467, 363 | 357 | +1.68% | 334 |
| EXP03 ER n60/k03 | 867, 915 | 775 | +11.87% | — |
| EXP03 scale-free n60/k04 | 904, 999 | 914 | **−1.09%** | — |
| EXP03 community n60/k06 | 3,352, 3,327 | 3,357 | **−0.89%** | — |
| EXP04 ER n120/k03 | 1,756, 1,951 | 1,389 | +26.42% | — |
| EXP04 scale-free n120/k03 | 521, 505 | 388 | +30.15% | — |
| EXP04 community n120/k08 | 10,331, 10,498 | 10,040 | +2.90% | — |
| EXP04 ER n240/k05 | 9,156, 9,957 | 7,763 | +17.94% | — |
| EXP04 community n480/k05 | 18,419, 18,155 | 15,624 | +16.20% | — |

Against the prior best on each graph, the component has **2 strict wins,
2 ties, and 8 losses**. Median relative deficit is **7.38%** across the 12
selected graphs. Against individual prior methods, its graph-level
win/tie/loss counts are LR-TA **5/1/6**, WMSF/L2 **6/1/5**, weighted Eades
**6/1/2 on 9 available graphs**, and IPSNS **2/2/8**. EXP03 has no earlier
weighted Eades result. Ten of twelve graphs have different final objectives
between external seeds; all twelve have different final ordering hashes.
These two-seed ranges describe observed variability without supporting a
general stochastic-performance claim.

For the four certified EXP06 cases, the component's **best-seed exact relative
gaps** are 0%, 27.78%, 0%, and 8.68% in table order. Two matches are genuine
certified optima; the other two are validated feasible orderings. No
uncertified best-known objective is called an optimum.

## Same-node insertion comparison

The separate insertion comparison job `1424484` used copies of validated
EXP03/04/06 LR-TA and WMSF orderings on the same 12 graphs. Its immutable
release is `523d73f76d0cd40b60c6f75e33e3065dc920c3f0` and its output is
`CUSTODY_PATH/insertion-523d73f`. Slurm
recorded `COMPLETED`, exit `0:0`, elapsed 00:02:11, batch MaxRSS 27,192 KB,
and host `n0093` (the same host as the external pilot). The task manifest
records 24/24 PASS, zero failures and censoring, with 7.153 child CPU-seconds.
Each run preserved a copied seed ordering, validated its source objective,
and saved the final ordering and task checkpoint. The independent
[`analyze.py`](analyze.py) reparsed the original weighted graph and both CSV
orderings, checked source and output hashes, complete numeric vertex coverage,
backward weights, acyclicity, and nonincreasing objective: **24/24 PASS**.
No EXP05 production artifact was used or modified. The insertion job log is
`CUSTODY_PATH/insertion-1424484.out`.
Its raw `run_manifest.json` has SHA-256
`de1630ee19d8cadb331a6365d8df9bbda44bc5f1c839e2680006462aa8dbe8f8`.

| Graph | External best | Insertion from LR-TA | Insertion from WMSF/L2 | Best verified after comparison | External relative deficit |
|---|---:|---:|---:|---:|---:|
| EXP06 ER n12/k02 uniform | 150 | 150 | 210 | 150 | 0.00% |
| EXP06 scale-free n12/k02 uniform | 115 | 90 | 90 | 90 | 27.78% |
| EXP06 community n12/k02 uniform | 103 | 103 | 103 | 103 | 0.00% |
| EXP06 ER n20/k04 capped lognormal | 363 | 377 | 352 | 352 | 3.13% |
| EXP03 ER n60/k03 | 867 | 762 | 779 | 762 | 13.78% |
| EXP03 scale-free n60/k04 | 904 | 856 | 922 | 856 | 5.61% |
| EXP03 community n60/k06 | 3,327 | 3,193 | 3,272 | 3,193 | 4.20% |
| EXP04 ER n120/k03 | 1,756 | 1,502 | 1,513 | 1,389 | 26.42% |
| EXP04 scale-free n120/k03 | 505 | 388 | 388 | 388 | 30.15% |
| EXP04 community n120/k08 | 10,331 | 10,121 | 10,264 | 10,040 | 2.90% |
| EXP04 ER n240/k05 | 9,156 | 7,913 | 8,214 | 7,763 | 17.94% |
| EXP04 community n480/k05 | 18,155 | 16,130 | 16,899 | 15,624 | 16.20% |

Against the best insertion output per graph, the external component has
**0 wins, 2 ties, and 10 losses**. The same counts hold against the best
verified objective across historical and pilot methods. Its median relative
deficit against that latter reference is **9.69%**. A prespecified-seed,
graph-unit bootstrap of this median gives a descriptive resampling interval
of **3.01%–22.18%**; purposive graph selection means it is not a population
confidence interval. In particular, the two historical wins on the EXP03
scale-free and community graphs vanish after insertion refinement.
The independent combined analysis JSON in ignored
`data/cache/exp09/comparison-final.json` has SHA-256
`8a74169e269b865ffb5e11164f477529026401f85c22908bd4c4febeccb70e5f`.

Median task wall time was 0.014 seconds for insertion (range 0.003–2.911)
and 0.073 seconds for the external component (range 0.034–2.025). These
both include initialization and filesystem effects. Although both jobs ran
on the same host, they used different code, iteration budgets, and task
startup conditions; the numbers describe execution cost under these pilot
settings, not intrinsic speed rankings. Historical EXP03/04/06 runtimes were
recorded on other environments and are not used for a controlled timing claim.

## Production gate

[A fully specified conditional production proposal](../../configs/exp09_production_proposal.json)
identifies the exact 378 existing EXP03/04/06 weighted graphs through pinned
manifest SHA-256 values and every manifest row's graph IDs and hashes. It
uses two seeds, one CPU, 4 GB, an eight-hour maximum allocation, 30 seconds
per run, and a 22,680 CPU-second hard ceiling, with graph-level statistical
grouping and independent validation. **Its pilot gate failed:** only 2/12
strict wins against prior best, no wins against insertion, and a 9.69% median
deficit against the best verified pilot reference. No production job was
launched. A larger
benchmark of the complete Rocket-Crane method would require first establishing
a faithful, bounded JAX/Crane workflow and independently validating its
outputs; this component-only pilot does not supply that evidence.
