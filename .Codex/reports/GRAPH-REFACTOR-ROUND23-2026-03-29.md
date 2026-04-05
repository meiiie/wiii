# Graph Refactor Round 23 — 2026-03-29

## Summary

This round continued the architecture-first cleanup without touching Wiii's `thinking` behavior directly.
The main focus was to slim two remaining high-traffic shells and remove one deep package-import coupling point:

- `semantic_memory_repository.py` -> converted into a true facade + runtime mixin split
- `living_agent.py` -> reduced to a thin FastAPI router shell with dedicated models/runtime helpers
- `app/api/v1/__init__.py` -> converted to a lazy router builder so importing one v1 submodule no longer eagerly imports every v1 route

This was a structural round, not a product-behavior round.

## Files Added

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\repositories\semantic_memory_repository_runtime.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\living_agent_models.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\living_agent_runtime.py`

## Files Modified

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\repositories\semantic_memory_repository.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\living_agent.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\__init__.py`

## 1. Semantic Memory Repository Refactor

### Before

`semantic_memory_repository.py` still contained:

- repository bootstrap/session ownership
- basic CRUD
- maintenance operations
- running-summary persistence

This was inconsistent with the rest of the semantic-memory package, which already used extracted mixins such as:

- `FactRepositoryMixin`
- `InsightRepositoryMixin`
- `VectorMemoryRepositoryMixin`

### After

Added:

- `semantic_memory_repository_runtime.py`

Moved into the new runtime mixin:

- `save_memory()`
- `get_by_id()`
- `delete_by_session()`
- `count_user_memories()`
- `is_available()`
- `update_last_accessed()`
- `get_memories_by_type()`
- `delete_memories_by_keyword()`
- `delete_all_user_memories()`
- `delete_oldest_insights()`
- `delete_memory()`
- `upsert_running_summary()`
- `get_running_summary()`
- `delete_running_summary()`

The shell file now keeps only:

- repository identity/constants
- shared-engine bootstrap
- embedding formatting
- factory function

### Result

Line count:

- `semantic_memory_repository.py`: `874 -> 81`
- `semantic_memory_repository_runtime.py`: `639`

This brings the file back in line with the repo's existing facade+mixin pattern instead of leaving one last monolith in place.

## 2. Living Agent API Refactor

### Before

`living_agent.py` mixed together:

- Pydantic request/response models
- feature-gate checks
- serializer/mapping logic
- endpoint runtime logic
- FastAPI route declarations

### After

Added:

- `living_agent_models.py`
- `living_agent_runtime.py`

`living_agent_models.py` now owns all request/response schemas:

- `EmotionalStateResponse`
- `JournalEntryResponse`
- `SkillResponse`
- `HeartbeatInfoResponse`
- `LivingAgentStatusResponse`
- `HeartbeatTriggerResponse`
- `BrowsingLogResponse`
- `PendingActionResponse`
- `ResolveActionRequest`
- `HeartbeatAuditResponse`
- `GoalResponse`
- `CreateGoalRequest`
- `UpdateGoalProgressRequest`
- `ReflectionResponse`
- `RoutineResponse`
- `AutonomyStatusResponse`

`living_agent_runtime.py` now owns route runtime/serialization helpers:

- `check_living_agent_enabled()`
- status/emotion/journal/skills/heartbeat builders
- goal/reflection/routine/autonomy handlers

`living_agent.py` is now a thin router shell:

- imports/re-exports the models
- keeps endpoint decorators and signatures
- delegates behavior into runtime/support modules
- keeps `_check_enabled()` as a backward-compatible alias for tests/importers

### Result

Line count:

- `living_agent.py`: `837 -> 341`
- `living_agent_models.py`: `187`
- `living_agent_runtime.py`: `417`

This makes the API surface much easier to extend later without turning the router back into a serialization/logic dump.

## 3. Lazy v1 Router Package

### Problem

`app/api/v1/__init__.py` eagerly imported nearly every v1 router at package import time.

That meant:

- importing one small submodule like `app.api.v1.living_agent`
- implicitly loaded many unrelated routers
- which pulled in unrelated dependencies
- which made import behavior fragile and increased coupling

This was also the reason the living-agent integration tests were previously getting blocked by unrelated router imports.

### Change

Replaced eager package initialization with a lazy router builder:

- `router` is now built only when `app.api.v1.router` is actually accessed
- importing `app.api.v1.living_agent` no longer eagerly builds the full v1 router tree

Implementation detail:

- `__getattr__("router")` now lazily builds and caches the v1 `APIRouter`
- core router registration is centralized in `_build_router()`
- optional router registration remains feature-gated

### Result

Line count:

- `app/api/v1/__init__.py`: `124 -> 139`

The file got slightly longer, but the architecture is much cleaner:

- lower import-side effects
- lower package coupling
- cleaner separation between "package import" and "assemble API router"

This is one of the most meaningful architectural fixes in this round even though it was not a line-count win.

## Validation

### Compile

Passed:

```powershell
python -m py_compile app/repositories/semantic_memory_repository.py `
  app/repositories/semantic_memory_repository_runtime.py `
  app/api/v1/living_agent.py `
  app/api/v1/living_agent_models.py `
  app/api/v1/living_agent_runtime.py `
  app/api/v1/__init__.py
```

### Tests

Passed:

```powershell
pytest tests/unit/test_sprint122_memory_foundation.py -k "F1 or F2" -q -p no:capture --tb=short
```

Result:

- `5 passed, 11 deselected`

Passed:

```powershell
pytest tests/unit/test_living_agent_integration.py -q -p no:capture --tb=short
```

Result:

- `28 passed`

Passed:

```powershell
pytest tests/unit/test_auth_ownership.py -q -p no:capture --tb=short
```

Result:

- `15 passed`

Passed:

```powershell
pytest tests/unit/test_sprint175_web_deployment.py -q -p no:capture --tb=short
```

Result:

- `52 passed`

### Notes

One unrelated existing assertion remains in the full `test_sprint122_memory_foundation.py` file:

- `TestF4SingleFactInjectionPath::test_core_memory_section_empty_in_tutor_node`

That failure is tied to current `tutor_node.py` source shape and was not introduced by this round.

## Sentrux

Command:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate .
```

Workdir:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app`

Result:

- `Quality: 3581 -> 4421`
- `Coupling: 0.36 -> 0.30`
- `Cycles: 8 -> 8`
- `God files: 9 -> 3`
- `Distance from Main Sequence: 0.31`
- `No degradation detected`

## Current Hotspots After Round 23

Top large files now include:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\config\_settings.py` — `1143`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\repositories\fact_repository.py` — `843`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\subagents\search\workers.py` — `840`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py` — `836`

## Recommended Next Cuts

Most promising next seams, in order:

1. `subagents/search/workers.py`
2. `tutor_node.py`
3. `_settings.py` (later, higher risk)

Reasoning:

- `workers.py` is free-function heavy and still structurally ripe
- `tutor_node.py` is large but more behavior-sensitive
- `_settings.py` is a meaningful cleanup target, but riskier because it sits on global configuration behavior
