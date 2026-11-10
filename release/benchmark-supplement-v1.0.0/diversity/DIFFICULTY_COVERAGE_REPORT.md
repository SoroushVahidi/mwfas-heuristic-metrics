# Difficulty coverage using existing evidence only

**Assessment: several observed regimes are present, but difficulty coverage is not independently balanced across source, size and reference quality.** Structural cyclicity, a timeout and a large feedback objective are not interchangeable hardness definitions.

## Exact-solver/reference evidence

| Cohort | Numerically certified graphs | Bounded graphs | No applicable numerical reference |
|---|---:|---:|---:|
| EXP03 | 9 | 0 | 36 |
| EXP04 | 11 | 25 | 99 |
| EXP06 | 198 | 0 | 0 |
| EXP05 | 0 | 0 | 38 |
| EXP12 | 0 | 0 | 20 |
| EXP13 | 0 | 0 | 3 |
| Wikimedia | 0 | 0 | 3 |

All 243 references are on generated graphs. Of the 218 certificates, 198 are EXP06 n=12/20/28; only two certified records exceed n=240. All empirical and Ali records have saved feasible witnesses but no applicable numerical reference in this register. This does not imply their optimum is unknown outside the register.

The 25 bounded EXP07 references have `(UB−LB)/UB` minimum 0.1736, median 0.6520, maximum 0.9051. These retain meaningful bound provenance but often do not resolve a narrow optimum gap. Existing “certified” statuses remain numerical, not exact-arithmetic proofs.

Actual saved EXP06 MILP runtime was read from 198 raw solver records and checked against each associated run's evidence hash:

| n | Records | Median saved solver seconds | Maximum saved solver seconds |
|---|---:|---:|---:|
| 12 | 66 | 0.2827 | 0.5394 |
| 20 | 66 | 0.3510 | 0.6490 |
| 28 | 66 | 0.5124 | 1.9659 |

This is a comparatively quick solved cohort under the original implementation/settings. Wrapper process wall times range up to 61.81 seconds and must **not** be interpreted as exact solving effort. Both values are preserved in `DIFFICULTY_SOLVER_EFFORT.tsv`. These descriptive within-cohort summaries are not cross-hardware speed claims or an effort-normalized hardness ranking. No new solver was invoked. Comparable solver-effort metadata across every cohort is unavailable, so no pooled runtime comparison is made.

## Heuristic evidence

Among graphs with numerical certificates, best **existing** feasible heuristic results match the reference on 118/218 graphs. Their gap distributions differ:

| Cohort | Certified graphs | Best recorded heuristic hits | Median relative gap | Maximum relative gap |
|---|---:|---:|---:|---:|
| EXP03 | 9 | 0 | 8.03% | 22.79% |
| EXP04 | 11 | 2 | 2.70% | 11.19% |
| EXP06 | 198 | 116 | 0% | 15.36% |

These describe the tested algorithm portfolio and original protocols. Different arm sets, budgets and selection criteria prevent interpreting the differences as intrinsic difficulty or method superiority. Best-observed and worst-observed objectives/spread are retained per graph as descriptive coverage, not a new comparison experiment.

Original statuses remain 4,933 PASS, 198 CERTIFIED_OPTIMAL, 110 TIMEOUT, 11 FAIL and two dependency skips. The 108 EXP05 IPSNS timeouts occur across 20 graphs (CollegeMsg 4, Email-Eu-core 2, Wiki-Vote 2, EXIOBASE 12). The two EXP13 insertion timeouts occur on one IRS graph. This gives 21 affected graphs across five parents. Failed/timeout observations are not converted into completed objective results or imputed from another arm.

## Structural associations, not intrinsic-hardness labels

`DIFFICULTY_STRUCTURAL_ASSOCIATIONS.tsv` reports within-cohort descriptive summaries. The 12 EXIOBASE views with an observed timeout have median n=164.5, cyclic-arc fraction 0.961 and weight CV 4.790; the 18 without a timeout have medians n=10, cyclic-arc fraction 0.643 and weight CV 1.800. This identifies a joint size/cyclicity/weight regime associated with the recorded implementation limits **within one parent**, not a causal explanation or independent multi-source replication.

Within EXP06, the 82 graphs where the best recorded heuristic misses the numerical reference have median cyclic-arc fraction 1.0 and median weight CV 0.627; the 116 reference-hit graphs have medians 0.740 and 0.976 respectively. Both groups have median n=20. Higher weight concentration therefore does not monotonically identify the observed gap regime in this cohort. Family composition, topology and paired weights remain dependent/confounded; no significance, predictive model or universal hardness claim is attached. These summaries help select complementary benchmark conditions, not rank algorithms.

## Matched-budget and composition evidence already established

The validated EXP28 integration summary reports 117 tasks on nine generated topologies and four empirical parents, 234 budget rows and 182 paired comparison rows. Six of eight empirical IPSNS tasks timed out with valid incumbents; 13 restart tasks also reached their cap with usable incumbents. A predeadline feasible incumbent is an objective observation but does not change TIMEOUT into PASS. The two horizons and multiple seeds remain dependent observations.

Its reported comparator-sensitive patterns, including insertion results on four empirical parents, are existing findings. They demonstrate a limited matched-time regime; they are not newly discovered here or pooled with incompatible protocols. The nine synthetic plus four empirical units do not expand the 442 unique registered inputs.

The original EXP05 five-arm composition table was recomputed on exactly 37 complete original views (30 EXIOBASE, four CollegeMsg, one Email-Eu-core, two Wiki-Vote). All published six-decimal means match. Equal-view versus equal-parent weighting reverses WMSF/L2 and weighted Eades. This corroborates an **existing** source-composition result and is not claimed as new novelty. The full Email-Eu-core view is excluded consistently; no recovery or IPSNS record enters that table.

## Underrepresented regimes and interpretation

1. Empirical reference-backed comparisons are absent in this register. This requires reference work if a claim about empirical optimality gaps is desired; simply adding more uncertified graphs will not fix it.
2. Difficult-but-comparably-measured exact-solving regimes are thin: the homogeneous EXP06 cohort is solved quickly, while EXP07 bounds are often wide. More exact experiments are unnecessary for the current dataset/reuse claim, but needed to assert a representative exact-solver challenge suite.
3. Large cross-domain matched-budget heuristic comparisons are limited. Large navigation views have saved ranking witnesses, not a broad common-protocol algorithm contest. Only four empirical parents enter EXP28.
4. Near-acyclic, medium/large, multi-source cases are scarce. Additional SCC structure alone would not establish new algorithm difficulty.
5. Size, weight regime and reference availability are confounded. The high-concentration generated regime is small; reference quality does not span the empirical tail.

No exact solver, heuristic, stochastic optimization, EXP campaign or performance experiment was launched. All reported difficulty descriptors derive from existing validated records; raw identities and numerical metadata joins are preserved.
