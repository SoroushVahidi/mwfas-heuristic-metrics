# Federated benchmark profile resolution

Run `python profile_tools/resolve_profiles.py /fresh/output-directory` from this release. Python 3.12 standard library only. The destination must not exist. Every graph must match its raw, weighted and labeled-topology hash, declared size and profile identity. A changed upstream file causes failure, never substitution.

The 34-record core reuses the immutable table45 archive without duplication. The 47-record profile retains all core entries and one view per eight empirical parents/five Ali collection strata. It remains a federated profile: bundled licensed views and existing public inputs are used when available; SNAP and Ali inputs are downloaded from their pinned sources. The code-only distribution can also reconstruct IRS/Census/EXIOBASE views upstream. `upstream_specs.json` contains exact source URLs/member paths/commits/checksums/transformation metadata. OpenFlights uses its separately licensed derivative and retains the pinned reconstruction route.

`diversity/BALANCED_SUBSET_MANIFEST.tsv` and `BALANCED_PROFILE_WEIGHTS.tsv` are the original deterministic selections. `diversity/scripts/analyze_coverage.py` reproduces them from the 442 supplied feature rows; run on a copy because it writes its output files. No new profiles or statistical results are selected in this release. Candidate-order interface support is table45 only: Ali annotation and Wikimedia labeled/multiplicity contracts must not be silently passed to that interface.

The upstream adapter files originate in the already public project release at commit 4a89ffe5d0b8d9a0510ac0e715b9baef84e3c62f. Source retrieval and saved-output replay do not run the original algorithms.
