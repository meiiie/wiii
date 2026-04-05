# Runtime Endpoint Readiness Report — 2026-03-23

## Scope

Audited and smoke-tested the runtime-critical endpoints that now carry the new provider selectability, strict pinning, and admin LLM runtime policy flow:

- `POST /api/v1/chat`
- `POST /api/v1/chat/stream/v3`
- `GET /api/v1/admin/llm-runtime`
- `GET /api/v1/llm/status`

This pass focused on real endpoint contract integrity, fail-fast behavior for pinned providers, and merge/deploy readiness for the new runtime policy stack.

## What Was Verified

### 1. Endpoint contract audit

- `/api/v1/llm/status`
  - Returns additive selectability fields:
    - `state`
    - `reason_code`
    - `reason_label`
    - `selected_model`
    - `strict_pin`
    - `verified_at`
  - Hidden providers remain in the API payload with `state=hidden`, allowing the desktop to filter consistently.

- `/api/v1/admin/llm-runtime`
  - Returns runtime truth from admin/runtime policy serialization.
  - Verified against the actual app wiring, not just isolated helpers.

- `/api/v1/chat`
  - Explicit pinned provider now fails before full chat service execution when the provider is not selectable.
  - Returns stable handled payload:
    - `503`
    - `error_code=PROVIDER_UNAVAILABLE`
    - `provider`
    - `reason_code`

- `/api/v1/chat/stream/v3`
  - Explicit pinned provider now fails before `ChatService`/graph cold-start when the provider is not selectable.
  - Emits:
    - initial `status`
    - `error` with preserved `provider` and `reason_code`
    - terminal `done`

### 2. Regressions fixed during this pass

- Preserved `provider` and `reason_code` in SSE `error` serialization.
  - File: [chat_stream_presenter.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/chat_stream_presenter.py)

- Moved explicit-provider selectability checks earlier so disabled pinned providers fail before heavy service startup.
  - Files:
    - [chat_completion_endpoint_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/chat_completion_endpoint_support.py)
    - [chat_stream_coordinator.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_stream_coordinator.py)

- Preserved runtime provider/model metadata in sync multi-agent responses so `/chat` success metadata no longer drifts back to default Gemini when the request is pinned to another provider.
  - Files:
    - [graph.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
    - [chat_orchestrator.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_orchestrator.py)

- Added endpoint-level smoke coverage and regression tests for the fail-fast and metadata paths.
  - Files:
    - [test_runtime_endpoint_smoke.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py)
    - [test_chat_completion_endpoint_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_chat_completion_endpoint_support.py)
    - [test_chat_stream_presenter.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_chat_stream_presenter.py)
    - [test_chat_request_flow.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_chat_request_flow.py)

## Verification Results

### Focused automated suites

- Backend focused suite:
  - `102 passed`
- Frontend focused suite:
  - `8 passed`
- TypeScript:
  - `npx tsc --noEmit` passed

Focused backend coverage included:

- failover
- agent config
- runtime audit
- selectability
- structured invoke
- admin runtime
- chat request flow
- sync endpoint support
- endpoint smoke
- stream presenter

### Real-app smoke results

Executed against the actual FastAPI app via ASGI transport.

#### `GET /api/v1/llm/status`

- Status: `200`
- Result:
  - `google` -> `disabled/busy`
  - `zhipu` -> `selectable`
  - `ollama` -> `disabled/host_down`
  - `openai`, `openrouter` -> `hidden`

#### `GET /api/v1/admin/llm-runtime`

- Status: `200`
- Result:
  - runtime config serialized correctly from the app wiring

#### `POST /api/v1/chat` with explicit pinned `provider=google`

- Status: `503`
- Time: about `2.8s` cold
- Result:
  - handled `PROVIDER_UNAVAILABLE`
  - payload preserved `provider=google`
  - payload preserved `reason_code=busy`

#### `POST /api/v1/chat/stream/v3` with explicit pinned `provider=google`

- Status: `200`
- Time: about `0.011s`
- Result:
  - emitted `status`
  - emitted `error` with `provider=google` and `reason_code=busy`
  - emitted `done`
  - no `ChatService` cold-start on this fail-fast path after the patch

#### `POST /api/v1/chat` with explicit pinned `provider=zhipu`

- Status: `200`
- Time: about `61s` on the observed cold run
- Result:
  - response metadata now correctly reports `model=glm-5`
  - request path stayed pinned to the explicit provider contractually

## Live runtime state at report time

Persisted runtime audit snapshot:

- `audit_persisted = true`
- `degraded_providers = ["google", "ollama"]`
- `audit_updated_at = 2026-03-22T21:25:35.931432+00:00`

Observed selectability snapshot:

- `google`
  - `state=disabled`
  - `reason_code=busy`
  - `selected_model=gemini-3.1-flash-lite-preview`
- `zhipu`
  - `state=selectable`
  - `selected_model=glm-5`
- `ollama`
  - `state=disabled`
  - `reason_code=host_down`
- `openai`
  - `state=hidden`
- `openrouter`
  - `state=hidden`

## Findings

### Ready / green

- Endpoint contracts for `chat`, `chat/stream/v3`, `admin/llm-runtime`, and `llm/status` are internally consistent after this pass.
- Strict pinning now behaves correctly on the negative path.
- SSE error payloads no longer lose provider-specific metadata.
- Desktop selector contract is aligned with backend selectability.
- Sync response metadata no longer misreports explicit `zhipu` requests as Gemini by default.

### Residual risks

1. Google is still operationally degraded in this environment.
   - Reason: quota / busy condition from live runtime audit.

2. Ollama is still operationally degraded in this environment.
   - Reason: host unreachable, not a code-path issue.

3. Zhipu is contractually selectable and reachable, but one real multi-agent happy-path still showed latency pressure.
   - In the observed live run, the direct phase hit the current `12s` timeout and recovered through fallback behavior.
   - This is not a routing-contract bug anymore, but it is still a production quality risk.
   - The evidence supports the earlier conclusion that the current primary timeout is too aggressive for some heavier prompts/providers.

4. Persisted runtime audit exists, but persisted runtime policy is not populated in this environment right now.
   - Current runtime still works off env/config defaults plus live admin/runtime services.
   - Not a blocker for merge, but worth being explicit during rollout.

## Merge / Deploy Verdict

### Merge

`YES`

Reason:

- The new runtime endpoint contracts are now materially safer and more internally consistent than before this pass.
- The critical regressions found during smoke were fixed and locked by tests.

### Deploy

`YES, WITH GUARDED ROLLOUT`

Recommended rollout stance:

- Safe for staging and limited production rollout of:
  - selectability-driven provider selector
  - strict pinned-provider rejection
  - admin runtime visibility
  - SSE error contract improvements

- Do not treat this exact environment as fully green for broad production traffic until:
  - Google quota pressure is resolved
  - Ollama host connectivity is fixed if local fallback is expected
  - Zhipu timeout behavior is tuned or monitored closely for heavier multi-agent prompts

## Recommended next actions before wide rollout

1. Restore or raise Google quota so the default provider is not user-visible as `busy`.
2. Make the primary timeout configurable and likely tier-aware/provider-aware instead of fixed `12s`.
3. Decide whether Ollama should be a real production fallback in this environment; if yes, fix host reachability.
4. Persist a formal runtime policy snapshot through admin if this environment is meant to be admin-managed rather than env-managed.
5. Add one scripted pre-deploy smoke command that hits:
   - `/api/v1/llm/status`
   - `/api/v1/admin/llm-runtime`
   - `/api/v1/chat` pinned unavailable provider
   - `/api/v1/chat/stream/v3` pinned unavailable provider
   - one pinned happy-path provider request

## Bottom line

The endpoint layer is now merge-ready.

The deployment path is good enough for guarded rollout, but the environment is not yet “all providers green”:

- Google is degraded
- Ollama is degraded
- Zhipu is usable, but timeout tuning still matters for heavier prompts

That means the code is substantially harder and cleaner than before, but operations still need one more pass before calling the runtime stack fully relaxed for broad production traffic.
