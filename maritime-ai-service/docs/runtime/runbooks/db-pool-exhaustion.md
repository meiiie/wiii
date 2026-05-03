# Runbook: Postgres Connection Pool Exhaustion

**Alert:** asyncpg pool exhausted ≥ 3 occurrences in 1 minute
**Severity:** P1 page
**SLO impact:** pool exhaustion blocks every chat turn that needs DB
access (most of them). Drives both 5xx surge and latency spike pages
simultaneously.

## Symptom shape

The asyncpg pool has a fixed upper bound (`async_pool_max_size`,
default 50). When all 50 connections are in use and a new request
needs one, asyncpg blocks until a connection frees. If the pool is
exhausted under sustained load, requests queue up and ultimately
timeout. Symptoms:

- 5xx surge page fires (chat turns time out).
- Latency spike page fires (everything queues).
- Application logs show `TimeoutError: connection acquire timeout`
  or `pool exhausted` messages.

## First 2 minutes (this is a P1)

1. **Confirm exhaustion** vs other DB issues:
   ```sql
   SELECT count(*) AS active, max_conn AS max_pool
   FROM pg_stat_activity
   CROSS JOIN (SELECT setting::int AS max_conn FROM pg_settings WHERE name='max_connections') t
   WHERE state IS NOT NULL;
   ```
   Pool exhausted = `active` ≥ `max_pool * 0.95`.
2. **Check for long-running queries:**
   ```sql
   SELECT pid, state, query_start, state_change,
          now() - query_start AS duration, query
   FROM pg_stat_activity
   WHERE state != 'idle' AND now() - query_start > interval '30 seconds'
   ORDER BY duration DESC LIMIT 10;
   ```
   A handful of slow queries holding connections is the most common
   cause.
3. **Check for transactions stuck `idle in transaction`:**
   ```sql
   SELECT pid, state, query_start, state_change,
          now() - state_change AS idle_for, query
   FROM pg_stat_activity
   WHERE state = 'idle in transaction'
   ORDER BY idle_for DESC LIMIT 10;
   ```
   `postgres_idle_in_transaction_timeout_ms` (default 60s) should
   catch these but a recent deploy may have regressed the setting.

## Decision tree

### Branch A — Slow queries holding connections

- **Identify the query** (top of the slow-query list).
- If it's a recently-deployed code path, the easiest fix is to roll
  back. The query plan can be debugged off the hot path.
- If it's an established query suddenly slow, check for stale
  statistics: `ANALYZE <table>` may unstick it. If not, missing index.

### Branch B — `idle in transaction` accumulation

- A code path is opening a transaction and not committing/rolling
  back. Look at the query in the `idle in transaction` row — it
  identifies the offending session.
- Kill the offenders to free connections immediately:
  ```sql
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle in transaction'
    AND now() - state_change > interval '5 minutes';
  ```
- Then find the code path. `git grep -n 'BEGIN'` + recent changes is
  the starting point.

### Branch C — Real load, pool too small

- If queries are healthy and the pool is just too small for current
  traffic, raise `async_pool_max_size` (e.g. 50 → 100). Postgres'
  `max_connections` (default 100) is the upper bound; check both.
- This is a temporary fix — root cause is usually a spike in chat
  traffic + insufficient capacity planning.

## Mitigation while debugging

- **Pause chat ingress** by returning 503 from a load balancer rule.
  Better than slow death by timeout.
- **Drain the canary** — remove orgs from `native_runtime_org_allowlist`
  so the native dispatch path stops adding event-log INSERTs.

## When the alert clears

- Pool utilization must drop below 50% for 10 consecutive minutes.
- Postmortem is mandatory if the alert fired more than twice in a
  week — that's a capacity / code-quality signal, not noise.

## Related runbooks

- `chat-5xx-surge.md` — usually fires alongside this one.
- `chat-latency-spike.md` — usually fires alongside this one.
