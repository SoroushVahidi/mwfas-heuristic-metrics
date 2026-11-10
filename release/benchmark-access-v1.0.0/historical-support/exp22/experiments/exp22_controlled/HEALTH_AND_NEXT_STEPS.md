# EXP22 Wulver pilot health record

Recorded 18 October 2026. This file contains no private absolute Wulver path. The private Slurm snapshot `status/1426751-scontrol-at-health.txt` under the EXP22 Wulver root preserves the **exact `SubmitLine`**, full environment-path arguments, allocation, and command; SHA-256 `391bcf36779bb4fc02a92ee7e5a202a3d091b2a9aa849dc88de7b59915e8fbbf`. The root and full paths are supplied to the author privately, not committed. Reproduction must use the frozen release revision and a new output directory.

## Submission history

| Job | Frozen code | Slurm accounting and decision |
|---|---|---|
| `1426749` | `a08fd9be68d86cc4fb460cb54b3436cb93ecfd61` | First attempt, `FAILED`, exit `1:0`, elapsed `00:00:47` on `n0006`. Controller stopped on a 30.641 s task against a 30 s cap. Its first 10 s task, wall 9.504 s, passed a separate frozen independent audit of graph/order/1,388 restart events. It is not repeated. No two-minute healthy claim for this job. |
| `1426751` | `1adb34b5679661be93a4bbab921510a1d3947843` | Corrected, disjoint 15-task pilot. Submitted and entered RUNNING at `2026-10-18 18:47:16 UTC` (Slurm displayed 14:47:16 local). Account `ikoutis`, partition `general`, QoS `low`, node `n0006`; allocated one CPU, one task, 8 GB, 30 min; one CPU affinity in the run manifest. Pilot outcome is pending. |

## Actual RUNNING observations

| Approximate UTC | Slurm runtime/state | Credible liveness and fault check |
|---|---|---|
| 18:48:10 | `00:00:54`, RUNNING, `n0006` | `progress.json` 2/15; two task checkpoints; batch CPU 2 s, MaxRSS 67,544 KB; no fatal marker; Slurm affinity line in log. |
| 18:49:28 | `00:02:12`, RUNNING, `n0006` | `progress.json` 8/15; eight task checkpoints; batch CPU 14 s, MaxRSS 115,104 KB; no fatal marker or Python/solver traceback. Advancing checkpoints across the two observations establish actual execution. |
| 18:49:40 | `00:02:24`, RUNNING, `n0006` | Slurm confirmed allocated CPU=1, memory=8 GB, node=1, exit code still `0:0` while running. The exact launch `SubmitLine` was sealed in the private status snapshot. |

The two meaningful observations are 78 seconds apart, with the final observation more than 120 seconds after the actual RUNNING start. The pilot was **RUNNING_HEALTHY at handoff**, not completed. Its worker and frozen independent auditor continue within Slurm without this Codex session. Slurm log size remained 74 bytes because task progress is written to `progress.json` and per-task checkpoint files; log growth is not the heartbeat for this runner. No final objective or production inference is claimed.

## Private artifact map and recovery

All paths below are relative to the private EXP22 Wulver root. The original EXP11 data, sources, and output remain in their separate roots and are read only.

| Item | Relative path |
|---|---|
| Corrected immutable code release | `releases/1adb34b/` |
| Slurm log | `logs/1adb34b-1426751.out` |
| Run manifest, progress, task checkpoints, raw private ranks | `output/1adb34b-recovery-v1/manifest.json`, `progress.json`, `checkpoints/`, `tasks/` |
| Independent final audit, if successful | `output/1adb34b-recovery-v1/audit_report.json`, `task_inventory.csv`, `comparisons.csv`, `checksums.sha256` |
| Initial failed attempt | `output/a08fd9b-recovery-v1/`, `logs/a08fd9b-1426749.out` |
| First-task independent audit | `output/a08fd9b-first-audit-v1/` |
| Full Slurm command and allocation snapshot | `status/1426751-scontrol-at-health.txt` |

When job `1426751` finishes, use `sacct -j 1426751 --format=JobID,State,Elapsed,ExitCode,MaxRSS,AllocCPUS,NodeList -X` once in a later review. Verify `checksums.sha256`, require the frozen independent `audit_report.json` to show 15 audited tasks, zero INVALID and zero violations, and retain PASS/TIMEOUT distinctions. Combine these 15 only with EXP11's 56 audit-valid tasks and the separately audited first recovery task; the six one-second and one failed second-attempt records remain INVALID. The combined data can answer a limited Xiong–IPSNS feasibility question only. No production submission is authorized by a healthy startup.
