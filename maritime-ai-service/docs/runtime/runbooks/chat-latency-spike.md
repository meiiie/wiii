# Runbook: Chat Latency Spike

**Alert:** `p99 latency` ≥ 8 s over 5 minutes on any chat surface
**Severity:** P2 page
**SLO impact:** p99 target is ≤ 5.0 s — sustained breach erodes user
trust faster than 5xx because users wait, blame the product, then
churn.

## Symptom shape

`runtime.native_dispatch.duration_ms` p99 (or the equivalent
client-side timing on `/api/v1/chat`) is rising. Users complain
"Wiii feels slow today" before the page actually trips. The 8s p99
threshold gives ~3-5 minutes of degradation lead time before
customers escalate.

## First 5 minutes

1. **Pull the latency breakdown** by surface from `/metrics`:
   - `edge.openai_chat_completions.duration_ms` (Phase 16 summary).
   - `edge.anthropic_messages.duration_ms`.
   - `runtime.native_dispatch.duration_ms` (per-status — error
     latency reads differently than success).
2. **Check provider response time.** The provider's own status page
   often shows latency degradation hours before customers do. Look
   for "elevated response times" headlines.
3. **Check the agentic loop.** If latency is spiking on the
   `runtime.subagent.duration_ms` summary, the children are taking
   too long — usually a rate limit, a tool that hangs, or a new
   prompt that triggers more steps than designed.

## Decision tree

### Branch A — Provider latency only

- Wiii's own duration histogram shows tight bounds, but the inner LLM
  call is slow. The runtime is healthy; the upstream is not.
- **Switch the canary** to a provider with healthier latency: if
  `enable_unified_providers=True`, `unified_provider_priority` can
  be reordered without a redeploy.
- **Set expectations:** post a `#wiii-incidents` note that p99 is
  elevated due to upstream. Most customers tolerate 1-2 minutes of
  warning more than a silent slowdown.

### Branch B — Subagent depth explosion

- A new prompt or feature flip is causing children to consume more
  steps than the bound. Check `runtime.subagent.runs{status="max_steps_exceeded"}`
  — if it's nonzero and rising, the agentic loop is hitting the cap.
- **Tighten the cap temporarily** by lowering `subagent_default_max_steps`
  from 10 → 6 via env var. Buys time while the team finds the
  prompt or tool that's looping.
- **Identify the culprit** by sampling subagent payloads from the
  durable session log: `SELECT payload FROM session_events WHERE
  event_type='subagent_completed' AND payload->>'status'='max_steps_exceeded'
  ORDER BY created_at DESC LIMIT 20`.

### Branch C — Wiii pipeline regression

- Provider is fine, subagents are fine, but `edge.*.duration_ms`
  shows the server-side time growing. Likely culprits:
  - **Recent deploy** added a synchronous DB call on the hot path.
  - **Cache miss spike** — semantic cache eviction or warm-up.
  - **Memory pressure** — process is GC-thrashing.
- Pull a CPU profile (py-spy or austin) on a hot worker. The function
  consuming the most wall-time is your suspect.

## When the alert clears

- p99 must drop below 5 s for 15 minutes before declaring resolved.
- If the spike was provider-driven, file a one-line postmortem
  noting which provider + duration. These accumulate into the
  quarterly provider review.

## Related runbooks

- `chat-5xx-surge.md` — sometimes a latency spike precedes 5xx as
  callers time out client-side.
- `subagent-errors.md` — Branch B endpoint.
- `provider-failover.md` — Branch A endpoint.
