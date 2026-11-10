# EXP09 external MWFAS baseline pilot

EXP09 is isolated on `feat/exp09-external-heuristic-benchmarks`, stacked on
the EXP08 branch. [The frozen pilot configuration](../../configs/exp09.json)
selects 12 distinct graphs from immutable EXP03, EXP04, and EXP06 selection
manifests using only family, size, degree, SCC, and weight-distribution
properties. It includes four EXP06 exact-certified small instances, three
EXP03 60-vertex instances, four EXP04 120/240-vertex instances, and one
480-vertex EXP04 instance. EXP05 inputs are excluded while its preservation
and recovery continue. The graph identifiers and both graph hashes are in the
configuration. Their source validation reports have PASS records for every
selected graph: 60 EXP03, 75 EXP04, and 31 EXP06 checks. The 12 copied graph
files also passed independent DIMACS and weighted-graph hash verification.

## External algorithm compatibility and licensing

| Candidate | Evidence | EXP09 disposition |
|---|---|---|
| [Rocket-Crane paper](https://doi.org/10.1007/s13278-025-01491-2) and [official repository](https://github.com/Bader-Research/MinimumFeedbackArcSet) | Repository commit `c30a6ac857c44e05833a8495781d97e2829deb44`, root MIT license (2026 David Bader's Research Group). Published method combines JAX/Optax Rocket optimization with a longer Crane refinement. The repository supplies an original JAX script hardwired to `connectome_graph.csv`, 20,000 epochs, and output checkpoints, plus a separate C library of Okubo and Toposhuffle annealing components. No ready-made script reproduces the entire published pipeline on an arbitrary input within 120 seconds. | Pilot the **serial C Okubo + Toposhuffle annealing component** under that exact name. It is external and objective-compatible, but **not a faithful reproduction of complete Rocket-Crane**. Original C files remain pinned and unmodified in ignored source cache / Wulver `source/`. The small C driver calls their public functions and records their native best ordering and forward score. |
| [Xiong et al.](https://doi.org/10.1016/j.cor.2024.106724) | The article describes arc-weighted input, while its experiments emphasize unweighted FAS. It says supplementary source code exists, but an independently verifiable executable, source revision, license, weighted-mode invocation, and output contract were not established from the accessible publication record or public repository search. | No substitute implementation or benchmark claim. Reconsider only after obtaining and testing the authors' exact source and weighted behavior. |
| [MA-EDM](https://github.com/carlossegurag/LOP_MA-EDM) | Repository commit `0572185bcb7bddc8059eee2dbf8c6b3d549932ba` contains C++ source, Makefile, seed and time arguments, and dense integer LOP matrices. It has no repository license file or explicit software license in its README. A weighted MWFAS instance can be represented as a linear-ordering matrix, but the dense representation and objective direction require explicit validation. | Feasible candidate for later EXIOBASE/LOLIB comparisons after source-use authorization is established. No source integration, redistribution, or dense campaign in EXP09. |

The C library expects a headered `source,target,weight` CSV of nonnegative
32-bit integer arc weights and unsigned numeric vertex IDs. It maximizes the
weight of forward arcs, so for a complete ordering on the original graph,
`backward = total original weight − independently recomputed forward`. The
adapter aggregates parallel arcs by ordered endpoint pair, omits self-loops
whose weight is an unavoidable objective constant, retains zero-weight arcs,
and appends any isolated original numeric vertices after the external order.
It records each transformation explicitly. The pilot graphs have no isolates,
self-loops, parallel arcs, or zero-weight arcs. Inputs with weights outside
the library's integer range are rejected. The original weighted graph and
its identity hashes remain authoritative throughout validation.

The authors' `create_random_solution_instance()` mixes wall-clock time into
its seed. The driver instead supplies a seeded Fisher–Yates initial permutation
through the library's public `create_solution_instance()` API, then calls
`seed_rng(seed)` before the unchanged Okubo and serial annealing routines.
This preserves the random-start strategy while making the stated seeds
reproducible. It is a controlled adapter choice and should not be described
as the authors' unmodified example-script initialization. Two seeds per graph
measure limited within-graph variability.

## Validation and computational bounds

Every task stores the original C output, converted input, log, validated CSV
ordering, and JSON checkpoint in separate directories. Independent validation
checks original DIMACS and weighted-graph hashes, exact numeric vertex
coverage, C score versus recomputed original-graph forward weight, weighted
backward objective, and acyclicity after backward arcs are removed. A malformed
result is a failure, and a time-limited task is censored. No unvalidated
external score is used as a benchmark result. Tiny-graph tests include a
brute-force certified optimum, duplicate arcs, a zero-weight arc, a self-loop,
an isolated vertex, malformed permutations, and objective mismatch.

The Wulver pilot has 12 graphs × two seeds = 24 tasks; each external run is
capped at 120 seconds and the campaign at 7,200 CPU-seconds. Its Slurm request
is one CPU, 4 GB, and at most three hours on verified `ikoutis/general/low`.
The algorithm parameters are three Okubo epochs, 100,000 serial annealing
iterations, temperature range 0.001–0.1, rollback window 10,000, and
Toposhuffle frequency 5,000. These are bounded pilot settings, not the
authors' large-connectome settings. The C sources are compiled on Wulver
with its GCC into a separate `build/` directory. No Gurobi license is used.

The dedicated Wulver root is `CUSTODY_PATH/mwfas-exp09` with
`source/`, `releases/`, `venv/`, `graphs/`, `build/`, `pilot-output/`, and
`logs/` separated. The batch script is
[`pilot.sbatch`](pilot.sbatch). The run manifest records Slurm ID, source and
code revisions, configuration and binary hashes, host CPU, Python and
NetworkX versions, command, and task counts. Original evidence is never
overwritten; a new pilot requires a new output directory.

The completed, independently validated pilot and production decision are in
[`RESULTS.md`](RESULTS.md). Existing EXP03/04/06 results support objective
comparisons; their historic timing is not a controlled same-node measurement.

The pilot's separate [`independent_audit.py`](independent_audit.py) reparses
raw DIMACS arcs and external output without importing the run-time adapter.
For the insertion comparator, [`insertion_comparator.py`](insertion_comparator.py)
uses the existing, unchanged EXP05 insertion implementation on copies of each
selected graph's validated LR-TA and WMSF seed orderings. Its 24 tasks run in
a separate Slurm job and output directory, with a 110-second refinement
deadline, 120-second task cap, and the original 1,000 accepted-move limit.
The combined worst-case CPU budget of external and insertion tasks is below
7,200 CPU-seconds. No EXP05 production input, output, or recovery file is
read for this comparator.

Historical objective values are preserved in the small derived
[`prior_baselines.json`](prior_baselines.json) snapshot. The original EXP03,
EXP04, and EXP06 Parquet paths and SHA-256 values are in
[`prior_sources.json`](prior_sources.json). To reproduce the comparison,
copy those four source Parquet files into an ignored `prior_exports/`
directory using the filenames expected by [`verify_prior.py`](verify_prior.py),
then run that script to check all 69 selected prior records against the
exports. After copying the two immutable EXP09 output trees and 12 graphs,
run [`analyze.py`](analyze.py) to recheck all 48 pilot orderings and derive
the objective comparisons and graph-unit descriptive interval.
