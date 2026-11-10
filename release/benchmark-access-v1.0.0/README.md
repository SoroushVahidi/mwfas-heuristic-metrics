# MWFAS Benchmark Access and Historical Support — benchmark-access-v1.0.0

This additive release links existing public graph/order/reference evidence without duplicating large archives. It supports the Discrete Optimization benchmark manuscript; no journal acceptance or publication is claimed.

## Verified access census

Fresh anonymous downloads parsed and hash-checked all 442 contract-scoped weighted inputs (343 labeled topologies), including 44 empirical views from eight source lineages. There are now **414 directly released inputs and 28 upstream-reconstructed inputs** in this register. The earlier 381/61 split describes the older release, not current access. The additional EXP29 witness package is a separate protocol scope; do not add its record count to 442 without an identity join.

All **5,131 feasible outcomes** in the unchanged 5,254-record outcome register have publicly resolvable complete-order witnesses and exact integer rescoring matches. Original statuses remain 4,933 PASS, 198 CERTIFIED_OPTIMAL, 110 TIMEOUT, 11 FAIL and two SKIPPED_DEPENDENCY. No failed, missing or timeout observation was promoted to a successful outcome. The table45 subset remains 333 inputs and 3,423 outcomes.

The reference register remains **243 records: 218 solver-certified numerical optima and 25 unresolved bounds**. We also rescored the 45 separate EXP07 reference orders. This verifies feasible objective witnesses, not independently rerun solver certificates or exact-arithmetic optimality proofs. Separate EXP28/29/30 observations and repeated event orders are not added to the 5,254 count.

## Files and direct use

* `graphs.csv`: full corrected 442-record identity/provenance register. Only the previously blank 23 topology fields were completed in the preceding additive release.
* `graph_access.csv`: raw/weighted/topology hashes, source parents, exact immutable archive/file URLs and member paths for all 442 records.
* `run_outcomes.csv`: unchanged 5,254-row outcome/status/seed/budget register.
* `outcome_access.csv`: per-outcome saved-order hash, package member and exact objective verification status. Nonfeasible records retain original statuses.
* `numerical_references.csv`: exact 243-row reference metadata with quality class, lower/upper bounds and certification qualification.
* `source_parents.csv` and `upstream_recipes.json`: source identity/version/checksums/transformations. Historical rights fields are dated metadata; current distribution licenses remain component-specific.
* `SUMMARY.json`: fresh anonymous verification counts and download receipts; zero failures and zero optimizer runs.
* `verify_public_access.py`: independently reproduce the access audit with Python 3.12 and NumPy, using a new output directory. Example: `python -B verify_public_access.py /fresh/mwfas-access-check`. It downloads pinned public archives, verifies their checksums, resolves all inputs, rescores the 5,131 outcomes and 45 EXP07 reference witnesses, exercises the candidate-order CLI, and replays supplementary S1–S3. No original private path is read.
* `CAMPAIGN_SCOPE_INVENTORY.csv`: EXP03–EXP30 scope-by-scope availability and verification boundaries.
* `historical-support/`: 93 additional author-created diagnostic/pilot code, config, audit and analysis files; source hashes and sanitization mappings are in `HISTORICAL_SOURCE_INVENTORY.csv`. Their public availability and transport integrity do not establish complete campaign replay. See its README.
* `fidelity-cases/`: four original generated test graphs and eight saved external-method rank outputs; independently rescored without executing the external binary. `FIDELITY_VERIFICATION.json` records the checks.

The preceding benchmark-supplement-v1.0.0 release contains the public candidate-order interface, 34-/47-record profiles, all 442 structural descriptors, EXP29/30 witnesses, and S1–S3 reconstruction. The 47-record profile resolves 39 published-byte inputs plus eight upstream inputs. Neither profile is claimed representative of general MWFAS instances.

## Availability distinctions

1. **Public and independently verified:** the input/order/reference links and objective checks above; prior public table and supplementary replays; fidelity cases.
2. **Public but not independently replayed as full experiments:** newly released historical code/configuration/reports for EXP08–11, EXP22/24/25/27. Their original qualifiers and failures remain intact.
3. **Local-only:** original unsanitized custody reports and site-specific scheduler files; their research-relevant source/hash projections are published. Complete raw event trees for some older pilots were not found in accessible local worktrees and are reported as unavailable here rather than inferred from summaries.
4. **Unavailable or external-only:** original historical HF graph/order bytes, pre-May-2026 Wikimedia monthly raw snapshots, and third-party original-author binaries/proprietary solvers. Upstream-only SNAP/Ali graph inputs have tested exact reconstruction routes; no source substitution or implied redistribution grant is made.

Historical documentation may refer to old JDSA plans, private directories or earlier publication gates. Those are preserved historical context, not the current availability statement. Current manuscript framing is a reusable MWFAS benchmark/evidence resource. This release changes availability, not scientific observations or conclusions.
