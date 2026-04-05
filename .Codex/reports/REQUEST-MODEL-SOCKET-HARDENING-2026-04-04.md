# Request Model Socket Hardening

Date: 2026-04-04

## Summary

Mốc này khóa `per-request model` thành một socket thật từ desktop/API xuống runtime worker lanes, thay vì chỉ có `provider` pin còn `model` bị rơi hoặc bị thay bằng default runtime model.

## Fixed

### 1. Chat request schema now accepts `model`
- Backend `ChatRequest` đã có field `model`.
- Desktop stream request giờ gửi cả `provider` lẫn `model`, không còn chỉ gửi provider.

### 2. Request model now threads through sync + stream orchestration
- `chat_orchestrator` / `graph` / `graph_streaming` / bootstrap state đều mang `model`.
- Các path dùng `SimpleNamespace` cũ đã được giữ backward-compatible bằng `getattr(..., "model", None)`.

### 3. Worker lanes now honor the request model
- Confirmed user-facing lanes now pass `requested_model` xuống `AgentConfigRegistry.get_llm(...)`:
  - `direct`
  - `memory`
  - `tutor` request override
  - `code_studio`
  - `product_search` synthesis
  - `product_search` curation
  - subagent `aggregator`

### 4. Desktop request selection is now provider + model
- `useSSEStream` now consumes a full request selection, not only provider.
- `model-store` resolves selected model from runtime provider snapshot first, then falls back to local settings.

### 5. LLM usage batch logging no longer breaks on dataclass calls
- `LLMCall` dataclass records now normalize cleanly in batch usage logging.
- The old warning `'LLMCall' object has no attribute 'get'` no longer appears in the live logging path.

## Intentional Boundaries

The following call sites are still intentionally **not** driven by per-request `model`:

- `guardian`
- `supervisor`
- `reasoning_narrator`
- `tutor_runtime.initialize_tutor_llm()` base initializer

Reason:
- These are house-control / routing / fallback surfaces, not the primary user-facing worker answer path.
- Keeping them on stable house profiles avoids routing drift and preserves orchestration quality.

## Verification

### Backend
- `76 passed`
  - `tests/unit/test_agent_config.py`
  - `tests/unit/test_chat_request_flow.py`
  - `tests/unit/test_graph_stream_runtime.py`
  - `tests/unit/test_chat_stream_coordinator.py`
  - `tests/unit/test_direct_node_provider_errors.py`
- `54 passed`
  - `tests/unit/test_product_search_model_passthrough.py`
  - `tests/unit/test_agent_config.py`
  - `tests/unit/test_direct_node_provider_errors.py`
- `20 passed`
  - `tests/unit/test_chat_identity_projection.py`
  - `tests/unit/test_runtime_endpoint_smoke.py`
- aggregate regression batch: `165 passed`
  - token usage logging
  - request flow
  - stream runtime/coordinator
  - direct provider/model passthrough
  - product-search passthrough
  - identity projection
  - endpoint smoke

### Frontend
- `8 passed`
  - `src/__tests__/model-store.test.ts`
  - `src/__tests__/use-sse-stream-concurrency.test.ts`

## Current Truth

- `provider` is now a real socket.
- `model` is now also a real socket for the main user-facing lanes.
- Desktop no longer drops the selected model before sending the request.
- Product-search curation/synthesis no longer silently fall back to the default model when a request pins another model.
- `/api/v1/chat` and `/api/v1/chat/stream/v3` now have explicit smoke coverage proving `provider + model` survive auth canonicalization and reach the processing boundary.
- House-routing layers still intentionally use stable runtime profiles instead of per-request model overrides.

## Residual Notes

- A real OpenRouter sync smoke with `qwen/qwen3.6-plus:free` was attempted but timed out in-process, so the authoritative verification for this round is the deterministic test suite above rather than a live external completion.
- If needed next, a dedicated transient OpenRouter ASGI smoke can be added with a mocked provider boundary to verify endpoint-level passthrough without depending on upstream latency.
