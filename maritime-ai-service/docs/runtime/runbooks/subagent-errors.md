# Runbook: Subagent Error Rate Spike

**Alert:** Subagent error rate ≥ 5% over 15 minutes
**Severity:** P2 page
**SLO impact:** subagent error target is ≤ 1% — every percentage
point above 5% indicates a structural problem, not provider noise.

## Symptom shape

The Phase 13 façade tracks `runtime.subagent.runs` by status.
When the `error` bucket count divided by total exceeds 5% over a
15-minute window, this page fires. Subagent failures are usually
*structural* (the child can't do the task) rather than transient
(a single provider blip), which is why the threshold is higher and
the window longer than the chat 5xx page.

## Common root causes

| Pattern in `subagent_completed.error`              | Likely cause                              |
|----------------------------------------------------|-------------------------------------------|
| `RuntimeError: SubagentRunner has no runner_callable bound` | Singleton wasn't auto-wired (Phase 15 bug)  |
| `TimeoutError: ...`                                | Provider cold start or network jitter     |
| `RuntimeError: provider 5xx ...`                   | Upstream provider degradation             |
| `RuntimeError: max_steps_exceeded`                 | Agentic loop hitting the cap (see latency runbook) |
| `KeyError: '...'`                                  | Schema regression — child agent expects a field that no longer exists |

## First 5 minutes

1. **Pull a sample of recent failures** from the durable log:
   ```sql
   SELECT payload->>'error' AS error, count(*)
   FROM session_events
   WHERE event_type = 'subagent_completed'
     AND payload->>'status' = 'error'
     AND created_at > now() - interval '15 minutes'
   GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
   ```
2. **Check the count distribution.** If one error class dominates
   (>70% of the spike), that's the root cause. If errors are
   distributed across many classes, the issue is upstream — check
   provider status next.
3. **Check whether the singleton is wired.** From a Python REPL
   on the host:
   ```python
   from app.engine.runtime.subagent_runner import get_subagent_runner
   r = get_subagent_runner()
   assert r._runner is not None, "ChatService bridge not wired"
   ```
   A `None` runner means Phase 15's auto-wire failed somehow — file
   a critical bug.

## Decision tree

### Branch A — Single error class dominates

- **Schema regression.** Recent deploy changed a model or response
  shape. `git log --since="6 hours ago" maritime-ai-service/app/engine/`
  is your starting point.
- **Bad prompt.** A new SubagentTask description triggers behavior
  that fails consistently. Check the recent `subagent_started` payloads
  for unusual descriptions.
- **Provider quirk.** The provider rejects a specific tool call shape
  (e.g. JSON schema mismatch). Look for `400` codes specifically.

### Branch B — Errors distributed across classes

- Likely upstream — provider degradation. Cross-reference with the
  provider status page. Jump to `provider-failover.md`.

### Branch C — `max_steps_exceeded` rising

- A change made the agentic loop run longer. Tighten
  `subagent_default_max_steps` and find the loop cause.
- Jump to `chat-latency-spike.md` Branch B.

## Mitigation while debugging

- **Disable subagent isolation** for the affected org by removing it
  from the canary list — the parent will fall back to the legacy
  ChatService path which doesn't use the SubagentRunner.
- This is reversible and trades depth/isolation for stability while
  the root cause is identified.

## When the alert clears

- Error rate must drop below 2% for 30 minutes before declaring
  resolved. Subagent issues tend to come in waves; resist the urge
  to declare victory after the first 10 minutes of calm.

## Related runbooks

- `chat-5xx-surge.md` — chat error spike, sometimes correlated.
- `chat-latency-spike.md` — Branch C endpoint.
- `provider-failover.md` — Branch B endpoint.
