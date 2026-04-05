# Failover Taxonomy And Perf - 2026-04-02

## Scope
- Add stable failover reason taxonomy to runtime metadata, stream/sync response metadata, and admin runtime surfaces.
- Verify the new contract with focused tests.
- Measure a synthetic failover smoke to decide whether Wiii should switch toward a `fallbackModel`-style approach.

## Implemented

### Backend runtime + metadata
- Added structured failover classification in [llm_failover_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_failover_runtime.py)
  - `rate_limit`
  - `auth_error`
  - `provider_unavailable`
  - `host_down`
  - `server_error`
  - `timeout`
- Added normalized event recording and summary resolution in [llm_runtime_metadata.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_runtime_metadata.py)
- Added failover event trail to graph state in [state.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/state.py) and [graph_support.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_support.py)
- Direct/code-studio failover now records structured events into state in [direct_execution.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py)
- Process result payload now carries failover summary in [graph_process.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_process.py)

### Stream/sync contracts
- Sync chat response metadata now exposes `failover` in [schemas.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/models/schemas.py) and [chat_response_presenter.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_response_presenter.py)
- Stream metadata events now expose `failover` in [chat_stream_coordinator.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_stream_coordinator.py) and [graph_stream_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_runtime.py)

### Admin runtime surfaces
- Provider runtime status now exposes selectability reasons in:
  - [admin_schemas.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin_schemas.py)
  - [admin_llm_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin_llm_runtime.py)
  - [admin.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/admin.py)

### Public/runtime wrappers
- Added `on_failover` pass-through and completed runtime helper wiring in:
  - [llm_pool.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py)
  - [llm_pool_public.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool_public.py)
  - [structured_invoke_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/structured_invoke_service.py)

## Tests
Focused suite run in repo venv:

```text
60 passed in 28.94s
```

Covered files:
- [test_llm_runtime_metadata.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_llm_runtime_metadata.py)
- [test_llm_failover.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_llm_failover.py)
- [test_admin_llm_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_admin_llm_runtime.py)
- [test_runtime_endpoint_smoke.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py)
- [test_chat_stream_coordinator.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_chat_stream_coordinator.py)
- [test_structured_invoke_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_structured_invoke_service.py)

## Synthetic Perf Smoke
Measured with patched in-memory LLM doubles inside the repo venv:

```json
[
  {
    "case": "auth_error",
    "elapsed_ms": 1.32,
    "result": "glm-ok",
    "event": {
      "from_provider": "google",
      "to_provider": "zhipu",
      "reason_code": "auth_error"
    }
  },
  {
    "case": "server_error",
    "elapsed_ms": 93.48,
    "result": "glm-ok",
    "event": {
      "from_provider": "google",
      "to_provider": "zhipu",
      "reason_code": "server_error"
    }
  },
  {
    "case": "timeout",
    "elapsed_ms": 18.76,
    "result": "glm-ok",
    "event": {
      "from_provider": "google",
      "to_provider": "zhipu",
      "reason_code": "timeout"
    }
  }
]
```

## Assessment
- Current multi-provider failover is already fast on immediate provider failures like invalid API key.
- Timeout behavior is bounded by the configured primary timeout, as expected.
- Based on this smoke, a Claude Code style `fallbackModel` path is **not yet the best next move**.
- Better next move, if needed later:
  - keep current multi-provider pool as primary authority
  - add optional same-provider `fallbackModel` only for specific provider/model-family cases
  - evaluate only after live provider credentials are healthy again

## Notes
- Live end-to-end provider smoke was not used as the primary benchmark here because Gemini runtime credentials were already known to be expired in the current environment.
- The timing smoke above is still useful because it isolates failover orchestration cost from external network/provider instability.
