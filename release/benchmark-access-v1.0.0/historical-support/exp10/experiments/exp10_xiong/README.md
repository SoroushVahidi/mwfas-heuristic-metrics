# EXP10: bounded Xiong FASDC/RASstar versus frozen IPSNS

This study is stacked on the independent cross-campaign inventory in PR #22.
The prespecified `plan.json` selects 18 EXP04 weighted topologies (three
families × three sizes × replicates 1–2, degree five) and three full EXP05
source-parent views. There are 21 weighted inputs, two methods, and two seeds:
84 separately checkpointed process tasks. A one-CPU Wulver allocation runs
them sequentially on the same node. Each task has a 120-second process-wall
cap, including imports, graph parsing, conversion, and initialization.
Comparison work is bounded by 10,080 CPU-seconds; the allocation additionally
covers verified input preparation and independent audit overhead.

The Xiong source is the author-linked repository
`forgottencsc/FindingSmallFeedbackArcSetOnLargeGraphs` at
`8340e1633ba9290a567a882aff4d74f01b38102d`. It is used only for the
author-approved private research evaluation. No Xiong source or binary is
committed or redistributed; the repository has no explicit software license.
The original `fas_alg` entry point is compiled unchanged with GCC and invoked
as `W RASstar -r <seed> -p -o <rank_file>`. The `-w` flag is forbidden because
it replaces the graph's original arc weights. `-r` seeds `-p`'s label and arc
permutation. Without `-p` (or `-w`), changing `-r` alone is not a stochastic
replicate. The output is a zero-based rank for each original zero-based vertex.
The program's printed milliseconds start after graph loading and are recorded
separately from process-wall time. Compilation is outside task time and reported.

IPSNS is imported from the original frozen algorithm repository revision
`40209c26966247d9bf9ad34764de4ac4181f98c2`, using the EXP04/05 frozen
parameters, 200 fresh-run iterations, seeds 1–2, and the original graph.
An iteration cap and a process-wall cap are not equivalent computational work.
The frozen IPSNS parser can omit declared isolated vertices (as seen in the
prior EXP05 audit). The worker preserves its raw `order.csv` and writes a
separate `complete_order.csv` only if every missing vertex is isolated. The
second auditor verifies the exact missing IDs, unchanged ordering of all
original vertices, identical original-graph objective, and both file hashes.
Such endpoints are labeled `PASS_DERIVED_ISOLATES`, never raw complete PASS.
Any missing nonisolated vertex or altered objective stops the campaign.

The original DIMACS files remain read-only in EXP04/05 production trees.
`input_contract.py` checks byte hashes, canonical graph hashes, vertex and arc
counts, positive integer weights, 64-bit sums, and W conversion. A second
parser in `independent_audit.py` rechecks original graph content, exact rank
coverage, weighted backward objective, retained DAG, result status, and W
conversion. Failed and timed-out tasks remain in all denominators. The pair
table defines `(B_Xiong-B_IPSNS)/total_arc_weight`; negative favors Xiong.
Its baseline-relative column is `(B_IPSNS-B_Xiong)/B_IPSNS`, undefined for
zero IPSNS objective. Strict wins exclude ties. Synthetic topologies are the
units; the three real networks are separate case studies. Two topologies per
synthetic cell permit descriptive comparisons only.

The public review package is metadata-only. Raw graphs, converted W files,
orderings, process logs, third-party source, and executable remain private on
Wulver. After the job terminates, independently inspect `audit_report.json`,
`audit_inventory.csv`, `paired_results.csv`, `manifest.json`, and
`checksums.sha256` before making scientific claims. A successful scheduler
state or complete task count does not constitute scientific validation.
