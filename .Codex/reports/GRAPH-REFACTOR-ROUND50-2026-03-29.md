# Graph Refactor Round 50 - 2026-03-29

## Summary

This round continued the post-god-file cleanup with two low-risk coupling cuts:

1. `app/api/v1/admin.py`
2. `app/services/vision_processor.py`

The goal was not to change behavior, but to reduce static dependency density in router/service shells while keeping existing patch seams and endpoint contracts stable.

## Structural Result

Latest Sentrux gate:

- Quality: `6813`
- Coupling: `0.28`
- Cycles: `0`
- God files: `0`
- Distance from Main Sequence: `0.30`
- Verdict: `No degradation detected`

Compared with the previous best checkpoint (`6808`), this round improved quality again while preserving zero cycles and zero god files.

## Changes

### 1. Admin Router Lazy Runtime Bindings

Created:

- `app/api/v1/admin_runtime_bindings.py`

Updated:

- `app/api/v1/admin.py`

What changed:

- Moved a large group of engine/service/provider lookups behind a lazy runtime binding module.
- Kept patchable names in `admin.py` itself, including:
  - `get_ingestion_service`
  - `get_user_graph_repository`
  - `get_domain_registry`
  - model catalog/provider/runtime helpers
- Replaced function-local imports of:
  - `get_persisted_llm_runtime_policy`
  - `get_shared_session_factory`
  with stable top-level names supplied by bindings.

Local impact:

- `admin.py` internal app-module imports reduced from `16 -> 9`.

Verification:

- `python -m py_compile app/api/v1/admin.py app/api/v1/admin_runtime_bindings.py`
- `python -m pytest tests/unit/test_admin_api.py tests/unit/test_admin_llm_runtime.py tests/unit/test_runtime_endpoint_smoke.py -q -p no:capture --tb=short`
- Result: `42 passed`

### 2. Vision Processor Runtime Bindings + Compatibility Preservation

Created:

- `app/services/vision_processor_runtime_bindings.py`

Updated:

- `app/services/vision_processor.py`

What changed:

- Added a dedicated runtime bindings module for:
  - `ChunkResult`
  - `PageResult`
  - `get_effective_org_id`
  - `_analyze_image_with_vision`
  - `_fetch_image_as_base64`
- Preserved compatibility for existing patch paths by resolving some helpers at call-time instead of binding the underlying function too early.
- Kept `settings` and `get_shared_session_factory` on the service module so current tests and operational monkeypatches remain stable.

Important note:

- An initial version broke the org-id fallback test because the patched function was captured too early.
- This was corrected by changing `get_effective_org_id` to a wrapper that resolves the underlying implementation at call time.

Verification:

- `python -m py_compile app/services/vision_processor.py app/services/vision_processor_runtime_bindings.py`
- `python -m pytest tests/unit/test_sprint53_vision_processor.py tests/unit/test_sprint189_rag_integrity.py -q -p no:capture --tb=short`
- Result: `55 passed`

## Why This Helped

These cuts improved structural quality without reopening the harder risk areas:

- no new cycles
- no compatibility regressions in the admin or vision test surfaces
- better shell/boundary discipline for two modules that previously imported many internal services directly

## Remaining Coupling Hotspots

Based on the latest internal import scan, the next high-value targets are:

1. `app/engine/multi_agent/supervisor.py`
2. `app/engine/multi_agent/agents/product_search_runtime.py`
3. `app/engine/multi_agent/graph_streaming.py`
4. `app/engine/multi_agent/graph.py`
5. `app/engine/llm_pool.py`

These are now the best candidates if the next goal is to push coupling lower than `0.28`.

## Recommendation

Do not reopen already-clean shells just to chase the metric mechanically.

The best next move is targeted coupling work on the remaining high-degree hubs, starting with:

1. `supervisor.py`
2. `graph_streaming.py`
3. `product_search_runtime.py`

That path is more likely to improve the global coupling score than further polishing already-thin router/service shells.
