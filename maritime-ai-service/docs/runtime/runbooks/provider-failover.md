# Runbook: Provider Failover Storm

**Alert:** ≥ 5 provider failover events in 5 minutes
**Severity:** P3 ticket (no page — failover is the system working as
designed; the alert is a heads-up so the team can investigate the
upstream)
**SLO impact:** failovers are NOT a customer-visible failure if the
secondary provider holds. The ticket exists to catch upstream
provider degradation early so the team can pause the canary or
switch the priority order.

## Symptom shape

`enable_llm_failover=True` (the default) means LLMPool tries provider
A, falls back to B on a transient failure. A burst of failover
events is normal during a brief provider blip. ≥ 5 in 5 minutes
indicates either:

- The primary provider is genuinely degraded (the common case).
- The failover threshold is too sensitive (less common; LLMPool
  retries before declaring failover).
- A model-config mismatch (rare: requesting a model the primary
  no longer hosts → instant fallback every call).

## First 5 minutes

1. **Check provider status pages:**
   - OpenAI: https://status.openai.com
   - Google Gemini: https://status.cloud.google.com
   - NVIDIA NIM: https://status.nvidia.com
   - DeepSeek (NVIDIA-routed): same as NVIDIA
2. **Pull the recent failover log:** filter for `provider failover`
   in the application logs over the last 15 minutes. Look for the
   error class — `RateLimitError`, `TimeoutError`, `BadRequestError`
   each tell different stories.
3. **Check secondary provider health.** If failover is firing and
   the secondary is ALSO degrading (look for elevated `runtime.native_dispatch.runs{status="error"}`),
   you have correlated failure. Page on-call for **chat-5xx-surge.md**
   immediately.

## Decision tree

### Branch A — Primary provider has a public incident

- **Reorder the priority** if `enable_unified_providers=True`:
  ```bash
  # via env var, no redeploy needed
  export UNIFIED_PROVIDER_PRIORITY='["openai","google","ollama"]'
  ```
- Watch latency on the new primary; if it's holding, this is the
  right state until the original primary's incident clears.
- File the ticket noting the provider, duration, and which fallback
  was used. Quarterly provider review aggregates these.

### Branch B — No public incident, only Wiii sees the failures

- Likely a model-config drift. Did a recent deploy change
  `GOOGLE_MODEL` or similar to a model the provider no longer
  hosts? Check `git log --since="24 hours ago" maritime-ai-service/app/engine/llm_providers/`.
- Test the primary directly: `curl` the provider's `/models` endpoint
  with the configured API key. A 401/403 means key rotation hit.
- Test failover behavior is reciprocal: temporarily flip the primary
  to the secondary in the priority list. If it works, primary is
  the issue.

### Branch C — Both primary and secondary failing

- Treat as **correlated upstream incident** OR **internal Wiii bug**
  (a recent change broke the LLM call shape itself).
- Roll back any deploy from the last 2 hours.
- If rollback doesn't help, escalate to **chat-5xx-surge.md** path.

## When the alert clears

- Failover event count must drop below 1 per 5 minutes for 30
  minutes. Provider blips often come in waves.
- File a single ticket per incident, even if the alert fires multiple
  times during the same upstream issue. Ticket spam dilutes the
  quarterly provider review.

## What NOT to do

- **Do not disable failover** (`enable_llm_failover=False`) just to
  silence the alert. That removes the safety net; if the primary
  stays degraded, every chat turn breaks.
- **Do not page on-call for failover storms.** This is a P3 ticket
  by design — the system is doing its job. Page only if the
  *secondary* also degrades.

## Related runbooks

- `chat-5xx-surge.md` — Branch C escalation target.
- `chat-latency-spike.md` — failover often costs ~200ms per turn.
