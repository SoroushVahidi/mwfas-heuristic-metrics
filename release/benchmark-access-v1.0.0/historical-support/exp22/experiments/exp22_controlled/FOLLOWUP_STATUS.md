# EXP22 follow-up: running job and CI diagnosis

**Later status:** The dated running observations below are preserved as historical evidence. The corrected job has since completed and its independently audited, task-ID-reconciled EXP11/EXP22 findings are in [EXP24_INDEPENDENT_ANALYSIS.md](EXP24_INDEPENDENT_ANALYSIS.md). No experiment was relaunched for that analysis.

Read-only check on 18 October 2026 after the two-minute health handoff. This is an interim record, not a completed pilot audit.

## Slurm job `1426751`

At Slurm elapsed `00:06:42`, `squeue` and `sacct` both reported **RUNNING** on `n0006`, exit code `0:0` so far. `progress.json` reported 13/15 task checkpoints; the last was the CollegeMsg 120-second Xiong-restarts arm. The log still contained only the expected affinity lines, and no `fatal.json` existed. The output was **not** audited while the job was active. No ordering objective or corrected-task count is claimed from these checkpoints alone. The job was not modified, interrupted, or polled again during this follow-up.

The original EXP11 independent audit remains 37 PASS, 19 TIMEOUT, 22 INVALID: 56 audit-valid task statuses, of which 51 had a credited objective. The first EXP22 attempt contributed **one separately audited**, valid TIMEOUT task with a usable completed-restart objective. Its next task exceeded the cap and is invalid. The corrected job plans 15 disjoint tasks. Six original one-second tasks remain INVALID and must remain missing in any comparison. A future reconciliation must use task IDs, not row counts, to prevent duplicate credit; it must distinguish a valid timeout from whether a complete, before-deadline ordering was saved. This reconciliation cannot be finalized while job `1426751` runs.

## PR #34 GitHub Actions failure at `b411b820d011afb0a99ee3b895f697ed1ca1813e`

The two failed `validate / unit` checks are push run `39155986104` and pull-request run `39155992085`. Both check jobs have `runner_id=0`, an empty runner name, **zero steps**, and no available job log. GitHub's failure annotation says: “The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings.” A second annotation is an unrelated notice about future `ubuntu-latest` image migration. Thus no test, lockfile, or manifest step actually failed; no workflow or source repair is justified. The account billing/spending-limit gate must be resolved outside this task before GitHub Actions can run. No billing setting was changed.

At this commit, local `uv run --locked pytest -q` passed **15/15**, and `python scripts/check_manifests.py` passed all six manifests. These local results do not replace a completed GitHub Actions check.

## Next evidence gate

In a later review, check `sacct` once, then require the corrected output's frozen `audit_report.json` and `checksums.sha256` to pass. Verify all 15 task identities, input hashes, complete ranks, independently recomputed weighted objectives, DAG property, deadlines and checkpoints. Combine only the original 56 audit-valid tasks, the one audited first-recovery task, and independently validated corrected tasks. Preserve all INVALID one-second and failed-attempt records. Only then calculate paired five-graph summaries, and keep any production recommendation conditional on the scientific value of those summaries. No production job is launched here.

## Subsequent read-only status (18 October 2026, approximately 18:56:48 UTC)

Slurm `squeue` and `sacct` still reported job `1426751` **RUNNING**, elapsed `00:09:32`, on `n0006`; the recorded `0:0` exit field was provisional. `progress.json` showed 14/15 checkpoints, last task `exp05_college_full_count__b120__ipsns_frozen__s1`. No `fatal.json` existed; the log still had only the expected affinity lines. The final task and independent audit had not completed at this observation. The job was not changed or interrupted. No corrected-task PASS/TIMEOUT totals, objective comparisons, or EXP22 completion claim can be made yet.

The two `validate / unit` failures on this follow-up's starting commit `d24b6629226715c34eebbb218f9f287b11fd12ca` repeated the same account-level GitHub Actions annotation: recent account payments failed or the spending limit needs to increase. Both jobs again had `runner_id=0`, no runner name and zero steps. This confirms the earlier CI diagnosis; no code or workflow change was made.
