# Wiii Thinking Lifecycle V1

- Date: `2026-04-01`
- Scope: backend authority, sync/stream parity metadata, frontend finalize, golden eval/debug surfaces

## What Changed

### Backend authority
- Added [thinking_trajectory.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/thinking_trajectory.py) as the new visible-thinking authority.
- The authority tracks:
  - `turn_id`
  - `node`
  - `step_id`
  - `sequence_id`
  - lifecycle phases: `pre_tool`, `tool_continuation`, `post_tool`, `final_snapshot`
  - provenance: `live_native`, `tool_continuation`, `final_snapshot`, `aligned_cleanup`
  - status: `live`, `completed`

### Runtime integration
- Stream/runtime thought events now feed the lifecycle authority through:
  - [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py)
  - [graph_stream_node_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_node_runtime.py)
  - [graph_stream_dispatch_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_dispatch_runtime.py)
  - [memory_agent.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/memory_agent.py)
  - [tutor_node.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py)
  - [direct_node_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_node_runtime.py)
  - [code_studio_node_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/code_studio_node_runtime.py)

### Sync + stream parity
- Sync payload now emits `thinking_lifecycle` through:
  - [graph_process.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_process.py)
  - [chat_orchestrator_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_orchestrator_runtime.py)
  - [chat_response_presenter.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/chat_response_presenter.py)
- Stream final metadata now emits the same authority through [graph_stream_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_runtime.py).

### Contracts
- Added lifecycle metadata fields in:
  - [state.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/state.py)
  - [schemas.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/models/schemas.py)
  - [types.ts](/E:/Sach/Sua/AI_v1/wiii-desktop/src/api/types.ts)

### Frontend finalize
- [chat-store.ts](/E:/Sach/Sua/AI_v1/wiii-desktop/src/stores/chat-store.ts) now prefers `thinking_lifecycle.final_text` over thinner live text during finalize.

### Golden eval + HTML
- [probe_wiii_golden_eval.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/scripts/probe_wiii_golden_eval.py) now stores lifecycle metrics:
  - `live_length`
  - `final_length`
  - `provenance_mix`
  - `has_tool_continuation`
  - `rescued_by_final_snapshot`
- [analyze_wiii_sync_stream_parity.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/scripts/analyze_wiii_sync_stream_parity.py) now reads lifecycle metrics for parity analysis.
- [render_thinking_probe_html.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/scripts/render_thinking_probe_html.py) now shows a `Thinking Lifecycle` block.

## Validation

### Backend
- `pytest tests/unit/test_thinking_trajectory.py tests/unit/test_graph_process_thinking_lifecycle.py tests/unit/test_direct_execution_streaming.py -q`
  - `21 passed`
- `pytest tests/unit/test_tutor_agent_node.py -q`
  - `44 passed`
- `pytest tests/unit/test_memory_agent_node.py -q`
  - `15 passed`
- `pytest tests/unit/test_wiii_golden_eval_scripts.py tests/unit/test_sync_stream_parity_audit_scripts.py -q`
  - `12 passed`
- `python -m py_compile ...`
  - passed for all modified backend/runtime/script files

### Frontend
- `vitest --run src/__tests__/chat-store-thinking-lifecycle.test.ts`
  - `1 passed`

## Notes

- Existing desktop test [thinking-lifecycle.test.ts](/E:/Sach/Sua/AI_v1/wiii-desktop/src/__tests__/thinking-lifecycle.test.ts) still contains a legacy expectation that an empty thinking block should copy `thinking_start.summary` into visible body text. That behavior conflicts with the current `native-thinking-first` direction and was not changed in this step.
- The new lifecycle authority does not reintroduce `public_thinking_renderer` or authored prose fallback.
- The authority is designed so `sync` and `stream` can converge on the same finalized thought snapshot without forcing the UI to expose raw provenance tags.
