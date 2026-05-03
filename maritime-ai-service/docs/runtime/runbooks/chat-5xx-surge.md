# Runbook: Chat 5xx Surge

**Alert:** `error rate >= 5xx` ≥ 2% over 5 minutes on any chat surface
**Severity:** P1 page
**SLO impact:** error rate target is ≤ 0.5% — every minute over budget
counts toward the 43.2-min/month error budget.

## Symptom shape

The chat 5xx counter (`runtime.native_dispatch.runs{status="error"}` for
edge endpoints + the `/api/v1/chat` aggregate) is climbing. Users see
either an opaque "internal error" page or a connection drop after
`X-Request-ID` is logged. The page fires when **2% of all chat
requests** hit ≥ 500 over the last 5 minutes.

## First 5 minutes

1. **Open the metrics dashboard** (`/metrics` scrape or your Grafana
   panel pointing at it). Look at the bucket label of the spiking
   counter:
   - `runtime.native_dispatch.runs{status="error"}` — Phase 19 path,
     edge endpoints (canary orgs).
   - Legacy `/api/v1/chat` does not yet expose this metric — fall back
     to the application logs filter `error="internal_error"`.
2. **Check provider health.** Most 5xx surges trace back to the LLM
   provider. Hit `https://status.openai.com`, `https://status.cloud.google.com`,
   the NVIDIA NIM dashboard. If a provider incident is open, jump to
   the **provider degradation** branch below.
3. **Check Postgres.** If the database is overloaded the runtime can't
   record events and chat errors. Run `SELECT count(*) FROM pg_stat_activity`
   and compare to `async_pool_max_size` (default 50). If saturated,
   jump to **db-pool-exhaustion.md**.

## Decision tree

### Branch A — Provider incident open

- **Verify failover is firing:** look for `provider failover` log lines
  in the last 5 minutes. If failover is NOT triggering, `enable_llm_failover`
  may be off or the failover chain is misconfigured.
- **Pause the canary:** if a canary org is the bulk of the failures,
  remove it from `native_runtime_org_allowlist` to stop new pain
  while the provider recovers.
- **Communicate:** post in `#wiii-incidents` with the provider's
  status link. Customers asking should be told "upstream provider
  degradation, fallback active."

### Branch B — Postgres saturated

→ Jump to `db-pool-exhaustion.md`.

### Branch C — Wiii internal error (provider + DB healthy)

- **Last deploy:** `git log origin/main --since="2 hours ago"`. Recent
  commit + spike = candidate root cause. If a deploy is suspect,
  rolling back is the right first move.
- **Look at the exception class** in the logs (sample 10 errors via
  `jq '.error_code' < log.json | sort | uniq -c | sort -rn`). If one
  exception class dominates, search the codebase for it — often a
  Pydantic validation regression or an unhandled provider response
  shape.
- **Repro locally** with the same `X-Request-ID` if possible. Customer
  privacy: redact `message` field before pasting into a ticket.

## When the alert clears

- Error rate must drop below 1% for 10 consecutive minutes before
  declaring resolved.
- File a postmortem if the incident consumed > 25% of the monthly
  error budget (≥ 11 minutes downtime equivalent).

## Related runbooks

- `chat-latency-spike.md` — different symptom, often same root cause.
- `db-pool-exhaustion.md` — Branch B endpoint.
- `provider-failover.md` — Branch A endpoint.
