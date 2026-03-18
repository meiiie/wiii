# Wiii LLM-First Visual Phase 9

**Date:** 2026-03-18  
**Scope:** Backend visual cognition + prompt guidance  
**Status:** Local verified

## Mục tiêu

Chuyển article figures và chart runtime từ tư duy `template-first` sang `LLM-first generation, host-governed runtime` mà không phá contract frontend hiện có.

## Đã đổi

### 1. Visual intent mặc định
- `article_figure` và `chart_runtime` trong `resolve_visual_intent()` giờ trả:
  - `mode="inline_html"`
  - `preferred_tool="tool_generate_visual"`
  - `preferred_render_surface="svg"`
- `simulation` vẫn giữ:
  - `mode="app"`
  - `preferred_tool="tool_create_visual_code"`
  - `preferred_render_surface="canvas"`

### 2. Renderer resolution
- `tool_generate_visual` giờ ưu tiên `inline_html` cho `article_figure/chart_runtime` khi `enable_llm_code_gen_visuals=True`.
- Fallback structured builders vẫn được giữ như fail-safe nếu model chưa sinh `code_html`.
- `tool_create_visual_code` vẫn reject `article_figure/chart_runtime`.

### 3. Prompt/tool guidance
- Đã cập nhật:
  - `app/prompts/agents/assistant.yaml`
  - `app/prompts/agents/direct.yaml`
  - `app/prompts/agents/rag.yaml`
  - `app/prompts/agents/tutor.yaml`
  - `app/engine/multi_agent/agents/tutor_node.py`
  - `app/engine/multi_agent/graph.py`
- Policy mới:
  - `tool_generate_visual` = primary lane cho article/chart
  - `inline_html + SVG-first` = mặc định cho article/chart
  - `tool_create_visual_code` = simulation/app/widget/artifact

### 4. Regression coverage
- Added/updated tests for:
  - inline_html article/chart intent
  - chart runtime metadata prefers inline_html + svg
  - `tool_generate_visual` runtime context prefers `inline_html`
  - accented Vietnamese chart/simulation queries

## Files chính

- `maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py`
- `maritime-ai-service/app/engine/tools/visual_tools.py`
- `maritime-ai-service/app/engine/multi_agent/graph.py`
- `maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py`
- `maritime-ai-service/app/prompts/agents/assistant.yaml`
- `maritime-ai-service/app/prompts/agents/direct.yaml`
- `maritime-ai-service/app/prompts/agents/rag.yaml`
- `maritime-ai-service/app/prompts/agents/tutor.yaml`
- `maritime-ai-service/tests/unit/test_visual_intent_resolver.py`
- `maritime-ai-service/tests/unit/test_visual_tools.py`
- `maritime-ai-service/tests/unit/test_graph_routing.py`

## Verify

Passed:
- `python -m pytest maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q`
- `python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q`
- `python -m pytest maritime-ai-service/tests/unit/test_graph_routing.py -q`
- `python -m pytest maritime-ai-service/tests/unit/test_code_studio_streaming.py -q`

Smoke-checked:
- accented Vietnamese chart query -> `inline_html + chart_runtime + tool_generate_visual + svg`
- accented Vietnamese simulation query -> `app + code_studio_app + tool_create_visual_code + canvas`
- `tool_generate_visual` chart runtime metadata -> `renderer_kind=inline_html`, `runtime=sandbox_html`, `scene.render_surface=svg`

Blocked but unrelated to this patch:
- `python -m pytest maritime-ai-service/tests/unit/test_chat_request_flow.py -q`
  - fails during import because local environment has incompatible `sqlalchemy` version (`DeclarativeBase` missing)

## Ghi chú

Đây là slice backend/prompt an toàn:
- chưa xóa structured fallback
- chưa đổi sandbox renderer frontend
- chưa ép multi-figure LLM generation cho mọi article flow

Bước tiếp theo hợp lý:
- local/staging smoke test bằng prompt thật:
  - `Vẽ biểu đồ so sánh tốc độ các loại tàu container`
  - `Explain Kimi linear attention in charts`
  - `Hãy mô phỏng vật lý con lắc có kéo thả chuột`
