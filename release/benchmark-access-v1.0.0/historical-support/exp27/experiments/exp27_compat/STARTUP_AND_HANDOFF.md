# EXP27 Wulver startup and independent-audit handoff

**Observed state: RUNNING_HEALTHY at 3:16 elapsed; final audit pending.** This is a startup record, not a scientific result or a claim that the 12-task pilot has passed validation.

## Frozen launch

- Experimental source branch: `feat/exp27-controlled-time-compatibility-pilot`, frozen release commit `aa047f4735a7160b4f5127ef03cf003ce0784b8f` (based on EXP25 preflight `018ea9edc73c32fff71af54cc71b28de96ce9f14`). Release archive SHA-256: `403dc897836d9782aaebcf43b54a4e5b158aef98a3ecb47521eee839b909b86f`.
- Actual Slurm job **1426807**, submitted 2026-10-18 20:25:22 UTC; began running 20:25:23 UTC. Wulver `debug` partition and QoS, node `n0111`, one CPU, 8 GB, one-hour allocation. This queue was chosen after `sbatch --test-only` accepted the one-hour request and estimated an immediate start; `general`/`low` estimated a later start. It does not change the frozen method caps.
- Exact launch uses `sbatch --parsable --export=ALL --output=<private EXP27 root>/logs/aa047f4-%j.out --error=<private EXP27 root>/logs/aa047f4-%j.err <private EXP27 root>/releases/aa047f4-v1/experiments/exp27_compat/run.sbatch` after sourcing the mode-600 private `status/launch-aa047f4.env`. The private root is retained only in Wulver's `status/job-1426807.json`, not this Git document.
- Private evidence under that root: `output/aa047f4-pilot-v1/{manifest.json,progress.json,tasks/,checkpoints/}`; Slurm logs `logs/aa047f4-1426807.{out,err}`. On successful completion, the same job runs the separate auditor and writes `audit_report.json`, `task_inventory.csv`, and `checksums.sha256`. No old output directory is reused or overwritten.

## Pre-submission decision and checks

EXP11/22 used different EXP04 `r01/k05` views, and EXP13 did not run IPSNS on LODES. No equivalent active or queued EXP27 job existed immediately before submission. The frozen manifest has exactly 11 synthetic 30-second tasks and one LODES 300-second IPSNS task, 630 nominal cap seconds. Both DIMACS byte hashes and canonical weighted hashes match EXP25. The baseline checkout is exactly `40209c26966247d9bf9ad34764de4ac4181f98c2`; its IPSNS file hash matches the published EXP24 audit. The original-author Xiong checkout, Git-archive hash, and binary SHA-256 match the authenticated EXP24 records. The EXP13 adapter release and `igraph`/`networkx` versions match the prior audited environment. Wulver preflight passed all 12 identities. A read-only LODES parser/order smoke independently reproduced the audited EXP13 LR-TA objective 68,654, without a new method task. Local checks: 20 tests passed, six manifests valid, EXP25 arithmetic valid, and Slurm shell syntax valid.

Two earlier **read-only** Wulver preflight releases rejected the EXP13 `p graph` header and fifth arc annotation. The separate independent parser was corrected, regression-tested, and released at the above frozen commit before any Slurm submission. Those failed preflight releases remain private; they contain no EXP27 pilot output.

## Running-health observations

| Slurm elapsed | State and node | Progress | Liveness/fault evidence |
|---|---|---|---|
| 0:23 | RUNNING, `n0111` | 0/12; LR-TA active | Progress heartbeat created; one-CPU affinity logged; no error/fatal marker. |
| 1:28 | RUNNING, `n0111` | 4/12; WMSF insertion active | Four durable task checkpoints, advancing heartbeat, `sstat` MaxRSS 193,244 KiB, no fatal marker. |
| 2:43 | RUNNING, `n0111` | 9/12; Xiong restarts seed 1 active | Nine checkpoints, advancing heartbeat, MaxRSS 193,244 KiB, empty Slurm stderr. |
| 3:16 | RUNNING, `n0111` | 10/12; Xiong restarts seed 2 active | Ten checkpoints, first restart task classified TIMEOUT, advancing heartbeat, MaxRSS 193,268 KiB, no fatal marker. |

The controller and auditor run inside the persistent Slurm job, not in this Codex session. No production campaign or optional seven-parent stratum was launched. Do not assign pilot objectives or the LODES availability-gate result from this startup record. After the job becomes terminal, inspect `sacct` exit accounting and logs, run or verify the frozen independent auditor over all twelve tasks, check the checksum seal, and then produce a separately versioned sanitized result and GO/MODIFY/NO-GO decision. Preserve every failed/timeout/invalid artifact and do not rerun a task implicitly.
