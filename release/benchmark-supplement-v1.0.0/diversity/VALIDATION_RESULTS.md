# Validation results

**PASS: 442/442 complete feature records, no missing or malformed input after applying the documented format contracts.** No graph bytes or historical results were modified.

| Check | Result | Saved evidence |
|---|---|---|
| Original authoritative EXP18 register available and identical to audit snapshot | PASS | `evidence/INPUT_INVENTORY.json` |
| Every authoritative graph accounted for once | 442/442 | `GRAPH_DIVERSITY_FEATURES.tsv`, `evidence/OUTPUT_VALIDATION.json` |
| Local input availability and raw/canonical identities | 442/442 | `GRAPH_INPUT_VERIFICATION.tsv` |
| Distinct contract-scoped weighted identities / measured labeled topologies | 442 / 343 | Feature table and validation JSON |
| Complete declared vertex sets, sizes and total weights | 442/442 | Primary identity/metadata assertions; independent check |
| Independent parsing and SCC/degree/weight calculation | 442/442 | `evidence/INDEPENDENT_CONSISTENCY.tsv` |
| Source-parent joins | 288 groups covering 442 records | `SOURCE_PARENT_DIVERSITY.tsv` |
| Current public-access classifications | 381 direct; 61 reconstruction | Independent ledger joins |
| Existing feasible-outcome/reference coverage | 5,131 outcomes; 218 certified + 25 bounded graph references | Independent ledger joins |
| Parser/feature unit tests | 10 passed | `evidence/TEST_RESULTS.txt` |
| Exhaustive SCC oracle | All 4,096 directed simple graphs on four vertices | Mutual-reachability oracle inside test suite |
| Compact-profile membership, hashes, topology uniqueness and coverage | PASS | `evidence/OUTPUT_VALIDATION.json` |
| Record/topology/parent/family weights sum to one within their defined scopes | PASS | Output validator |
| Existing EXP05 source-composition table | All ten six-decimal means matched | `EXISTING_EXP05_COMPOSITION_CHECK.tsv` |
| Saved EXP06 raw solver evidence hashes | 198/198 | `DIFFICULTY_SOLVER_EFFORT.tsv` |
| Repeated numeric outputs and figures | 25 byte-identical artifacts | `evidence/REPEATABILITY.json` |
| Original repository/worktree HEAD and tracked-change status | Unchanged | Initial/final project-state JSON |

The focused tests cover isolated vertices, empty/edgeless inputs, known component structures, invalid headers/counts/endpoints, self-loop/parallel rejection for simple graphs, NaN/infinite/nonpositive/noninteger weights, Ali's graph-name header and transit-time annotation, Wikimedia UTF-8 labels and multiplicity, distinct weighted variants on the same topology, moments/Gini and tied-weight prevalence. Undefined empty-graph weight statistics are explicitly NA. Actual benchmark inputs all have positive arc counts, so all requested structural/weight descriptors are computed.

The primary iterative Kosaraju implementation was independently cross-checked using SciPy strong connectivity on a separately parsed sparse graph for every actual record. Independent checks also cover declared isolates, maximum/average degrees, sizes, total/mean/extreme weights, cyclic-edge counts, SCC vertex fractions, raw checksums, parent joins and current rights/access labels. No prior result was used as a substitute for computing the features.

The implementation initially rejected Ali records because it restricted the second header token to standard graph-type labels. The upstream README documents that token as a graph name. The adapter was corrected to implement `p NAME n m`, while preserving arc counts, vertex bounds, integer weights, duplicate/loop checks and exact raw/canonical identity comparisons. The initial development receipt is preserved. This was a parser-support correction, not repair or substitution of an invalid benchmark graph. The final tests and independent check ran against the corrected parser.

Figures were exported to vector PDF/SVG and 300-dpi PNG, visually inspected, and repeated with timestamp-free/deterministic metadata. Their bytes match across the two runs. Scatter points are records, with overlaps for related/paired inputs; they are not independent-sample plots.

Limitations are explicit: Wikimedia has an incident-label vertex universe, not a separately declared set of possible isolated source vertices; weights are integer-contract data; labeled hashes are not non-isomorphism proofs; original sources are not assumed statistically independent; missing numerical references remain NA; prior public availability is reused rather than freshly retested in this task; scientific feature statistics use floating-point ratios/moments.

No GitHub Actions, hosted CI, exact solver, heuristic run, original experiment rerun, publication, push, branch/worktree edit, manuscript change or deletion of user artifacts occurred. The local analysis completed in short bounded commands; no long-running background job remains.
