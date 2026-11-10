# EXP24 independent controlled-time pilot analysis

Analysis on the frozen EXP11/EXP22 outputs, 18 October 2026. This is a **private metadata-only report**. No original graph, ordering, Xiong source/binary, Wulver absolute path, or historical failed artifact is committed. The analysis starts from PR #34 commit `82152ad9c2e859277dc2a1ae0a141155bf0567cd`, uses the EXP11 frozen protocol, and does not modify any original output. The current EXP23 manuscript/PDF remain unchanged.

## Evidence and independent checks

| Source | Slurm job and terminal state | Sealed audit result | Disposition |
|---|---|---|---|
| Original EXP11 | `1425468`, FAILED `1:0`, 16:42, one CPU on `n0006` | 78 tasks: 37 PASS, 19 TIMEOUT, 22 INVALID; 51 credited objectives; 22 strict end-to-end wall-cap violations | Retain 56 valid statuses; preserve all 22 original invalid records. |
| First EXP22 recovery | `1426749`, FAILED `1:0`, 0:47, one CPU on `n0006` | Its separately run frozen auditor validated one 10-second Xiong-restarts TIMEOUT with a complete objective, 1,388 complete events, zero violations. The next attempted task overran its cap and remains failed evidence. | Credit only the one independently audited task. |
| Corrected EXP22 recovery | `1426751`, COMPLETED `0:0`, 10:13, one CPU on `n0006` | Frozen independent auditor: 15/15 TIMEOUT, nine credited objectives, 1,796 complete Xiong restart events, zero INVALID and zero violations | Credit 15 valid statuses, keeping their TIMEOUT labels. |

All three `checksums.sha256` files passed against their audit reports, inventories, comparisons, manifests, and restart-event ledgers. A separate read-only inspection matched all **94 checkpoint identities, wall times, and budget-compliance fields** to their manifests and inventories. The 15 graph entries across the three manifests passed byte SHA-256, canonical weighted graph hash, vertex count, arc count, total weight, and no-self-loop checks; the five graph hashes and normalization facts agree between jobs. The original and corrected job logs show their expected exit circumstances, and the corrected job has no fatal marker. Its `progress.json` still says `COMPUTATION_COMPLETE_AUDIT_PENDING` because it was written before the later, checksummed final audit; it is not the final status authority.

The Xiong source archive SHA-256 is `ff3f9f7a6182fccf8ea0b8e7d056ab8b34a612cb86da62dedf1b892bb75a1a07` at `8340e1633ba9290a567a882aff4d74f01b38102d`. The frozen binary SHA-256 `f58c54bb41e6e896225df40fab52b4e8e747a0967aa80ea3583c8025f2b7a2a9` matches the actual Wulver executable. The IPSNS checkout is `40209c26966247d9bf9ad34764de4ac4181f98c2`, and its `ipsns.py` SHA-256 `46a3f2b549897df1037ebe257e47b17490bddaa97effb2e31bce20a50ea54b36` matches all three manifests and the actual source file. The same original binary and IPSNS source were used across jobs on an AMD EPYC 7763 node. Compiler/build reproducibility beyond the frozen source archive and binary hash was not re-established here.

The standalone `analyze_frozen_pilot.py` verifies each report against its seal and recomputes statuses, objective availability, graph/algorithm/seed/budget identities, valid event counts, event deadlines, restart minima, graph weight denominators, and paired arithmetic from the frozen inventories. A separate rational-arithmetic check recomputed all nonmissing normalized pair values. The auditor, not this metadata script, independently reopens each private complete ordering, checks its hash and permutation, rescales no weights, recomputes weighted backward arcs, checks the retained DAG, and enforces event checkpoint deadlines. The raw witnesses stay private.

### Reconciliation without duplicate credit

| Evidence source | Audit-valid statuses | Usable objectives | Invalid original task identities still missing |
|---|---:|---:|---:|
| Original EXP11 | 56 = 37 PASS + 19 TIMEOUT | 51 | 22 |
| First recovery, disjoint original-invalid task | 1 TIMEOUT | 1 | 21 |
| Corrected recovery, 15 further disjoint original-invalid tasks | 15 TIMEOUT | 9 | 6 |
| **Combined, unique task identities** | **72 = 37 PASS + 35 TIMEOUT** | **61** | **6** |

The six missing cases are original one-second tasks: five on the 480-vertex Erdős–Rényi graph (all but one Xiong-single seed) and one IPSNS seed on the 120-vertex scale-free graph. They remain `INVALID`, not valid timeouts or objective losses. The failed second task from the first recovery is not counted; its corrected task is counted once. The combined inventory has the original **78 unique task IDs** and no new graph replication. Valid TIMEOUT means the task respected the strict outer wall cap; it does **not** imply a feasible objective. Across the combined inventory, 24 valid Xiong-restarts TIMEOUTs have a before-deadline complete-order objective, while 11 valid IPSNS TIMEOUTs have none.

## Five reused weighted graphs and paired results

The four synthetic graph bytes are reused EXP04 views from three generators; the larger Erdős–Rényi view is another size of the same family. CollegeMsg full-count is one EXP05 source-parent view. They are **five selected weighted graph views, not five independent empirical parents**. Total arc weight $T$ is shown because the signed paired metric is $(B_{\rm Xiong}-B_{\rm IPSNS})/T$; a positive value favors IPSNS. Both seeds are listed as `s1/s2`. For Xiong-single, a number denotes a completed PASS order; for Xiong-restarts, it denotes a complete incumbent saved before a valid TIMEOUT; for IPSNS, it denotes a completed PASS order. `T` means valid TIMEOUT without a usable order, and `I` means INVALID. A dash in the paired column means no valid quality comparison.

| Graph view | Cap (s) | $T$ | Xiong single s1/s2 | Xiong restarts s1/s2 | IPSNS s1/s2 | Restarts − IPSNS / $T$ |
|---|---:|---:|---|---|---|---:|
| ER 120 | 1 | 31,068 | 5,776 / 5,776 | 5,776 / 5,776 | T / T | — |
| ER 120 | 10 | 31,068 | 5,776 / 5,776 | 5,776 / 5,776 | 4,973 / 4,973 | +0.025846530 |
| ER 120 | 30 | 31,068 | 5,776 / 5,776 | 5,776 / 5,776 | 4,973 / 4,973 | +0.025846530 |
| Community 120 | 1 | 30,138 | 4,938 / 4,938 | 4,938 / 4,938 | T / T | — |
| Community 120 | 10 | 30,138 | 4,938 / 4,938 | 4,938 / 4,938 | 4,608 / 4,608 | +0.010949632 |
| Community 120 | 30 | 30,138 | 4,938 / 4,938 | 4,938 / 4,938 | 4,608 / 4,608 | +0.010949632 |
| Scale-free 120 | 1 | 30,556 | 1,805 / 1,805 | 1,805 / 1,805 | T / I | — |
| Scale-free 120 | 10 | 30,556 | 1,805 / 1,805 | 1,805 / 1,805 | 1,474 / 1,474 | +0.010832570 |
| Scale-free 120 | 30 | 30,556 | 1,805 / 1,805 | 1,805 / 1,805 | 1,474 / 1,474 | +0.010832570 |
| ER 480 | 1 | 121,369 | 18,916 / I | I / I | I / I | — |
| ER 480 | 10 | 121,369 | 18,916 / 18,430 | 18,430 / 18,430 | T / T | — |
| ER 480 | 30 | 121,369 | 18,916 / 18,430 | 18,430 / 18,430 | T / T | — |
| CollegeMsg full-count | 120 | 59,835 | 19,549 / 19,549 | 19,475 / 19,493 | T / T | — |

Only the three 120-vertex synthetic views have both Xiong and IPSNS objectives at 10 and 30 seconds. IPSNS has lower backward weight in both seeds on each of those three graphs at each cap: differences of 803, 330, and 331 weight units, or +0.025846530, +0.010949632, and +0.010832570 of the respective total weight. This is **three graph-level paired findings**, observed twice under separate fresh 10/30-second tasks; the twelve seed-by-cap pairs are dependent repeats. The identical recorded objective at 10 and 30 seconds is not an anytime trajectory or proof that extra time cannot help. The 480-vertex and CollegeMsg rows have no IPSNS objective; no cross-method quality winner can be assigned there.

Xiong restarts ties Xiong single on all three 120-vertex graphs. It improves over Xiong single for ER 480 seed 1 at both 10 and 30 seconds (18,430 versus 18,916) and for both CollegeMsg seeds at 120 seconds (19,475/19,493 versus 19,549). These are four strict paired seed-by-cap improvements among 24 available Xiong single/restarts objective pairs; the other 20 tie. Xiong's restarts consume the cap even after an early feasible incumbent and are labeled valid TIMEOUT, not completed single-shot executions.

### Availability and first valid order

| Cap (s) | Xiong single PASS / objective / INVALID | Xiong restarts valid TIMEOUT with objective / INVALID | IPSNS PASS / valid TIMEOUT without objective / INVALID | Median first saved complete order, seconds: single / restarts / IPSNS |
|---:|---|---|---|---|
| 1 | 7 / 7 / 1 | 6 / 2 | 0 / 5 / 3 | 0.733 / 0.243 / — |
| 10 | 8 / 8 / 0 | 8 / 0 | 6 / 2 / 0 | 0.461 / 0.517 / 3.699 |
| 30 | 8 / 8 / 0 | 8 / 0 | 6 / 2 / 0 | 0.507 / 0.593 / 3.670 |
| 120 | 2 / 2 / 0 | 2 / 0 | 0 / 2 / 0 | 0.821 / 0.967 / — |

These times run from the controller's monotonic start before worker launch to the first complete saved event; they include parsing, conversion, and initialization, but the independent post-run auditor is outside the method budget. Medians use only tasks with an available objective, so they are conditional on survival and are **not** a completed-time comparison over every task. For the six 10/30-second IPSNS completions per cap, first valid order lies between 1.955–5.736 s at 10 s and 1.636–5.821 s at 30 s. The Xiong single-shot and restart arms have an early order on every valid task at caps of at least 10 seconds; IPSNS completes 12/18 such tasks and has six valid no-objective timeouts, all on ER 480 or CollegeMsg. One-second conclusions are especially fragile because six tasks violate the strict outer cap.

## Exact original-method identity

The [published Xiong et al. article](https://doi.org/10.1016/j.cor.2024.106724) (*Computers & Operations Research* **169**:106724, 2024) studies graph reduction and a divide-and-conquer heuristic. Its mathematical setup admits positive arc weights, and its authors explicitly state that the main empirical focus is **unweighted** FAS, with limited weighted evaluation. Cardinality and weighted backward-arc objectives must not be conflated.

The [authors' repository README at the frozen commit](https://github.com/forgottencsc/FindingSmallFeedbackArcSetOnLargeGraphs/blob/8340e1633ba9290a567a882aff4d74f01b38102d/readme.md) maps `RASq` to **SimFASDC** with $r=1/q$ and `RASstar` to **FASDC** with $r=1/3$. [The executable source](https://github.com/forgottencsc/FindingSmallFeedbackArcSetOnLargeGraphs/blob/8340e1633ba9290a567a882aff4d74f01b38102d/src/fas_alg.cpp) dispatches `RASstar` to `hybrid<graph, true, 3, true>(g)`, while `RAS3` dispatches `hybrid<graph, false, 3, true>(g)`. The template parameters distinguish the recursive SCC variant from the simpler $q=3$ variant; `useAbs=true` selects the GreedyAbs choice within the hybrid. **The tested method is the authors' `RASstar` command, their FASDC $r=1/3$ variant—not the standalone GreedyABS baseline, all SimFASDC settings, or the entire paper's algorithm portfolio.**

The tested command supplies original positive integer weighted arcs in `W` format with `RASstar -r SEED -p -o RANKS`; `-w` is omitted because it would replace input weights. `-p` shuffles vertex labels and arc order and makes the seed meaningful. The original source is externally authored and has no explicit redistribution license; its source/binary remain outside this repository. The frozen auditor rescored complete output rankings on the unchanged weighted graph. This establishes source lineage, exact command-branch identity, and validated weighted output semantics. It does **not** establish that these five weighted inputs reproduce the paper's main unweighted benchmarks or that every implementation detail is bit-for-bit reproducible across compilers.

For the manuscript, describe the comparator as **“the authors' RASstar executable (their FASDC $r=1/3$ variant) applied to the original weighted inputs”**, rather than “the Xiong algorithm” as a generic claim. Preserve the existing distinction between authenticated source, the tested configuration, and the publication's broader method family. No source or reference edit is made in EXP24.

## Scientific interpretation and decisions

The pilot adds credible **deadline-availability evidence** that EXP10's unequal-work 120-second comparison could not supply: on these three small synthetic inputs, IPSNS completes by 10 s and yields a lower objective than the tested RASstar setting, whereas Xiong yields an early complete order under one-second caps where valid and remains available on ER 480 and CollegeMsg when IPSNS has no completed order at 30 or 120 s. Restarting can improve Xiong's saved incumbent on the larger two views. This is useful for designing a fairer future experiment and for avoiding the false interpretation of TIMEOUT as always having no objective.

The present five-view result **does not materially change the EXP23 JDSA conclusions**. EXP10 already observed IPSNS objective wins on selected synthetic graphs and Xiong's superior completion on larger empirical views under a different protocol. EXP24 narrows the time boundary but adds no independent inputs, no other contemporary baseline, and no real-view cross-method objective pair. It cannot support a league table, confidence interval over source parents, or statistical significance. The same selected graphs and two seeds appear at multiple fresh budgets; the Ali parent structure and most public objective-witness gaps remain unresolved. The current manuscript's nine tables and 5,254 public outcomes should not be changed merely to include these internal pilot records. No new main-text figure or table is proposed.

**Manuscript integration: NO-GO now.** Keep EXP23's accurate partial-EXP11 description and method/reproducibility qualifications. After a separate editorial decision, a short supplemental feasibility note could cite the 13-row graph/budget inventory, but only with the missing-objective and dependence boundaries above; it is not a replacement for a controlled contemporary benchmark.

**Broader controlled-time study: conditional GO for design and preflight, NO launch in EXP24.** A prespecified, modest study across more independently identified source parents and synthetic regimes could materially improve fairness if it includes at least the current project-maintained LR-TA, WMSF/L2, weighted Eades, IPSNS, and authenticated Xiong variants on identical weighted bytes, with full initialization and validated incumbents. One-second caps should be dropped; 10/30/120 s can be retained only after workload-specific feasibility checks. Distinguish a single-shot method, an intentional restart-until-cap method, and a method that exposes an order only at final return. The EXP22 protocol's 24-view, seven-arm, two-seed, three-cap upper-bound estimate is **53,760 CPU-seconds (14.9 CPU-hours) before overhead**, not an authorized production run or a journal requirement. Freeze graphs and independent source-parent units before outcomes, verify software fidelity and public/reviewer witness rights, and pilot any newly added arm before committing cluster resources. Rights/access resolution remains the nearer submission gate.

## Reproduction without private bytes in Git

Run from a private checkout after independently verifying the three original audit directories and their seals:

```sh
python experiments/exp22_controlled/analyze_frozen_pilot.py \
  --original "$EXP11_AUDIT_DIR" --first "$EXP22_FIRST_AUDIT_DIR" \
  --corrected "$EXP22_CORRECTED_AUDIT_DIR" \
  --output /tmp/exp24-recomputed-metadata
```

Compare the generated four metadata files against `analysis/EXP24_*`. The private variables are supplied by the investigator; no absolute Wulver path or graph/order byte is recorded in Git. The frozen audit sources and the failed-run evidence remain unchanged. The EXP23 author declarations—no research funding and no competing interests—are untouched.
