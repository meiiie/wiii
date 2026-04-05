# Wiii Chat Flow Audit + Engine/API Divergence

Date: 2026-03-29
Workspace: `E:\Sach\Sua\AI_v1`
Author: Codex (LEADER audit)

## Executive Summary

Backend runtime has reached a structurally much healthier state after the refactor campaign, but the current `thinking` problem still cannot be judged cleanly from UI/API behavior alone.

The most important truth right now is:

- `core engine path` and `live HTTP/API path` are not telling the same story
- the divergence is real and reproducible
- the main blocker is upstream runtime/provider truth, not yet the quality of the public thinking wording itself

The deepest confirmed cause found in this audit is:

- the running server restores a persisted LLM runtime policy from DB at startup
- that persisted policy contains a `google_api_key` value that is different from the container env `GOOGLE_API_KEY`
- direct core tests that run in a fresh Python process bypass startup restore and therefore use the env key
- live HTTP requests go through the already-started server process, which uses the DB-restored runtime state

This explains the current split:

- direct core invocation can route through Gemini and produce a substantive answer
- live `/api/v1/chat` and `/api/v1/chat/stream/v3` still fall back to `rule_based + direct fallback + generic thinking`

In other words:

- before fixing `thinking` quality, we must first restore a single authoritative backend truth
- otherwise every UI observation is polluted by runtime-provider drift

---

## Local Runtime Truth

Current local surfaces:

- frontend: `http://localhost:1420`
- backend: `http://localhost:8000`

Why `localhost:1420` matters:

- the desktop/browser login flow builds the Google login URL from `settings.server_url`
- the browser redirect uses `window.location.origin`
- so when the app is opened at `http://localhost:1420`, OAuth redirect origin also becomes `http://localhost:1420`

Relevant frontend files:

- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\auth\LoginScreen.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\lib\constants.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\api\client.ts`

Practical conclusion:

- for local auth and real browser flow, use `localhost:1420`
- do not use `127.0.0.1:1420` unless you intentionally want a different origin

---

## Current Chat Flow

### 1. Sync path: `/api/v1/chat`

Entry:

- `app/api/v1/chat.py`

High-level flow:

1. request enters `/api/v1/chat`
2. auth identity is canonicalized onto request payload
3. `process_chat_completion_request()` is called
4. `ChatService.process_message()` delegates to `ChatOrchestrator.process()`
5. orchestrator prepares turn
6. input/context is assembled
7. multi-agent execution input is built
8. `process_with_multi_agent(...)` is invoked
9. internal response is shaped back into API response

Important files:

- `app/api/v1/chat.py`
- `app/api/v1/chat_completion_endpoint_support.py`
- `app/services/chat_service.py`
- `app/services/chat_orchestrator.py`
- `app/services/chat_orchestrator_runtime.py`

### 2. Streaming path: `/api/v1/chat/stream/v3`

Entry:

- `app/api/v1/chat_stream.py`

High-level flow:

1. request enters `/api/v1/chat/stream/v3`
2. auth identity is canonicalized onto request payload
3. `generate_stream_v3_events()` emits initial status
4. same orchestrator `prepare_turn(...)` is used
5. execution input is built with streaming fields
6. `process_with_multi_agent_streaming(...)` streams graph events
7. SSE transport serializes events to UI
8. orchestrator finalizes the response turn

Important files:

- `app/api/v1/chat_stream.py`
- `app/services/chat_stream_coordinator.py`
- `app/engine/multi_agent/graph_streaming.py`

### 3. Shared preparation path

The two routes are supposed to share the same business truth:

- auth canonicalization
- session/thread normalization
- context assembly
- graph execution
- persistence/finalization

This is why the current divergence is not “just frontend”.

---

## Current Context Assembly Truth

The current request preparation path still matches the earlier audit:

- session + thread normalization
- pronoun style
- conversation history
- semantic memory
- LMS/page/host context
- org/domain context
- prompt/persona loading
- multi-agent execution input

Key files:

- `app/services/input_processor.py`
- `app/services/chat_orchestrator_runtime.py`
- `app/services/chat_stream_coordinator.py`
- `app/prompts/prompt_loader.py`

This means the current `thinking` problem is not coming from “missing context assembly”. It is happening later, around runtime/provider truth, routing, and public-thinking production.

---

## Confirmed Engine vs API Divergence

### A. Direct core invocation works

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\direct-core-pendulum-2026-03-29.json`

Prompt:

- `Phân tích về toán học con lắc đơn`

Observed:

- substantive answer
- `provider = google`
- `model = gemini-3.1-flash-lite-preview`
- `routing_metadata.method = structured`
- `routing_metadata.intent = learning`

This proves the core engine is capable of taking this prompt down the expected route.

### B. Live `/api/v1/chat` falls back

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-chat-2026-03-29-fixed.json`

Observed:

- HTTP `200`
- fallback apology response
- `routing_metadata.method = rule_based`
- `routing_metadata.intent = unknown`
- `reasoning_trace.direct_response.result = Fallback (LLM generation error)`
- `thinking_content` collapses to short generic fallback

### C. Live `/api/v1/chat/stream/v3` also falls back

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-stream-pendulum-2026-03-29-fixed.json`

Observed:

- `thinking_start.summary` already generic
- `thinking_delta` repeats the same fallback content
- answer remains fallback apology
- metadata again shows `rule_based + unknown`

### D. Server logs explain the degraded HTTP path

Observed from live container logs during HTTP path:

- `Native structured invoke failed; falling back to JSON path`
- `LLM routing failed`
- Google error equivalent to `API key not valid`
- direct node then fails generation
- route falls back to `rule_based`

This is not a mere UI rendering issue. The server really is taking a different upstream route.

---

## Deepest Confirmed Root Cause

### Startup order matters

In server startup:

1. persisted LLM runtime policy is restored from DB
2. then LLM pool is initialized
3. then agent registry is initialized

Relevant file:

- `app/main_startup_runtime.py`

This means the live server process does not simply use `.env` as-is. It uses:

- env defaults
- then persisted DB runtime policy overrides

### DB runtime policy overrides secrets too

Relevant file:

- `app/services/llm_runtime_policy_service.py`

Important behavior:

- `apply_persisted_llm_runtime_policy()` loads DB snapshot
- `apply_llm_runtime_policy_snapshot()` then writes fields directly onto live `settings`
- this includes `google_api_key`

### Confirmed mismatch

Confirmed in-container comparison:

- env `GOOGLE_API_KEY`: present
- DB persisted `google_api_key`: present
- equality: `False`
- both same length
- hashes differ

Meaning:

- the server startup restore is very likely replacing the good env key with a different persisted key

This is the strongest current explanation for the divergence:

- fresh direct core process uses env key and works
- long-running HTTP server restores stale/wrong DB key and fails at Google

### Why direct core bypasses the problem

The direct test used:

- `docker exec -i wiii-app python - ... process_with_multi_agent(...)`

That fresh Python process does not run the full FastAPI app startup lifecycle. So it does not inherit the server’s restored runtime state in the same way.

That is why both of these can be true at once:

- core invocation succeeds on Gemini
- live HTTP server still fails on Gemini

---

## Why This Blocks Thinking Work

Right now, the visible `thinking` problem has two stacked layers:

### Layer 1. Upstream runtime/provider truth is unstable

When Google routing/generation fails upstream:

- supervisor routing degrades
- direct lane degrades
- public thinking collapses into generic fallback lines

This means many bad `thinking` traces currently seen in UI are not pure “thinking design” failures. Some of them are symptoms of upstream provider failure.

### Layer 2. Public thinking authority is still split

Even once provider truth is fixed, the earlier audit remains valid:

- narrator
- node-native reasoning
- tool reflections
- stream events
- final metadata

are still multiple producers of public reasoning.

So the order of repair matters:

1. restore one backend runtime truth
2. then unify public thinking authority
3. then improve wording/quality

If we skip step 1, we will keep chasing false signals.

---

## Current Backend Truth

The backend truth today is:

- structurally much healthier after refactor
- `god files = 0`
- `cycles = 0`
- coupling now acceptable
- but runtime truth is still split between:
  - fresh engine process
  - long-running HTTP server process

This is a better position than before refactor, because now the main divergence is narrow and diagnosable.

---

## Fix Map Before Real Thinking Work

### Priority 0: restore one LLM runtime truth

Investigate and fix the secret precedence rule:

- env secret should likely win over DB-persisted secret
- or DB should not persist API keys at all
- or startup should explicitly refuse persisted secret override when env secret exists

Practical targets:

- `app/services/llm_runtime_policy_service.py`
- `app/main_startup_runtime.py`
- any admin runtime policy endpoints that persist provider secrets

### Priority 1: ensure long-running server can rebuild runtime state cleanly

After runtime policy changes, the live server should be able to reset and rebuild:

- `LLMPool`
- `AgentConfigRegistry`
- any cached provider/model instances

Relevant components:

- `app/engine/llm_pool.py`
- `app/engine/multi_agent/agent_config.py`
- `app/services/chat_service.py`

### Priority 2: re-run engine vs HTTP parity tests

After fixing runtime truth, re-test:

- direct core invocation
- `/api/v1/chat`
- `/api/v1/chat/stream/v3`

with the same prompt set:

- `Buồn quá`
- `Bạn là ai?`
- `Tên gì?`
- `Phân tích về toán học con lắc đơn`
- one visual/tool-heavy prompt

### Priority 3: only then attack thinking architecture itself

Once backend truth is unified:

- choose one producer/authority for public thinking
- keep metadata/internal reasoning separate from visible rail
- remove duplicate narrator/summary/delta overlap

This remains the real future `thinking` fix target.

---

## Concrete Working Diagnosis

Today the shortest honest diagnosis is:

> Wiii’s bad thinking on local UI is currently a mixture of two different failures:
> 
> 1. live HTTP server runtime is using a different Google key/runtime state than fresh core execution
> 2. public thinking still has multiple overlapping producers

So the next correct move is not “rewrite the thinking prompt again”.

The next correct move is:

- fix engine/API parity first
- then unify public-thinking authority

---

## Recommended Next Sprint Entry

Suggested next task framing:

1. Fix persisted LLM runtime secret precedence so server and direct core use the same Google key
2. Add a deterministic parity test: `process_with_multi_agent` vs `/api/v1/chat` vs `/api/v1/chat/stream/v3`
3. Only after parity passes, begin public-thinking refactor

---

## Supporting Artifacts

- `E:\Sach\Sua\AI_v1\.Codex\reports\WIII-CHAT-FLOW-AUDIT-2026-03-27.md`
- `E:\Sach\Sua\AI_v1\.Codex\reports\THINKING-RUNTIME-RECHECK-2026-03-29.md`
- `E:\Sach\Sua\AI_v1\.Codex\reports\direct-core-pendulum-2026-03-29.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-chat-2026-03-29-fixed.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\runtime-smoke-stream-pendulum-2026-03-29-fixed.json`
