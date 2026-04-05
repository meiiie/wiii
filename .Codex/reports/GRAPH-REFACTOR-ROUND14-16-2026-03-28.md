# Refactor Rounds 14-16 — API / Orchestrator / Sandbox Cleanup

> Date: 2026-03-28
> Scope: Continue clean-architecture refactor without touching thinking behavior
> Status: Completed and verified

## Summary

This batch focused on high-ROI god-file reduction outside the core thinking path:

1. `course_generation.py`
2. `admin.py`
3. `chat_orchestrator.py`
4. `opensandbox_executor.py`

The goal was to keep public/test surfaces stable while moving long runtime flows
into cohesive helper modules.

## Files Created

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation_runtime.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin_llm_runtime.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator_multi_agent.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\sandbox\opensandbox_artifacts.py`

## Files Reduced

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation.py`
  - `1355 -> 895` lines
  - background outline/expand/retry/recovery + heartbeat/task runtime extracted
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin.py`
  - `1458 -> 962` lines
  - LLM runtime status/catalog/update helpers extracted
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator.py`
  - `1012 -> 935` lines
  - multi-agent scope/context/input builders extracted
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\sandbox\opensandbox_executor.py`
  - `1022 -> 884` lines
  - artifact harvesting/inline-content helpers extracted

## Verification

### Course Generation

- `py_compile` passed for:
  - `app/api/v1/course_generation.py`
  - `app/api/v1/course_generation_runtime.py`
- Tests:
  - `25 passed`
  - command:
    - `.\.venv\Scripts\python.exe -m pytest tests\unit\test_course_generation_flow.py tests\unit\test_course_generation_source_preparation.py -q -p no:capture --tb=short`

### Admin LLM Runtime

- `py_compile` passed for:
  - `app/api/v1/admin.py`
  - `app/api/v1/admin_llm_runtime.py`
- Tests:
  - `125 passed`
  - command:
    - `.\.venv\Scripts\python.exe -m pytest tests\unit\test_admin_llm_runtime.py tests\unit\test_sprint178_admin_foundation.py tests\unit\test_sprint178_admin_flags_analytics.py tests\unit\test_sprint178_admin_compliance.py tests\unit\test_sprint194c_admin_context.py -q -p no:capture --tb=short`

### Chat Orchestrator

- `py_compile` passed for:
  - `app/services/chat_orchestrator.py`
  - `app/services/chat_orchestrator_multi_agent.py`
- Tests:
  - `4 passed, 11 deselected`
  - command:
    - `.\.venv\Scripts\python.exe -m pytest tests\unit\test_chat_request_flow.py -q -p no:capture --tb=short -k "resolve_request_scope or build_multi_agent_context or build_multi_agent_execution_input or build_minimal_multi_agent_execution_input"`

### OpenSandbox

- `py_compile` passed for:
  - `app/sandbox/opensandbox_executor.py`
  - `app/sandbox/opensandbox_artifacts.py`
- Tests:
  - `37 passed`
  - command:
    - `.\.venv\Scripts\python.exe -m pytest tests\unit\test_opensandbox_executor.py tests\unit\test_opensandbox_health.py tests\unit\test_sandbox_catalog.py tests\unit\test_sandbox_service.py tests\unit\test_browser_sandbox_service.py -q -p no:capture --tb=short`

## Sentrux

Latest gate after this batch:

- `Quality: 3581 -> 3593`
- `Coupling: 0.36 -> 0.33`
- `Cycles: 8 -> 8`
- `God files: 9 -> 5`
- verdict: `No degradation detected`

## Remaining Large Files

Current top files over 1000 lines:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\tools\visual_tools.py` — `2751`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\config\_settings.py` — `1689`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py` — `1131`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\living_agent\heartbeat.py` — `1070`

## Notes

- One unrelated local/runtime drift still exists in a broader `chat_request_flow` assertion:
  - expected model `glm-5`
  - actual metadata `glm-4.5-air`
  - this was not introduced by the orchestrator refactor and should be handled as a separate runtime-config issue.

## Suggested Next Cuts

1. `graph.py`
   - target: push remaining node/runtime ownership out of shell
2. `heartbeat.py`
   - target: split scheduler/actions/persistence from emotion/life policy
3. `visual_tools.py`
   - target: separate chart/html/simulation builders and publishing surface
4. `_settings.py`
   - target: extract provider/runtime/sandbox/admin config groups into submodels
