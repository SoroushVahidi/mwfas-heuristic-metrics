# EXP08B: controlled multi-SCC seed diagnostic

**Verdict: DIAGNOSIS_COMPLETE.** Across six structurally selected EXP04
graphs, all 30 IPSNS runs had two or three eligible positive-backward-weight
SCCs at iteration 1. Different seeds changed SCC selections and full search
traces on every graph. They did not change the validated final objective or
ordering on any graph by iteration 50. This is evidence that the seed is
effective at choosing neighborhoods, with no observed final-quality effect in
this small diagnostic. It is not evidence of global optimality or of seed
insensitivity on other graph classes.

## Frozen design and graph provenance

[The prespecified configuration](../../configs/exp08b.json) was committed as
`9199ca72782a2354c01fe0fbfad6c5eff9d7f158` before the first run. Its
SHA-256 is `854a62f48a9f6a14e3f65c8557a8a5fe90602136f42633ac32a37e8b76ee6149`.
An independent structural scan found ten graphs with at least two cyclic SCCs
among EXP04's 135 validated graph inputs. Selection used family, size, density,
and SCC sizes: the sole qualifying ER graph, first community graph, first
scale-free 120/k03 graph, three-SCC scale-free 240/k03 graph, first
scale-free 240/k05 graph, and first scale-free 480/k05 graph. Within each
category, “first” means lexicographically first graph ID. Algorithm outcomes
were not used for selection. EXP04's saved validation report records 15 PASS
checks for each selected graph (90/90). All six are generated EXP04 graphs;
none is a real-world network or a new synthetic fixture.

| Family and graph ID | Vertices / arcs | Cyclic SCC sizes | Weighted graph SHA-256 | DIMACS SHA-256 |
|---|---:|---|---|---|
| ER `exp04_er_n240_k03_r02` | 240 / 720 | 204, 2 | `c904266dba7a41ec4c197323726b9ae15ca794aa9eb67446d70ac334e9c0440c` | `e5bf27edf11926143165b3dff1d5bf20a23d95bd6a68227c5d23b93aa90718ea` |
| Community `exp04_cm_n240_k03_r01` | 240 / 720 | 220, 2 | `c412d932cb656b0d295c1843e86b4f2e0fa1379184022035d02936dcf5654ca8` | `c21d2930cb85463a49c85874756f4c24df6c2fbe7c4dba14e7c13b530d241b39` |
| Scale-free `exp04_sf_n120_k03_r01` | 120 / 360 | 25, 3 | `3e39d0a73a5dca745c631fb58f545f1c2be3a0cc76fccee8cebdfada44564587` | `a35772f5de9723e5df75a395d0ce9bd5e461d97049d78f1ea81ca3825d7c6bae` |
| Scale-free `exp04_sf_n240_k03_r03` | 240 / 720 | 20, 12, 3 | `051d6c3e9a909ee479620a4bfef07de114420b98e18086c3abdd9682d0667c37` | `ca33dd4683e19024964e56b8eea934e2a4479b209a8afaeff3edbba6cf969573` |
| Scale-free `exp04_sf_n240_k05_r02` | 240 / 1,200 | 138, 2 | `8da3460cd20c94a5ff471bd7d66c919d178cd27ccc1e94e1b7fde47614bcbb7d` | `c0dfc9a3a3e20a4ff2e694dbeedc507ec2522c2c8a3591afc301d7bd4717ef14` |
| Scale-free `exp04_sf_n480_k05_r02` | 480 / 2,400 | 281, 2, 2 | `6804daead39293ff4fe3363465a1206fa5eeecae84b08d85368e9608413bd4cf` | `c0783653baeed8772c6b80f9bb0f9f26f4c76d4b458ba272b6d1e42f0d9df72d` |

Each directed cycle has positive integer arc weights, so every initial
complete ordering incurs positive backward weight in each cyclic SCC.
The observer confirmed an eligible pool of two or three at the first draw
of every run. Graph files were copied read-only from
`CUSTODY_PATH/graphs` to ignored
`data/cache/exp08b/graphs/`; raw inputs, orderings, traces, and logs are not
committed. EXP05 and EXP07 evidence and jobs were untouched.

The canonical IPSNS source remains the pinned
`SoroushVahidi/minimum-weighted-fas-heuristics` commit
`40209c26966247d9bf9ad34764de4ac4181f98c2`. Seeds were **1–5** for each
graph. Runs used L2 full WMSF initialization, weighted top-15 SCC choice,
0.30 add-back fraction, 0.02 forced-removal fraction, and `1e-12` tolerance.
Every run had 50 iterations, recorded best-objective checkpoints at **10**
and **50**, and a **15-second wall cap**. The campaign cap was **900 CPU-seconds**.
Time-limited runs would have been recorded as censored, without implying a
completed final solution.

The successful campaign used observer revision
`a99182d2b318f3a5f40e29c06be6c1e0df099eee` and this command:

```bash
uv run --locked python experiments/exp08_seed_sensitivity/diagnostic.py campaign \
  --config configs/exp08b.json --source data/cache/exp08/upstream \
  --graphs data/cache/exp08b/graphs \
  --output data/cache/exp08b/pilot-a99182d
uv run --locked python experiments/exp08_seed_sensitivity/analyze.py \
  --config configs/exp08b.json --graphs data/cache/exp08b/graphs \
  --output data/cache/exp08b/pilot-a99182d
```

The host was `al-khwarizmi` (Intel Core i7-12700K), running Python 3.12.3,
NetworkX 3.6.1, and pandas 3.0.2. The successful campaign ran on 2026-10-17
from 18:19:32 to 18:19:46 UTC and used **13.347 child CPU-seconds**. The exact
timestamps and command are in the ignored
`data/cache/exp08b/pilot-a99182d/run_manifest.json` (SHA-256
`d25a0125fc069c89aa9986b7770166c4d0aa2c6e2801062f1eee718dbc14c71a`).

The first attempt under the frozen design, in ignored
`data/cache/exp08b/pilot-9199ca7/`, revealed a diagnostic observer error:
it counted an internal WMSF objective evaluation as one of the two seed
solutions. It recorded five completed observations and 25 instrumentation
failures, using 13.252 child CPU-seconds. Those observations are **excluded**
from scientific comparisons, and their original files remain intact. The
observer fix and regression test were committed before the complete rerun.
Together, both attempts used 26.599 CPU-seconds, well below the 900-second
new-campaign ceiling. No IPSNS algorithm code or random-seed semantics changed.

## Validation and seed diversity

The successful manifest has **30/30 completed, zero failures, zero timeouts**.
Each worker and the post-run analyzer reopened the original DIMACS graph and
saved CSV, checked exact graph hashes and counts, verified a complete numeric
vertex permutation and ranks, recomputed backward-arc weight directly from
original weighted arcs, and checked the saved objective and ordering hash.
All **30/30** passed. Each run had one expected RNG initialization and 50
recorded SCC-selection draws; none drew randomness inside neighborhood
perturbation. The analyzer's `analysis.json` SHA-256 is
`af6e849dae8630f5a4739b107c9870cfb657c6808b4a1cb51044c8cd73b41a0d`.
An additional read-only stdlib check independently parsed the raw `p` and `a`
DIMACS lines and CSV ranks, verified file hashes and every numeric vertex,
and recomputed objectives and ordering hashes: **30/30 PASS**.

| Graph | Initial pool | Distinct SCC paths / candidate-objective paths | First selection divergence | Best initial → at 10 → at 50 | Accepted improvements per seed | Distinct final objectives / orderings |
|---|---:|---:|---:|---:|---:|---:|
| ER 240/k03 | 2 | 5 / 5 | 11 | 2,226 → 2,226 → 2,226 | 0 | 1 / 1 |
| Community 240/k03 | 2 | 4 / 4 | 11 | 2,281 → 2,281 → 2,281 | 0 | 1 / 1 |
| Scale-free 120/k03 | 2 | 5 / 1 | 1 | 388 → 388 → 388 | 0 | 1 / 1 |
| Scale-free 240/k03 | 3 | 5 / 1 | 1 | 300 → 300 → 300 | 0 | 1 / 1 |
| Scale-free 240/k05 | 2 | 4 / 1 | 11 | 2,744 → 2,611 → 2,611 | 2 (iterations 1, 2) | 1 / 1 |
| Scale-free 480/k05 | 3 | 5 / 5 | 11 | 5,095 → 5,095 → 5,095 | 0 | 1 / 1 |

Distinct full-trajectory counts equal the SCC-path counts in the table:
**5, 4, 5, 5, 4, 5**. Candidate objective values varied among seeds on
ER 240/k03, community 240/k03, and scale-free 480/k05, but no differing
candidate was accepted. For scale-free 240/k05, both improvements occurred
before the first selection divergence. Its later differing selection paths
changed neither candidate-objective paths nor final quality. The per-iteration
incumbent curves are in ignored
`data/cache/exp08b/pilot-a99182d/convergence.csv` (SHA-256
`1a052e6bd0b98bd2982f50d60ded8843c2599e8f3ba3e1c98c50f7e4afb0f869`).
All 30 curves are flat from iteration 2 through 50. The recorded final
ordering SHA-256 values appear in each run JSON; within every graph, all five
seeds have the same hash, and the saved CSVs independently pass validation.

Median function-level IPSNS times by graph were 0.186, 0.216, 0.013, 0.016,
0.122, and 0.484 seconds in table order. These laptop times describe the
diagnostic only; they are not hardware-controlled comparisons to Wulver.

## Interpretation and limits

[EXP08A](RESULTS.md) observed only one eligible SCC in each of six denser
generated graphs, so five seeds had identical complete trajectories.
EXP08B deliberately tests the multi-SCC branch: every graph shows different
selection and full trajectories, proving the canonical `random.seed` and
`random.choices` path is effective. The one common final ordering per graph
does not imply a deterministic search. With strict-improvement acceptance,
different rejected neighborhoods can leave the protected incumbent identical.

Existing read-only EXP05 traces likewise show seed-dependent SCC paths in
seven of 151 completed three-seed instance-budget groups, concentrated in
two real-world graphs (`exp05_rxr_2015` and `exp05_isic_fr_2022`), without
different recorded final objectives or orderings. EXP05 is undergoing
separate preservation and recovery; its evidence should not be promoted to
a final paper claim until that audit finishes. EXP08B provides controlled
generated-graph evidence, not real-world prevalence estimates.

No completed run improved after iteration 2, and all six groups have the
same objective at iterations 10 and 50. Extra iterations of this unchanged
protocol have no demonstrated scientific value on these inputs. A large
untargeted repeated-seed sweep should be **abandoned**. Any later robustness
experiment should be redesigned around prespecified graphs with multiple
**substantial** SCCs and comparable initial backward contributions, and
should first show that additional iterations can produce accepted changes.
That is a separate hypothesis; this six-graph, five-seed diagnostic cannot
establish general seed invariance, convergence to an optimum, or causal
runtime effects of different SCC choices.
