# EXP08: bounded IPSNS seed-sensitivity diagnostic

**Verdict: DIAGNOSIS_COMPLETE for the six-graph pilot.** The seed is passed to
the canonical algorithm and the RNG is called. On these six inputs, every call
selects from exactly one eligible cyclic SCC, so changing the seed cannot
change the selected neighborhood. Perturbation within that SCC is deterministic
in the pinned implementation. The five seeds therefore produce identical
candidate paths, final objectives, and final orderings on every graph. This is
an algorithmic exploration limit on these inputs, not a broken seed parameter.

## Frozen protocol and provenance

The design was committed at `678a24c11af1ed0264c228c9b7ed394544c1e21d`
before running. [The frozen configuration](../../configs/exp08.json) has SHA-256
`a0065da998a47b1a0e7b40e04e1e0862b0339f5a2a4060449732d1c6cd7f59b1`.
The six inputs are EXP04 replicate 1 at target mean outdegree 5: one 120-vertex
and one 240-vertex graph in each family. This rule does not use IPSNS outcomes.
EXP04 had independently validated all 2,025 production runs, including the
selected graphs, before EXP08. Graph files were copied read-only from
`CUSTODY_PATH/graphs` to ignored
`data/cache/exp08/graphs/`; no EXP04, EXP05, or EXP07 artifact was modified.

| Family | Graph ID | Vertices / arcs | Weighted graph SHA-256 | DIMACS SHA-256 |
|---|---|---:|---|---|
| Erdős–Rényi | `exp04_er_n120_k05_r01` | 120 / 600 | `87fa70b1df5569438ae5c434b8e828aa128017011c75b7ceb054a023eefccd92` | `fd08b9ed5a9f0836c27510add64613a14d045b20b2d6593cad01af91194ce4c0` |
| Erdős–Rényi | `exp04_er_n240_k05_r01` | 240 / 1,200 | `86ad10ac0856bfcac4b904f8694cc966f1835d991fd29c0a98c1889960f4a531` | `7b09303e4905c6f64e20f34ddd1abac3276c624026494c1d527f65011fa6e779` |
| Scale-free | `exp04_sf_n120_k05_r01` | 120 / 600 | `2c699a905f9fc6da0f9d6832725860d1069983b700f43fb8bf54c278d160f551` | `11ea3a299b3b9290e9ee4f4411c0dc17a74f19f5370f7560b64306cf7b6d83d0` |
| Scale-free | `exp04_sf_n240_k05_r01` | 240 / 1,200 | `133b7ffd4627460f3a004df99ec6b407fd0c3d09fb0f3c70758734790205dbaa` | `436fb85f4b04d7bd436bf76f4b9c882b3dfe6e56a4f0126690001642b35a52ac` |
| Community | `exp04_cm_n120_k05_r01` | 120 / 600 | `e9b5aa453cfa83c92af3d69db085c488f41078e88d27725dded8091ded2ac462` | `06021961f0e33ffc587a0b9ddcd8cc8bf3724cdd48b64b1cdc144e8e44aad384` |
| Community | `exp04_cm_n240_k05_r01` | 240 / 1,200 | `fa4d2590ae3211c652cff35f400c2270b7790974123143e570919f6d451b4c61` | `3e64bc1ab3d473c614662086b9d9e8d0bbcef3b223fc19fe88e410c4a9252cef` |

The pinned canonical algorithm is
`SoroushVahidi/minimum-weighted-fas-heuristics` commit
`40209c26966247d9bf9ad34764de4ac4181f98c2`. Each graph received one
fresh 50-iteration run at seeds **1, 2, 3, 4, 5**, with incumbent-objective
checkpoints at iterations **10 and 50**. Parameters were L2 full WMSF seed,
weighted SCC selection with top-K 15, add-back fraction 0.30, forced-removal
fraction 0.02, and tolerance `1e-12`. Each subprocess had a **15-second wall
cap**; the campaign had a **1,800 CPU-second cap**. Time-limited runs would
have remained `CENSORED_TIMEOUT` without a valid final ordering.

The pilot command was:

```bash
uv run --locked python experiments/exp08_seed_sensitivity/diagnostic.py campaign \
  --config configs/exp08.json --source data/cache/exp08/upstream \
  --graphs data/cache/exp08/graphs --output data/cache/exp08/pilot-678a24c
```

The machine was `al-khwarizmi` with an Intel Core i7-12700K, Python 3.12.3,
NetworkX 3.6.1, and pandas 3.0.2. The command ran from
18:07:55 to 18:08:14 UTC on 2026-10-17, used **18.716 child CPU-seconds**, and
recorded its software versions, command, code revision, source revision, graph
hashes, and host in ignored `data/cache/exp08/pilot-678a24c/run_manifest.json`.
The raw orders, per-iteration records, and logs remain outside Git. The
independent `analysis.json` has SHA-256
`fd90562ed0abc1298299b41b0337826f3052ff7683ab92a152767131c1e7889f`.

## Source inspection and prior evidence

The canonical function calls `random.seed(rng_seed)` once at entry. Its
WMSF/LR-TA initialization is deterministic. At every positive-backward-weight
SCC iteration it calls `random.choices` to choose one SCC from a weighted
top-K pool. There is no reseeding inside the loop and no unused alternate RNG.
The imported graph reader, WMSF, LR-TA, and objective modules contain no
other RNG calls on this path.
The add-back move takes the heaviest removed edges in sorted order; forced
removal takes the lightest active edges in sorted order. Repair is deterministic.
The algorithm accepts only strict objective improvements, restores the prior
incumbent after rejection, and stops after its iteration budget or when no
positive-backward-weight SCC remains. EXP08 observed these calls passively;
it did not change the algorithm. On the multi-SCC regression fixture, the
observer and unmodified canonical source wrote byte-identical orderings at
three seeds, while SCC selections differed between seeds.

Existing production evidence distinguishes outcomes from paths:

| Experiment | Completed three-seed instance-budget groups | Groups with different final objectives | Groups with different final ordering hashes | Groups with different recorded SCC-selection traces |
|---|---:|---:|---:|---:|
| EXP03 | 270 | 0 | 0 | Not recorded |
| EXP04 | 540 | 0 | 0 | Not recorded |
| EXP05 | 151 | 0 | 0 | 7 |

EXP05's seven divergent traces occurred on `exp05_rxr_2015` at budgets 50 and
200 (first selection divergence at iteration 34), and `exp05_isic_fr_2022`
at budgets 1, 3, 10, 50, and 200 (first divergence at iteration 1). The
eligible pool reached two SCCs in those groups. Their common final objectives
and orderings therefore **do not** mean that the seed was unused. EXP05 remains
under separate recovery and validation; these trace counts are read-only
descriptive evidence from its saved original production records. Its final
108 IPSNS timeouts remain censored.

## Pilot validation and results

All **30/30 runs completed**, with **zero timeouts and zero failures**. The
worker and a separate analyzer each reopened the graph and saved CSV, checked
all numeric vertices and ranks, verified file and graph hashes, and recomputed
the weighted backward-arc objective directly from original arcs. All 30
passed. Each run initialized the RNG once and made 50 observed SCC-selection
draws, so there were **1,500 draws** total. The eligible pool size was one at
all 1,500 selections. All 1,500 candidate objectives were captured. There
were **50 accepted improvements** across the 30 runs; the other candidates
did not improve the incumbent. No random draws occurred inside perturbation.

| Graph | Initial objective | Best at 10 | Best at 50 | Improvements per seed | Distinct SCC / full paths | Distinct final objectives / orders | First divergence |
|---|---:|---:|---:|---:|---:|---:|---|
| ER 120 | 5,641 | 4,973 | 4,973 | 1 | 1 / 1 | 1 / 1 | None |
| ER 240 | 8,794 | 7,763 | 7,763 | 3 | 1 / 1 | 1 / 1 | None |
| Scale-free 120 | 1,639 | 1,474 | 1,474 | 1 | 1 / 1 | 1 / 1 | None |
| Scale-free 240 | 3,262 | 2,927 | 2,927 | 1 | 1 / 1 | 1 / 1 | None |
| Community 120 | 4,608 | 4,608 | 4,608 | 0 | 1 / 1 | 1 / 1 | None |
| Community 240 | 9,961 | 9,126 | 9,126 | 4 | 1 / 1 | 1 / 1 | None |

The shared final ordering-identity SHA-256 values (numeric node IDs joined in
rank order with newline terminators) are:

| Graph | Final ordering identity SHA-256 |
|---|---|
| ER 120 | `13b46d1f6acf60f744452028aea6ff94473ac0274d590f6c13a3bc46ee2d2c2c` |
| ER 240 | `78a2a2203b81c102dd9da6fb3e7a8827bdee9bf8460957cab5eba0e4901082cb` |
| Scale-free 120 | `b3038a8d0bd4448b3d20602525d989d2143300d40ae08213b26a2c2d82f37ac9` |
| Scale-free 240 | `9479f2d091ce230b4ae4f9034ba004988ba7114b2c5af33d40bea32f7098110c` |
| Community 120 | `1ce497175c9147d6feca577a74115e5f48172164c6e43e2bc74a3d0adb475c51` |
| Community 240 | `ccd6c15b687784efe789e685b401d9a413cb206153c93edc7efd8ea1fd831f39` |

Within each graph, the five seeds also had one perturbation-choice path and
one candidate-objective path. The last accepted improvement was at iteration
1 for ER 120 and both scale-free graphs, iteration 3 for ER 240, and iteration
4 for community 240; community 120 never improved its initial incumbent.
The objective curves are therefore flat after iteration 4. The
independently validated 1,530-row convergence CSV is
`data/cache/exp08/pilot-678a24c/convergence.csv` (SHA-256
`ebf5b59338af23c92ab3c850d6ae238e09d69c2f965de77201e81e88143ca7c2`).
Its PNG and PDF plots in the same directory show all five seed curves
overlapping on each graph.

| Graph | Median initialization | Median search | Median total algorithm time |
|---|---:|---:|---:|
| ER 120 | 0.014 s | 0.203 s | 0.219 s |
| ER 240 | 0.047 s | 0.689 s | 0.739 s |
| Scale-free 120 | 0.005 s | 0.038 s | 0.044 s |
| Scale-free 240 | 0.013 s | 0.155 s | 0.170 s |
| Community 120 | 0.012 s | 0.201 s | 0.214 s |
| Community 240 | 0.043 s | 0.691 s | 0.735 s |

The search boundary is observed immediately before CSV output. Total
algorithm time includes final output work. Process startup and imports outside
the function are included in the per-run 15-second wall cap, but not in this
function-level timing table. These laptop timings must not be compared as
hardware-controlled runtime effects against Wulver production.

## Interpretation and next experiment

The seed parameter is functional: EXP05 has recorded seed-dependent SCC
choices when more than one eligible SCC exists. On all six pilot graphs,
the canonical weighted-selection pool collapses to one SCC; its other move
choices are deterministic. The identical trajectories are therefore more
specific than an identical final objective: this pilot did not exercise a
stochastic branch with multiple outcomes. Early flat incumbent curves show no
further *accepted* improvements under the 50-iteration protocol; they do not
prove optimality or global convergence.

No implementation defect was established, so no correction or corrected-result
comparison is warranted. A larger same-protocol seed sweep over similar
one-eligible-SCC graphs would have little scientific value. If stochastic
robustness remains a paper objective, first prespecify a small structural
sample with **multiple eligible cyclic SCCs** and inspect trajectory diversity
there. A randomized perturbation would be a separately labeled algorithmic
variant requiring its own matched comparison, not a silent fix to IPSNS.
Six deliberately selected graphs and five seeds cannot support a population
claim about all random, scale-free, community, or real-world networks.
