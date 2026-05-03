# Runbook: Two Consecutive Nightly Replay Failures

**Alert:** Two nightly replay jobs fail in a row
**Severity:** P2 page
**SLO impact:** the replay net is the regression detector — when it's
red, behavior changes ship blind. Two consecutive failures indicate
a real problem, not a flake.

## Symptom shape

`.github/workflows/nightly-replay-eval.yml` runs at 02:00 UTC daily.
Today it operates in **harness-validation mode** — it generates 5
synthetic recordings and replays them in `--dry-run`, asserting:

- The script can read JSONL recordings produced by `EvalRecorder`.
- `diff_records` produces non-error metrics.
- HTML report renders without crashing.

When the team flips `enable_eval_recording=True` in production, the
synthetic step is replaced with an artifact pull, and the same job
becomes a real regression check. **A double-failure today** = the
harness is broken. **A double-failure post-cutover** = a recent
production change regressed against yesterday's recordings.

## First 10 minutes

1. **Open the failed run in GitHub Actions.** The artifacts tab has
   `replay-report-YYYY-MM-DD.html` — even on failure, it captures
   what the harness saw before crashing.
2. **Check whether it's the same failure twice or two different
   failures:**
   - Same failure → systemic. Likely a code change broke the
     harness or an artifact source.
   - Different failures → flaky environment. Less urgent; investigate
     but don't roll back.
3. **Determine the mode:**
   - Harness-validation mode (today) — the failure is in the
     `replay_eval.py` script itself or the synthetic generation step.
   - Real-recording mode (post-cutover) — the failure is in the
     model behavior, the diff thresholds, or the artifact pipeline.

## Decision tree

### Branch A — Harness-validation mode failure

- Run the harness locally with the workflow's exact command to
  reproduce:
  ```bash
  python scripts/replay_eval.py \
      --base-dir /tmp/wiii_replay_smoke \
      --day 2026-05-03 --org smoke-org \
      --dry-run --report-out /tmp/report.html \
      --fail-on-regression
  ```
- If the failure is reproducible, look at the recent commits to
  `scripts/replay_eval.py`, `app/engine/runtime/eval_recorder.py`,
  `app/engine/runtime/replay_context.py`. Last successful run's
  commit + bisect.
- If the failure is **not** reproducible locally, the issue is the
  GitHub Actions environment — Python version, missing system
  package, time zone. Check the workflow log for setup-step output.

### Branch B — Real-recording mode failure (post-cutover)

- **Pull the recordings** the failed job replayed:
  ```bash
  gh run download <run-id> --name replay-report-<day>
  open replay-report-<day>.html
  ```
- The HTML report flags which records regressed and what the diff
  metrics were. Common patterns:
  - **token_jaccard < 0.85 across many records** → model output
    materially changed. Roll back any recent prompt or model
    config change.
  - **sources_overlap < 0.70** → RAG retrieval changed. Recent
    embedding or hybrid-search change is the suspect.
  - **latency_delta_ms > 5000** for many records → performance
    regression. Profile the hot path.
- **If the regression is intentional** (e.g. a prompt rewrite the
  team agreed to ship), update the regression thresholds in
  `REGRESSION_THRESHOLDS` (top of `replay_eval.py`) before silencing
  the alert.

### Branch C — Different failure each night

- Treat as flake. File a low-priority ticket, attach both run logs.
- If the same flake recurs > 3 times in 30 days, escalate it to a
  proper ticket — the harness should not be flaky.

## Mitigation

- The replay job does NOT block any deploy. It's an after-the-fact
  detector. Do not rush to fix at 03:00 UTC; wait for business hours
  unless the failure correlates with another active incident.
- **Do not disable the workflow** to silence the alert. The cost of
  a missed regression > the cost of a noisy alert.

## When the alert clears

- The next nightly run must pass cleanly. One green night = clear.
  Two green nights = quietly clear; no further action.
- If the cause was a real regression that shipped, file a postmortem
  after the rollback or threshold update.

## Related runbooks

- None. The replay net is its own concern; it does not interact
  with the live request path.
