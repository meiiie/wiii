# Graph Refactor Round 45

**Date:** 2026-03-29  
**Scope:** `visual_payload_runtime` facade split + `temporal_graph` runtime extraction  
**Status:** PASS WITH KNOWN DRIFT

## Summary

This round focused on two medium-risk but high-value ownership cleanups:

1. `visual_payload_runtime.py` was reduced to a compatibility facade.
2. `temporal_graph.py` was split so graph-manager model code is cleaner and integration/runtime logic is externalized.

Neither change altered the public module paths used by callers.

## Changes

### 1. Visual payload runtime split

Created:

- [visual_payload_normalization.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_payload_normalization.py)
- [visual_payload_grouping.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_payload_grouping.py)
- [visual_payload_parsing.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_payload_parsing.py)

Refined:

- [visual_payload_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_payload_runtime.py)

Ownership split:

- `visual_payload_normalization.py`
  - `build_artifact_handoff_impl`
  - `normalize_visual_payload_impl`
  - `coerce_visual_payload_data_impl`
- `visual_payload_grouping.py`
  - `apply_runtime_patch_defaults_impl`
  - `build_auto_grouped_payloads_impl`
  - `build_multi_figure_payloads_impl`
- `visual_payload_parsing.py`
  - `parse_visual_payloads_impl`
  - `parse_visual_payload_impl`

Result:

- [visual_payload_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_payload_runtime.py): `28` lines

Why this matters:

- Visual payload logic is no longer one mixed file containing normalization, patch defaults, grouping, and parsing.
- The facade pattern preserves compatibility for [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py) and any older imports.

### 2. Temporal graph runtime split

Created:

- [temporal_graph_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/temporal_graph_runtime.py)

Refined:

- [temporal_graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/temporal_graph.py)

Moved out of the main module:

- `build_context_text_impl`
- `to_dict_impl`
- `from_dict_impl`
- `extract_graph_from_facts_impl`

Kept in [temporal_graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/temporal_graph.py):

- enums
- dataclasses
- `TemporalGraphManager` public API
- singleton access

Result:

- [temporal_graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/temporal_graph.py): `564` lines
- [temporal_graph_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory/temporal_graph_runtime.py): `212` lines

Why this matters:

- The temporal graph module now separates graph-domain objects from graph integration/runtime orchestration.
- This makes future semantic-memory work less likely to re-mix stateful model code with extraction and formatting logic.

## Verification

### Compile

- `python -m py_compile maritime-ai-service/app/engine/tools/visual_payload_runtime.py maritime-ai-service/app/engine/tools/visual_payload_normalization.py maritime-ai-service/app/engine/tools/visual_payload_grouping.py maritime-ai-service/app/engine/tools/visual_payload_parsing.py`
- `python -m py_compile maritime-ai-service/app/engine/semantic_memory/temporal_graph.py maritime-ai-service/app/engine/semantic_memory/temporal_graph_runtime.py`

### Tests

- `python -m pytest maritime-ai-service/tests/unit/test_sprint200_visual_search.py maritime-ai-service/tests/unit/test_graph_visual_widget_injection.py -q -p no:capture --tb=short`
  - `55 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_sprint184_temporal_memory.py -q -p no:capture --tb=short`
  - `39 passed`

### Known drift re-confirmed, not introduced by this round

- `python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q -p no:capture --tb=short`
  - `78 passed`
  - `7 failed`

Those seven failures remain in the previously known visual-runtime policy drift cluster:

- renderer kind defaults (`template` vs `inline_html`)
- patch strategy defaults (`spec_merge` vs `replace_html`)
- auto-group figure count expectations (`1` vs `2/3`)

This round did **not** create a new failure pattern; it preserved the same cluster already observed before.

- `python -m pytest maritime-ai-service/tests/unit/test_sprint79_memory_hardening.py -q -p no:capture --tb=short`
  - still blocked by pre-existing local environment drift:
    - `sqlalchemy.orm.DeclarativeBase`
    - `app.repositories.chat_history_repository` import surface issues

These are outside the `temporal_graph` seam itself.

### Sentrux

- `Quality: 3581 -> 5944`
- `Coupling: 0.36 -> 0.28`
- `Cycles: 8 -> 1`
- `God files: 9 -> 0`
- `Distance from Main Sequence: 0.31`
- Verdict: `No degradation detected`

## Architectural Impact

This round continued the same pattern that has worked well for the codebase:

- keep compatibility shells where callers already depend on legacy module paths
- move dense implementation logic into narrower runtime modules
- verify with focused test batches instead of assuming equivalence

It did not materially change Sentrux headline metrics, but it improved ownership boundaries in two subsystems that were still denser than they needed to be.

## Next Suggested Cuts

Highest-ROI next seams:

1. [direct_prompts.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_prompts.py)
2. [llm_pool.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py)
3. [international_search_tool.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/international_search_tool.py)

Recommendation:

- Continue favoring thin compatibility shells plus runtime support modules.
- Do not try to “solve” the visual-runtime drift inside a pure refactor round; treat it as behavior work, not structure work.
