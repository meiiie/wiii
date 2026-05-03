# Canary Onboarding — Native Runtime

Phase 28 of the runtime migration epic ([#207](https://github.com/meiiie/wiii/issues/207)).
Step-by-step procedure for adding a new organisation to
`native_runtime_org_allowlist` and validating the rollout. Companion
to the [SLO doc](SLO.md) — the SLO defines the bar; this doc defines
the path to crossing it.

## Pre-flight

Before adding any org, confirm:

- [ ] **Phase 19 shipped on main** — `native_chat_dispatch` is in the
      production binary. Check `git log origin/main --grep='phase-19'`.
- [ ] **`/metrics` scrape working** — Phase 16 endpoint reachable from
      your monitoring; `runtime.native_dispatch.runs` counter
      produces non-empty output.
- [ ] **Runbooks reviewed** — primary on-call is familiar with
      [`runbooks/chat-5xx-surge.md`](runbooks/chat-5xx-surge.md) and
      [`runbooks/chat-latency-spike.md`](runbooks/chat-latency-spike.md).
- [ ] **Baseline captured** — see "Capture baseline" below. You need
      legacy-path numbers to compare against.

If any of the above is unchecked, **stop**. Onboarding without these
guardrails turns the canary into a blind cutover.

## Procedure (per-org, ~15 minutes plus a 1-hour soak)

### 1. Pick the canary

The first canary should be **a low-volume, internally-controlled org**.
Ideal:

- < 100 chat requests/day (so an issue affects few users).
- Internal staff or willing pilot customer (so feedback loop is fast).
- Has at least one engineer who can sanity-check responses manually.

Document the chosen org_id in the runbook log + the
`#wiii-rollout-log` channel.

### 2. Capture pre-flight baseline

Run the [Locust harness](../../loadtest/README.md) against the org's
typical traffic shape, BEFORE flipping the flag:

```bash
WIII_LOAD_PROFILE=legacy_only \
WIII_HOST=https://api.wiii.example.com \
WIII_API_KEY=$WIII_PILOT_KEY \
WIII_USER_ID=canary-baseline-1 \
WIII_ORG_ID=canary-org-1 \
locust -f loadtest/locustfile.py --headless \
    -u 30 -r 3 -t 5m \
    --csv reports/canary-org-1-baseline
```

Capture:

- `_stats.csv` — p50 / p95 / p99 / fails for each endpoint.
- `_failures.csv` — any non-200 (other than documented 503s).
- A scrape of `/metrics` at end-of-run for histogram totals.

### 3. Flip the flag

Edit production env (or your config-as-code source of truth) to add
the org_id to `native_runtime_org_allowlist`:

```bash
# Example: docker-compose.prod.yml or k8s ConfigMap
NATIVE_RUNTIME_ORG_ALLOWLIST='["canary-org-1"]'
```

Restart the runtime workers. Verify the routes register:

```bash
curl -s -H "X-API-Key: $WIII_API_KEY" \
     -H "X-Organization-ID: canary-org-1" \
     -H "X-User-ID: smoke-test" \
     -X POST https://api.wiii.example.com/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "wiii-default", "messages": [{"role": "user", "content": "ping"}]}'
```

Expected: HTTP 200 with an OpenAI-shape envelope. HTTP 503 ⇒ flag not
read; check workers re-ran with the new env. HTTP 401/403 ⇒ auth issue,
not a runtime issue.

### 4. Capture canary numbers

Same Locust command as step 2, but `WIII_LOAD_PROFILE=edge_only`:

```bash
WIII_LOAD_PROFILE=edge_only \
WIII_HOST=https://api.wiii.example.com \
WIII_API_KEY=$WIII_PILOT_KEY \
WIII_USER_ID=canary-canary-1 \
WIII_ORG_ID=canary-org-1 \
locust -f loadtest/locustfile.py --headless \
    -u 30 -r 3 -t 5m \
    --csv reports/canary-org-1-canary
```

### 5. Compare against the SLO acceptance bar

Open both `_stats.csv` files. Compute:

| Check                                             | Pass criterion                                         |
|---------------------------------------------------|--------------------------------------------------------|
| Canary p50 vs baseline p50                        | Canary p50 ≤ baseline p50 × 1.2                        |
| Canary p99 vs baseline p99                        | Canary p99 ≤ baseline p99 × 1.5                        |
| Canary error rate vs baseline error rate          | Canary error_rate ≤ baseline error_rate + 0.5%         |
| Sample 10 canary responses manually               | All match the format / quality the org expects         |
| Canary `runtime.native_dispatch.runs{status="error"}` increment | ≤ 0.5% of canary success counter                |

If **all five checks pass** → proceed to step 6 (soak).
If **any check fails** → revert per the rollback section below.

### 6. Soak for 1 hour

Leave the flag on, do **nothing**. Watch:

- The Phase 16 `/metrics` scrape — counter and duration aggregates
  shouldn't drift from the canary numbers in step 4.
- Application logs filtered to the org_id — look for 5xx, unhandled
  exceptions, unusual provider failover events.
- The on-call dashboard — no new pages.

After 1 hour clean, the canary is **soaked**. Repeat steps 2-6 with
the next org on the rollout list.

## Rollback

To remove an org from the canary:

```bash
# Restore the previous allowlist value
NATIVE_RUNTIME_ORG_ALLOWLIST='[]'  # or the prior list
```

Restart workers. Verify the routes still register globally if at
least one other org is in the list, OR are entirely unmounted if the
list is empty + `enable_native_runtime=False`.

The rollback is **fully reversible** — durable session events
recorded under the canary remain readable; nothing in the legacy path
expects them to be absent. Removing an org from the allowlist just
means new requests no longer go through `native_chat_dispatch`.

## Acceptance criteria for full cutover

The native runtime is ready for `enable_native_runtime=True` (global,
all orgs) when:

- [ ] At least 5 distinct orgs have soaked successfully.
- [ ] Cumulative canary p50 ≤ legacy p50 (no regression).
- [ ] Cumulative canary p99 ≤ legacy p99 × 1.2.
- [ ] No P1 or P2 page from the [`runbooks/`](runbooks/) set in the
      last 14 days that traced to native_dispatch as root cause.
- [ ] At least one nightly replay job has flagged zero regressions
      against canary recordings.

## Review log

| Date       | Reviewer | Change                                              |
|------------|----------|-----------------------------------------------------|
| 2026-05-04 | runtime  | v1 — initial onboarding doc, Phase 28 of #207       |
