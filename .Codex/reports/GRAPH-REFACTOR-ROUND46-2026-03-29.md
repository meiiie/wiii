# Graph Refactor Round 46 - 2026-03-29

## Goal

Push the backend past the last structural blocker reported by Sentrux:

- reduce `Cycles: 1`
- keep `God files: 0`
- avoid regressions while lowering architectural coupling pressure around boundary modules

## What Changed

### 1. Split `main_runtime_support` into explicit startup/shutdown/contracts layers

Created:

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/main_runtime_contracts.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/main_startup_runtime.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/main_shutdown_runtime.py`

Converted:

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/main_runtime_support.py`

Result:

- `main_runtime_support.py` is now a compatibility facade (`92` lines)
- startup/shutdown responsibilities are separated
- bootstrap imports now load dependencies lazily at the application boundary

Line counts:

- `main_runtime_support.py`: `92`
- `main_startup_runtime.py`: `498`
- `main_shutdown_runtime.py`: `201`
- `main_runtime_contracts.py`: `19`

### 2. Turned `app.engine.tools` into a true lazy package boundary

Updated:

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/__init__.py`

Changes:

- replaced eager top-level imports with lazy attribute resolution
- preserved legacy registry side effects for core tools via dynamic module priming
- converted extended tool wiring to dynamic module loading
- kept public import paths stable for existing code and tests

Result:

- static edges from `app.engine.tools.__init__` dropped to the registry boundary only in custom AST scan
- package still supports:
  - `from app.engine.tools import init_all_tools`
  - `from app.engine.tools import tool_think`
  - `from app.engine.tools import product_search_tools as pst`

### 3. Restored graph compatibility seam for tracer tests

Updated:

- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py`

Change:

- re-exported `_TRACERS` from `graph_trace_store` so legacy tests and patch paths continue to work

## Verification

### Compile

- `python -m py_compile` passed for:
  - `app/main_runtime_contracts.py`
  - `app/main_startup_runtime.py`
  - `app/main_shutdown_runtime.py`
  - `app/main_runtime_support.py`
  - `app/engine/tools/__init__.py`
  - `app/engine/multi_agent/graph.py`

### Tests

Passed:

- `tests/unit/test_runtime_endpoint_smoke.py`
- `tests/unit/test_sprint175_web_deployment.py`
- `tests/unit/test_alembic_startup.py`
- `tests/unit/test_browser_sandbox_service.py`
- `tests/unit/test_sprint26_tool_access.py`
- `tests/unit/test_sprint124_per_user_blocks.py`
- `tests/unit/test_sprint148_thinking_chain.py`
- `tests/unit/test_sprint153_hardening.py`

Key batch results:

- startup/web batch: `68 passed`
- tools/compat batch: `125 passed`

## Structural Outcome

### Sentrux Gate

Latest:

- `Quality: 6808`
- `Coupling: 0.28`
- `Cycles: 0`
- `God files: 0`
- `Distance from Main Sequence: 0.31`
- verdict: `No degradation detected`

Compared to the original baseline:

- `Quality: 3581 -> 6808`
- `Coupling: 0.36 -> 0.28`
- `Cycles: 8 -> 0`
- `God files: 9 -> 0`

### Interpretation

This round fully removed the last remaining Sentrux cycle without reopening god files or breaking compatibility paths. Coupling did not move below `0.28` in this round, but the remaining pressure is now concentrated in a few legitimate hubs rather than broad accidental cycles.

## Remaining Hotspots

Highest remaining hubs from custom import-degree scan:

- `app.engine.llm_pool`
- `app.engine.multi_agent.graph`
- `app.services.output_processor`

Recommended next refactor targets if we want to push coupling below `0.28`:

1. `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py`
2. `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_runtime_bindings.py`
3. `E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/output_processor.py`

## Verdict

Round 46 is accepted.

The backend is now in a materially better architectural state for future thinking-work:

- no god files
- no Sentrux cycles
- compatibility kept intact
- startup/tool boundaries are significantly cleaner
