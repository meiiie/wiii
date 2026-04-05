# Product Search + Code Studio Lifecycle E2E Matrix

Date: 2026-04-06  
Owner: Codex (LEADER)

## Summary

Khóa thêm một vòng E2E focused cho hai lane còn hở của chat lifecycle:

- `product_search`
- `code_studio`

Mục tiêu là đưa hai lane công cụ nặng này lên cùng mặt bằng với:

- `chat core lifecycle`
- `multimodal lifecycle`
- `provider/model request socket`

để hệ không chỉ đúng ở unit/runtime nhỏ lẻ, mà còn có regression ở tầng `API -> lane surface -> sync/stream contract`.

## Changes

### 1. New focused E2E matrix

Added:

- [test_product_code_lifecycle_e2e_matrix.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_product_code_lifecycle_e2e_matrix.py)

Coverage:

- `sync / product_search`
  - request carries `provider + model`
  - response preserves `routing_metadata.final_agent=product_search_agent`
  - thinking lifecycle surfaces through API
- `stream / product_search`
  - `status -> thinking_start -> tool_call -> answer -> metadata -> done`
  - product-search-specific routing survives SSE surface
- `sync / code_studio`
  - request carries `provider + model`
  - response preserves `agent_type=code_studio`
  - lifecycle and routing survive presenter surface
- `stream / code_studio`
  - `status -> thinking_start -> code_open -> code_delta -> code_complete -> metadata -> done`
  - code-studio-specific stream contract stays intact

### 2. Fixed stale Code Studio test import

Updated:

- [test_code_studio_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_code_studio_streaming.py)

Problem:

- test still imported `CODE_CHUNK_SIZE`, `CODE_CHUNK_DELAY_SEC`, `_maybe_emit_code_studio_events`
  from legacy `graph.py`
- current runtime owns them in `visual_events.py`
- result: suite failed during collection

Fix:

- switch import to `app.engine.multi_agent.visual_events`

This is a real regression cleanup, not just a test rewrite.

## Verification

Focused E2E matrix:

- `4 passed`

Broader lifecycle + multimodal + product/code verification:

- `187 passed`

Commands run:

```powershell
E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_product_code_lifecycle_e2e_matrix.py `
  -q -p no:capture --tb=short

E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_multimodal_lifecycle_e2e_matrix.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_code_studio_streaming.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_product_search_model_passthrough.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint179_visual_rag.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint186_visual_memory.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_vision_runtime.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint50_vision_extractor.py `
  -q -p no:capture --tb=short
```

## Current Truth

Ở mức focused lifecycle regression, hệ hiện đã có coverage cho:

- chat core sync/stream
- provider failover sync/stream
- multimodal vision/OCR/visual-rag/visual-memory
- product search sync/stream
- code studio sync/stream

Tức là phần `RAG -> chat -> tool-heavy lanes -> stream/sync surface` hiện đã kín hơn rất nhiều so với checkpoint trước.

## Residual Gaps

Những chỗ chưa nên gọi là full closure toàn hệ:

- live upstream provider parity cho `product_search` và `code_studio`
- `product_search` quality benchmark thật trên provider sống
- `code_studio` live artifact quality/preview E2E với frontend runtime thật
- full-path `vision + OCR + tutor + product/code` in one composite live scenario

## Assessment

Nhát này không thay đổi behavior production trực tiếp, nhưng nó:

- tăng độ tin cậy của vòng đời hệ thống
- bắt và dọn một regression test-collection thật
- giúp checkpoint “hệ đã kín E2E tới đâu” bớt mơ hồ hơn

Current assessment:

- `chat lifecycle core`: good
- `multimodal lifecycle`: good
- `product/code lifecycle`: now good at focused E2E level
- `full-system live closure`: still not fully done
