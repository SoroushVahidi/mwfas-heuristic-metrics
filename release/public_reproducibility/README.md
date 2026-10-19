# Complete saved-output reproduction: Tables 4 and 5

This release independently reconstructs all displayed entries of the frozen
EXP04 refinement table and EXP06 paired-weight table from original graph and
saved-order bytes. The versioned data are in the existing public
[SoroushVahidi/mwfas-benchmark-extension](https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension),
under `releases/table45-v2-20261019/`. Historical releases are preserved.

Supply the immutable full code and data commits recorded in that release's
README. From a newly downloaded copy of this script, with Python 3.12:

```bash
env -i PATH=/usr/bin:/bin HOME=/tmp/mwfas-anonymous \
  python3 -I -B anonymous_replay.py \
  --code-revision CODE_COMMIT --data-revision HF_COMMIT \
  --directory /tmp/mwfas-table45-fresh
```

The destination must not exist. This downloads fresh public GitHub and HF
archives without credentials, checks their hashes, and runs the verifier from
the downloaded code. Its file-read guard permits only this new directory,
interpreter libraries, and system/TLS configuration. It rejects private `/home`
and `/project` reads and subprocess execution. Historical absolute paths inside
original metadata are provenance strings and are never opened. A system-call
trace can additionally be collected with `strace -f -e trace=%file -o trace.log`.

Expected output is PASS: 333 graphs, 3,423 orders, 3,423 original task records,
99 EXP06 topology pairs, 210 numerical solver evidence records (198 HiGHS and
12 igraph IP cross-checks), 41 displayed cells including 34 numeric cells, and
both tables PUBLIC_REPLAYABLE. A mismatch raises an error and no success receipt
is written. `public_replay.json` records immutable URLs, download hashes,
software/hardware, command and the verification result; `results/` contains each
ordering objective, reconstructed task classification, graph-level contrasts,
all 396 EXP06 method/weight pairs, 16 paired summaries, and every displayed-cell
comparison. Missing or extra task/order files fail rather than disappear.

The verifier uses only the Python standard library. It recomputes byte hashes,
canonical weighted and topology identities, full permutations, integer backward
weights and retained-DAG acyclicity. It reconstructs the original complete-case
selection, median-of-three seed aggregation, initializer tie-breaking by process
wall time, and the original 2,000-replicate topology-stratified bootstrap with
seed 20261017 and original iteration order. All displayed values are compared
at their frozen printed precision; unrounded statistics and graph-level results
are compared with the unchanged original cross-campaign package. Counts and
printed zeros must agree exactly. No optimizer runs during this replay.

## Original execution, distinct from saved-output reproduction

The archive includes exact original author-written runner dependency closures,
configs and selections under `table45/execution/exp04/` and `exp06/`, with their
original code revisions in the manifest. The original commands are preserved in
every run JSON, including seeds and budgets; run manifests record environments,
Slurm IDs, launch commands and task limits. Source selection records preserve
all graph-generation and weight seeds. Use the released exact graph files;
regeneration is a new experiment, never recovery of historical bytes.

For a separate stochastic optimization rerun, create an isolated Python 3.12.3
environment and install `networkx==3.6.1 pandas==3.0.2 pyarrow==24.0.0
igraph==1.0.0 scipy==1.17.1 numpy==2.5.4`. NumPy 2.5.4 was observed in the
retained EXP06 environment on 2026-10-19; the other versions are also recorded in
the original campaign manifests. Obtain the original MIT algorithm code:

```bash
git clone https://github.com/SoroushVahidi/minimum-weighted-fas-heuristics.git source
git -C source checkout --detach 40209c26966247d9bf9ad34764de4ac4181f98c2
```

For each original task selected for rerun, take its JSON `command` array, replace
only the interpreter, `--source`, `--graph`, `--order` and `--raw` paths with your
local environment, pinned source, released graph, and new output destinations.
Set `PYTHONPATH` to the corresponding `execution/exp04/src` or `execution/exp06/src`.
Preserve the module/subcommand and all algorithm/seed/budget/time-limit arguments.
For example, an EXP04 worker invocation is:

```bash
PYTHONPATH="$PACKAGE/execution/exp04/src" python -m mwfas_data.exp04_runner worker \
  --source "$PWD/source" \
  --graph "$PACKAGE/mwfas-exp04/production-output/graphs/exp04_er_n120_k03_r01.d" \
  --order "$NEW_OUTPUT/order.csv" --raw "$NEW_OUTPUT/worker.json" \
  --algorithm ipsns --seed 1 --budget 200
```

Run substantial computation through your scheduler; the example is instructions,
not an experiment performed by this release. Original EXP04 fresh IPSNS budgets
are 10/50/200/400 with seeds 1/2/3, alongside LR-TA, WMSF/L2 and weighted Eades.
EXP06 uses fresh 200-iteration IPSNS seeds 1/2/3, the three deterministic methods,
198 HiGHS tasks and 12 igraph IP cross-checks. Original caps and solver settings
are in the frozen configs and command arrays. No third-party executable is
redistributed, and software dependencies retain their upstream licenses.

Original process-wall times are reproduced numerically as recorded observations;
this is not a hardware-normalized runtime rerun. EXP04 records an AMD EPYC 7763
CPU; the EXP06 manifest does not record a CPU model. Stochastic outcomes and
runtime are not promised bit-identical on another execution or machine. HiGHS
status, gap and objective/bound consistency are numerical evidence, not an
independent exact-arithmetic mathematical proof. No solver is rerun to upgrade
that certification. Other manuscript tables are outside this release's complete
saved-output replay coverage.

Copyright 2026 Soroush Vahidi. Replay scripts: MIT. Documentation: CC BY 4.0.

## Published and independently replayed version

The successful public replay used code
`d5fb6c885a6ae55b3d4d9c8acec98442f535a8b8` and HF payload
`33902c7cc409794a43c17fc5428cf022f440da48` (tag `table45-v2.0.0`).
Its [public receipt and all cell comparisons](https://huggingface.co/datasets/SoroushVahidi/mwfas-benchmark-extension/tree/b66ce13298467a1f0b4928d55a7440e6ab948cb6/releases/table45-v2-20261019/replay)
record PASS. Coverage is 2/10 numerical tables and 3/17 central claim groups,
including the previously released Wikimedia saved-objective group.

`inventory_table1.py table45 table1.json` additionally checks the public metadata
inventory and graph/task/EXP07 reuse joins. It reports `PUBLIC_METADATA_ONLY`,
not full graph-byte reproducibility: 45 EXP03 and 38 EXP05 input bytes remain
outside this release. This script does not rerun ordering validation.
