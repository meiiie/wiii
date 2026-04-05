# Graph Refactor Pass — 2026-03-28

> Scope: continue safe `graph.py` decomposition while preserving routing, Code Studio, and visible-thinking behavior
> Working principle: cut ownership seams that help future thinking fixes, not just raw line count

---

## 1. What changed in this pass

Two new ownership modules were extracted from [graph.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py):

### A. Public thinking ownership

New file:

- [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py)

Moved responsibilities:

- visible-thinking text normalization
- internal-marker filtering
- delta chunk de-duplication
- fragment capture from `thinking_delta`
- final `thinking_content` assembly from interval fragments

Moved helpers:

- `_normalize_reasoning_text`
- `_PUBLIC_THINKING_INTERNAL_MARKERS`
- `_public_reasoning_delta_chunks`
- `_code_studio_delta_chunks`
- `_append_public_thinking_fragment`
- `_capture_public_thinking_event`
- `_resolve_public_thinking_content`

Why this matters:

- this isolates one of the most important future seams for Wiii thinking
- it reduces accidental ownership overlap between orchestration and public surface shaping
- it also reduces one `direct_execution -> graph.py` dependency

### B. Code Studio output surface

New file:

- [code_studio_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/code_studio_surface.py)

Moved responsibilities:

- artifact-name extraction from Code Studio tool results
- document-studio error detection
- synthesis observations for final delivery
- streamed summary-message construction for Code Studio delivery

Moved helpers:

- `_DOCUMENT_STUDIO_TOOLS`
- `_DOCUMENT_STUDIO_EXTENSIONS`
- `_extract_code_studio_artifact_names`
- `_is_document_studio_tool_error`
- `_build_code_studio_synthesis_observations`
- `_build_code_studio_stream_summary_messages`

Why this matters:

- Code Studio presentation/synthesis logic no longer lives in the same file as routing and node execution
- this makes later thinking/surface fixes easier because output-surface code is becoming more legible

---

## 2. Current structural effect

Current line counts:

- [graph.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py) → `4358`
- [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py) → `103`
- [code_studio_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/code_studio_surface.py) → `168`

This is a meaningful reduction from the recent `~4653` state and far below the original `8137` line god-file size.

Largest remaining functions in `graph.py` now:

1. `_execute_code_studio_tool_rounds` → `582`
2. `direct_response_node` → `372`
3. `code_studio_node` → `297`
4. `process_with_multi_agent` → `216`
5. `_execute_pendulum_code_studio_fast_path` → `140`
6. `build_multi_agent_graph` → `136`

Interpretation:

- the broad prompt/surface utilities are steadily moving out
- the remaining weight is now more honestly concentrated in orchestration and execution loops

That is the right direction.

---

## 3. Verification

### Compile

Passed:

- [graph.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [direct_execution.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py)
- [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py)
- [code_studio_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/code_studio_surface.py)

### Focused tests

Passed:

- [test_graph_routing.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_graph_routing.py) → `73 passed`
- [test_supervisor_agent.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_supervisor_agent.py) → `46 passed`
- combined focused run → `119 passed`

### Sentrux gate

Real Sentrux rerun via:

- [sentrux.exe](/E:/Sach/Sua/AI_v1/tools/sentrux.exe)

From:

- [app](/E:/Sach/Sua/AI_v1/maritime-ai-service/app)

Gate result:

```text
Quality:      3581 -> 3589
Coupling:     0.36 → 0.35
Cycles:       8 → 8
God files:    9 → 9
✓ No degradation detected
```

Meaning:

- structural quality improved modestly
- coupling improved slightly
- no regression
- but god-file count has not yet dropped under Sentrux thresholds

---

## 4. Why this helps future thinking work

The point of this pass is not only size reduction.

It improves the future thinking refactor in two specific ways:

1. **public visible thinking now has a more explicit owner**
- what becomes gray-rail text is less entangled with graph orchestration

2. **Code Studio delivery surface is becoming separable from execution**
- that makes it easier to reason later about:
  - what is real thinking
  - what is action/progress
  - what is delivery summary

This is directly aligned with the long-term goal of restoring Wiii's thinking quality.

---

## 5. Best next cuts

Recommended next extractions, in order:

1. `_build_simple_social_fast_path`
- small enough
- user-facing
- improves readability around direct lane behavior

2. `_execute_pendulum_code_studio_fast_path`
- isolated fast-path logic
- lower risk than touching the main Code Studio execution loop

3. public-thinking-adjacent helper cleanup
- small helper grouping around thinking/render ownership if needed

### Not recommended yet

Avoid splitting these immediately unless a very explicit seam is defined:

- `_execute_code_studio_tool_rounds`
- `direct_response_node`
- `code_studio_node`

These are still the highest-risk functions and touch the hottest behavior surfaces.

---

## 6. Verdict

This pass should be considered successful:

- real structural progress
- no regression in focused tests
- Sentrux gate still green
- future thinking work now has cleaner ownership seams to build on

