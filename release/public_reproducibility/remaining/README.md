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

Complete public replay passed for all four packages on 2026-10-19. The dataset
revision is `667e164d0768d635a73692cd594801f10fe12382` and the tested verifier revision is
`4a89ffe5d0b8d9a0510ac0e715b9baef84e3c62f`. All numerical table cells match the frozen manuscript.
See `public_receipts/J1.json` through `J4.json` and `summary.json`.

For each scope, use a new directory and the public bootstrap from the pinned code:

```sh
env -i PATH="$PATH" python3.12 -I -B -S anonymous.py \
  --code-revision 4a89ffe5d0b8d9a0510ac0e715b9baef84e3c62f \
  --data-revision 667e164d0768d635a73692cd594801f10fe12382 \
  --scope J1 --directory /tmp/mwfas-public-J1-new
```

Run J2, J3 and J4 in separate new directories for the other packages. Do not reuse
an existing replay directory. The guard permits only downloaded artifacts, the
active interpreter standard library, and necessary operating-system/TLS files.
No credentials, private caches or optimizer processes are permitted. The package
contains 4,390 hash-manifested files (including its index) plus the manifest itself;
objects are deduplicated. Eleven invalid original EXP05 order files retain FAIL
and are independently rejected as incomplete permutations. The inventory replay
additionally reconstructs the existing public EXP04/06 and Wikimedia graph
identities; its 442 graph rows are normalization-contract scoped, not a global
independent-source count.

Original private Slurm archival jobs and the accepted 5,007-witness audit were
not repeated. GitHub Actions could not start due to billing restrictions; 25
local tests, manifest validation and the four Slurm public replays passed.

