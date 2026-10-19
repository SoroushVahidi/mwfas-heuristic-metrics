# Remaining printed tables: independent replay

Packages J1 (EXP05: printed Tables 5, 8, 12), J2 (EXP07: Table 11),
J3 (EXP12/13: Table 10), and J4 (EXP03 and inventory: Tables 3, 4)
share a content-addressed evidence archive. Identical objects are stored once.
Original run statuses and historical selections are immutable. Derived EXP05
recovery records are kept separately and excluded from all original counts.

`build.py ORIGINAL_ARCHIVES OUTPUT` validates the four sealed archival manifests,
then creates public projections of original author-owned records and saved orders.
The lineage ledger records original and projected hashes. Only private location
prefixes are redacted; original archives are preserved separately. Third-party
graphs and proprietary solver/RASstar executables are excluded. Synthetic input
bytes, original complete orders, statuses and original author-generated worker
records are included. No optimizer is invoked by any script here.

`replay.py --package EXTRACTED --output NEW_DIRECTORY --scope J1 --mode public`
retrieves exact pinned third-party sources, verifies graph and order identities,
complete permutations, retained DAGs and weighted objectives, and independently
recomputes all displayed cells before comparing to frozen LaTeX rows. Substitute
J2, J3 or J4 for the other packages. Python 3.12 standard library is sufficient.
Private mode uses `--original ARCHIVAL_ROOT` and reuses byte-bound accepted order
audits; it is never evidence of public reproduction. J4 retrieves the already
public EXP04/06 and Wikimedia artifacts, reconstructs structural hashes from
actual graphs, and verifies task-count joins and EXP07 reuse. It reuses accepted
Wikimedia objective audits instead of repeating them.

Tables 6 and 7 correspond to internal T4 and T5; printed Table 9 corresponds
to internal T10. This package does not change their completed public replays.
EXP07 certificates remain numerical solver certificates, not exact-arithmetic
proofs. The Ali inputs reproduce the recorded EXP12 run, not earlier Hugging Face
runs for which historical graph-byte identity remains unverified.

No new coverage is claimed until a complete fresh anonymous public replay passes.
