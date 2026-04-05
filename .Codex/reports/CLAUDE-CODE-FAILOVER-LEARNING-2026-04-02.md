# Claude Code Failover Learning - 2026-04-02

## Scope
- Review local `claude-code` source after Wiii failover hardening.
- Focus: retry, fallback, error classification, and what is worth borrowing for Wiii.

## Sources Read
- `E:/Sach/Sua/test/claude_lo/claude-code/src/QueryEngine.ts`
- `E:/Sach/Sua/test/claude_lo/claude-code/src/query.ts`
- `E:/Sach/Sua/test/claude_lo/claude-code/src/services/api/errors.ts`
- `E:/Sach/Sua/test/claude_lo/claude-code/src/bridge/bridgeMain.ts`
- `E:/Sach/Sua/test/claude_lo/claude-code/src/utils/teleport/api.ts`

## What Claude Code Actually Does

### 1. It does have fallback, but mostly as `fallbackModel`, not provider-pool failover
- In `src/QueryEngine.ts` and `src/query.ts`, there is a `fallbackModel` passed into the query loop.
- When a `FallbackTriggeredError` occurs, they:
  - switch `currentModel = fallbackModel`
  - clear the failed assistant/tool attempt state
  - strip model-bound thinking signatures before retry
  - retry the request with the fallback model
- This is **model fallback inside the same general provider/runtime flow**, not the same architecture as Wiii’s multi-provider pool.

### 2. Their retry policy is strict about fatal vs transient
- In `src/bridge/bridgeMain.ts`:
  - `401/403` are treated as fatal in bridge work loops
  - connection/server errors get exponential backoff and eventual give-up
- In `src/utils/teleport/api.ts`:
  - retries only happen on:
    - network/no-response errors
    - `5xx`
  - `4xx` are treated as non-transient

### 3. They classify API errors very explicitly
- In `src/services/api/errors.ts`, they separate:
  - rate limit / overload
  - auth failure
  - invalid model
  - prompt too long
  - media-size errors
  - connection errors
  - server errors
- `categorizeRetryableAPIError(...)` maps:
  - `529`, `429` -> `rate_limit`
  - `401/403` -> `authentication_failed`
  - `>=408` -> `server_error`

## What Wiii Should Learn From This

### 1. Error classification should be intentional, not accidental
Claude Code is strong here. They do not just “catch exception and hope”.

For Wiii, the valuable lesson is:
- keep distinguishing:
  - auth/provider-unavailable
  - rate-limit/quota
  - server/host-down
  - prompt/content/tool-protocol errors
- then decide lane behavior from that classification

This aligns with the failover patch we just made.

### 2. Retry budget and backoff should be explicit
Claude Code keeps retry loops bounded and typed:
- transient network/server -> retry with backoff
- fatal auth/client -> no useless retry

For Wiii, this means:
- provider fallback is good
- but we should still keep bounded retry/backoff rules per error class
- especially for sync endpoint hangs and dead-provider latency

### 3. They reset failed attempt state before retry/fallback
In `src/query.ts`, when fallback happens, Claude Code clears:
- assistant partials
- pending tool state
- model-bound signature artifacts

This is a very good lesson for Wiii’s stream-heavy lanes:
- if we ever retry/fail over after partial generation, we must ensure:
  - no duplicate answer tail
  - no orphan tool state
  - no cross-model thought artifacts leaking into the retry

## What Wiii Should NOT Copy Blindly

### 1. Their fallback is model-centric, not provider-centric
Claude Code’s world is much more Anthropic/CLI-shaped.

Wiii is different:
- Google
- Zhipu
- OpenRouter/OpenAI-compatible
- Ollama
- streaming desktop/web/LMS

So Wiii should **not** flatten its architecture into “just fallbackModel”.
Our provider-pool approach is still the right backbone.

### 2. Their fatal `401/403` rule is not directly portable
For Claude Code, `401/403` often means “same trust/auth stack is broken, stop retrying”.

For Wiii, a `401 invalid API key` from **Google** can still mean:
- Google is dead for this request
- but `zhipu/openrouter/ollama` may still be fine

So Wiii was right to harden cross-provider failover on auth/provider-down failures.

## Bottom Line

Claude Code confirms three things:

1. Wiii should keep its multi-provider pool architecture.
2. Wiii should keep strengthening explicit error classification and bounded retry policy.
3. Wiii should clear failed partial state carefully before retry/failover in stream-heavy lanes.

## Recommended Next Follow-Up For Wiii

If we want to borrow one more concrete idea next, it should be:
- add a clearer **retry/failover reason taxonomy** into runtime metadata/logging, e.g.
  - `rate_limit`
  - `auth_error`
  - `provider_unavailable`
  - `host_down`
  - `server_error`
  - `timeout`

That would make live diagnosis and parity debugging much easier.
