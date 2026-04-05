# Graph Refactor Round 44

**Date:** 2026-03-29  
**Scope:** `supervisor_surface` responsibility split + `course_generation` thin-router extraction  
**Status:** PASS

## Summary

This round continued the shift from broad shell modules toward smaller runtime-ownership modules:

- `supervisor_surface.py` now only owns supervisor stream/render/finalize surface logic.
- Routing-hint detection lives in `supervisor_hint_runtime.py`.
- `course_generation.py` now behaves as a thinner FastAPI router shell.
- Endpoint bodies moved into `course_generation_endpoint_runtime.py`.

The goal of both cuts was to reduce mixed responsibility inside high-traffic modules without changing public import paths or test patch seams.

## Changes

### 1. Supervisor surface split finalized

Refined:

- [supervisor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py)
- [supervisor_surface.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor_surface.py)
- [supervisor_hint_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor_hint_runtime.py)

What changed:

- `supervisor.py` now imports routing-hint helpers from `supervisor_hint_runtime.py`.
- `supervisor_surface.py` was reduced to:
  - routing turn summarization
  - recent-turn formatting
  - visible reasoning cleanup/render
  - supervisor stream queue push/get
  - routing-reasoning finalization
- All routing-hint detection and fast-chatter heuristics were removed from `supervisor_surface.py`.

Line counts after split:

- `supervisor.py`: `569`
- `supervisor_surface.py`: `223`
- `supervisor_hint_runtime.py`: `472`

Why this matters:

- `supervisor_surface` is now genuinely a surface module, not half surface and half routing policy.
- Routing hint ownership is clearer and easier to test/change without touching render code.

### 2. Course generation router thinned

Created:

- [course_generation_endpoint_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation_endpoint_runtime.py)

Refined:

- [course_generation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py)

Endpoint bodies moved into runtime helpers:

- `list_generation_jobs_impl`
- `generate_outline_impl`
- `expand_chapters_impl`
- `retry_failed_chapter_impl`
- `cancel_generation_job_impl`
- `resume_generation_job_impl`
- `get_generation_status_impl`

`course_generation.py` now keeps:

- router definitions
- compatibility wrappers
- background-phase runners
- helper wrappers already used by tests/patches

Line counts after split:

- `course_generation.py`: `535`
- `course_generation_endpoint_runtime.py`: `379`

Why this matters:

- FastAPI router modules become thinner and more uniform across the codebase.
- Endpoint behavior is easier to unit test independently from route declaration.
- Existing tests that import `course_generation.*` still work because wrappers were preserved.

## Verification

### Compile

- `python -m py_compile maritime-ai-service/app/engine/multi_agent/supervisor.py maritime-ai-service/app/engine/multi_agent/supervisor_surface.py maritime-ai-service/app/engine/multi_agent/supervisor_hint_runtime.py`
- `python -m py_compile maritime-ai-service/app/api/v1/course_generation.py maritime-ai-service/app/api/v1/course_generation_endpoint_runtime.py`

### Tests

- `python -m pytest maritime-ai-service/tests/unit/test_supervisor_agent.py maritime-ai-service/tests/unit/test_graph_routing.py maritime-ai-service/tests/unit/test_sprint54_graph_streaming.py -q -p no:capture --tb=short`
  - `159 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_course_generation_flow.py -q -p no:capture --tb=short`
  - `21 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_runtime_endpoint_smoke.py maritime-ai-service/tests/unit/test_sprint175_web_deployment.py -q -p no:capture --tb=short`
  - `59 passed`

### Sentrux

- `Quality: 3581 -> 5944`
- `Coupling: 0.36 -> 0.28`
- `Cycles: 8 -> 1`
- `God files: 9 -> 0`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

## Architectural Impact

This round did not change the headline Sentrux metrics, but it improved module ownership in two useful ways:

1. `supervisor_surface` now matches its name and can evolve independently from routing heuristics.
2. `course_generation` follows the same thin-shell pattern already established in other API/service layers.

These are the kinds of refactors that reduce future thinking/surface work friction because orchestration files stop mixing policy, rendering, and transport concerns in one place.

## Next Suggested Cuts

Highest ROI next:

1. [engine/llm_pool.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py)
2. [engine/tools/visual_payload_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_payload_runtime.py)
3. [engine/semantic_memory/temporal_graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/temporal_graph.py)

Suggested priority:

- Continue on modules with heavy ownership density.
- Do not chase the last Sentrux `Cycles: 1` blindly until a concrete remaining heuristic source is identified.
