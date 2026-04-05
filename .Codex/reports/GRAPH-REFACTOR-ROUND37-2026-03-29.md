# Graph Refactor Round 37 — Course Generation Runtime Phase Split

Date: 2026-03-29

## Summary

This round split the heavy course-generation phase executors out of the runtime
shell so the public runtime module can focus on:
- job dispatch
- cancellation
- heartbeats
- recovery orchestration

The public function names in `course_generation_runtime.py` were preserved as
thin wrappers so the API router and tests do not need to change.

## Changes

### 1. Extract course generation phase executors

Added:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation_phase_runtime.py`

Moved into this module:
- `run_outline_phase_impl`
- `run_expand_phase_impl`
- `run_retry_chapter_impl`

These functions own the long-running course generation phase logic:
- conversion + outline preparation
- chapter expansion waves
- retry flow for failed chapters

### 2. Convert runtime module into job-shell + wrappers

Modified:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation_runtime.py`

Kept in this module:
- `dispatch_course_generation_task`
- `cancel_active_generation_tasks`
- `build_outline_status_message`
- `heartbeat_interval_seconds`
- `start_generation_heartbeat`
- `stop_generation_heartbeat`
- `generation_heartbeat_loop`
- `raise_if_generation_cancelled`
- `recover_course_generation_jobs_impl`

`course_generation_runtime.py` now re-exports the same phase function names via
thin wrapper functions that delegate into `course_generation_phase_runtime.py`.

## Line Count Impact

- `app/api/v1/course_generation_runtime.py`: `672 -> 313`
- `app/api/v1/course_generation_phase_runtime.py`: `491`

Net effect:
- the runtime shell now has a much clearer boundary
- phase execution logic has a dedicated home
- future refactors can target retry/expand/outline behavior independently

## Validation

### Compile

Passed:

```powershell
python -m py_compile `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation_runtime.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation_phase_runtime.py
```

### Focused tests

Passed:

```powershell
python -m pytest tests/unit/test_course_generation_flow.py -v -p no:capture --tb=short
```

Result:
- `21 passed`

Passed:

```powershell
python -m pytest tests/unit/test_sprint175_web_deployment.py tests/unit/test_runtime_endpoint_smoke.py -v -p no:capture --tb=short -k "course_generation or startup or chat_stream_v3_smoke_success_transport or admin_llm_runtime_smoke"
```

Result:
- `3 passed`
- `56 deselected`

## Sentrux

Command:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate E:\Sach\Sua\AI_v1\maritime-ai-service\app
```

Result:
- `Quality: 4501`
- `Coupling: 0.30`
- `Cycles: 7`
- `God files: 0`
- `No degradation detected`

## Why This Round Matters

Before this round, one module mixed:
- background task lifecycle
- heartbeat infrastructure
- recovery orchestration
- outline phase logic
- expand phase logic
- retry phase logic

That made course generation difficult to evolve because any change in one phase
reopened the whole runtime shell.

After this round:
- the runtime shell owns orchestration concerns
- phase execution owns business/process concerns
- API compatibility remains intact

## Recommended Next Cuts

High-ROI follow-ups:
1. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation.py`
2. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\semantic_memory\temporal_graph.py`
3. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\admin.py`

Rationale:
- these are no longer god files, but they still concentrate multiple concerns
- the course-generation surface is now ready for the next shell split
