# MWFAS public supplemental evidence — benchmark-supplement-v1.0.0

**Public saved-output witness package with upstream reconstruction for SNAP inputs.** This archive independently reconstructs the supplemental S1–S3 findings from existing graph/order/event evidence. It does not rerun optimization, prove optimality, establish experimental independence, or make a failed campaign successful.

From a fresh extraction, with Python and NumPy installed:

```sh
cd supplementary-evidence
python protocol/hydrate_external.py /tmp/mwfas-snap-cache
sha256sum -c SHA256SUMS
python verification/guarded_verify.py > ../verification.json
python verification/verify.py --tables-dir ../regenerated-tables > ../tables-verification.json
```

The guarded command rejects network calls, subprocess creation, writes, and evidence reads outside the extracted package. Interpreter library reads are allowed. Commands contain no private filesystem dependencies. A PASS verifies all manifest entries, all selected event orders and horizons, original/selected/audited status distinctions, all 185 EXP05 deterministic orders, exact aggregation and manuscript S1–S3 rows. The `source/` keys in historical records are logical identifiers resolved through `witnesses/index.json`, not folders to locate on a cluster.

## Contents and evidence boundaries

- `objects/`: SHA-256 addressed bytes. 84 graph file identities cover 45 EXP29 generated inputs, 37 EXP05 views and two additional EXP30 graphs; Wiki-Vote is reused from EXP05. Many repeated orders/stdout files share one object.
- `witnesses/index.json`: every logical file key, original SHA-256, storage SHA-256, captured original nanosecond mtime, size and sanitization flag. External RASstar binary is hash-only and excluded.
- `inputs/graph_manifest.json`, `selection/selection_rules.json`: graph/selection identities; full EXP29 roster and both historical ledgers remain in the indexed protocol/combined-view files.
- `tables/`: unchanged manuscript supplement, reproduced S1–S3 CSVs and row-level witness crosswalks.
- `protocol/`: optional upstream reconstruction recipes and source metadata. These use the network only when explicitly invoked; they are not part of offline verification.
- `verification/`: adapted prior independent graph/order/event checker plus separate EXP05 exact aggregation and read-confinement wrapper. It imports no optimizer.
- `receipts/`: prior validation, collection chain checks, sanitization bridge and preparation verification. Original hashes and stored hashes are intentionally distinct for redacted provenance.

To inspect one indexed file, use `python verification/materialize.py LOGICAL_KEY ../exported-file` (destination must not already exist). Graphs and complete orders are byte-identical to collected originals. Private storage prefixes and node/job labels were redacted only from provenance text; original-to-stored digest mappings are explicit. Original filesystem timestamps are evidence records, not cryptographically authenticated clocks. Sanitized provenance cannot be independently rehashed to its original byte digest without the private original; collection checked that digest before redaction.

EXP29 retains its failed 180-task campaign and a post hoc whole-arm selection of 90 original-v1 tasks (IPSNS 2901 versus RASstar single 1). The 45 paired results are 33/5/7. EXP30 has 12 selected observations, 24 dependent horizon values, 3 completed PASS and 9 valid TIMEOUT observations, 7 v1 and 5 v2 controllers. LODES mixes controllers. No pooled EXP28/EXP30 inference is authorized. EXP05 is the 37-view five-deterministic-arm cohort, not the separate 18/38 long-budget IPSNS cohort.

The full nonselected EXP29 optimizer event trees and noncohort EXP05 orders are not needed for these claims and are excluded. Their original status/roster/checkpoint records are retained. The package reproduces the reported failed-campaign classification from preserved audits, rather than independently rerunning every excluded observation's audit. No missing selected witness is substituted with a summary.

`PACKAGE_MANIFEST.json` hashes all payload files; `SHA256SUMS` also hashes the manifest but not itself. Final ZIP hashes are in the external delivery manifest/receipt, avoiding self-referential checksums. Component licenses and exact external/withheld inventories are in LICENSES.md and FILE_DISPOSITIONS.tsv.

## New public packaging

Seven SNAP graph views, seven node maps and two logical converted inputs are upstream-only. hydrate_external.py recreates exact content-addressed objects from anonymous source downloads and refuses any hash mismatch. These reconstructed objects are explicitly allowed by verification; they are not part of the downloadable payload. All other eligible objects from the validated package are included. The original selected-vs-recovered evidence and original controller distinctions are preserved. The complete original 180-task campaign is not newly certified; selected witnesses reproduce S1–S3. This is saved-output replay, never algorithm execution.
