# Multimodal Lifecycle E2E Matrix

Date: 2026-04-06

## Summary

This round closes one of the main gaps left after the previous system checkpoint:

- chat core already had lifecycle E2E coverage
- multimodal runtime did not yet have a compact regression matrix spanning:
  - OCR specialist and fallback routing
  - visual RAG enrichment
  - visual memory injection into chat context

This report records the new matrix, the bug found while building it, and the current truth after the fix.

## Added E2E Matrix

New focused suite:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_multimodal_lifecycle_e2e_matrix.py`

Covered paths:

### 1. OCR runtime lifecycle

- `ocr_specialist_success`
  - `zhipu / glm-ocr`
- `ocr_fallback_success`
  - `zhipu / glm-ocr` fails
  - fallback to `ollama / gemma3:4b`

What is asserted:

- provider attempt order
- final provider selection
- fallback only after specialist failure
- OCR path still returns structured markdown text

### 2. Vision extractor runtime surface

- `VisionExtractor.extract_from_image(...)`
- runtime markdown from shared vision authority is analyzed into:
  - `has_tables`
  - `headings_found`

### 3. Visual RAG enrichment lifecycle

- `enrich_documents_with_visual_context(...)`

What is asserted:

- visual docs are enriched
- `visual_description` is attached
- original non-visual docs remain unchanged
- content keeps page-aware visual annotation

### 4. Visual memory -> chat context lifecycle

- `build_context_impl(...)`
- visual memory retrieval injects semantic context
- base64 image attachments schedule visual memory storage

What is asserted:

- visual memory context reaches chat context
- image storage scheduling happens on image-bearing turns
- multimodal context wiring is alive at input-processing level

## Bug Found And Fixed

While building the matrix, one real bug surfaced in:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\vision_extractor.py`

Problem:

- OCR markdown tables using normal separator rows such as:
  - `| --- | --- |`
- were not detected as tables by `VisionExtractor._analyze_extraction(...)`

Cause:

- the regex only matched a too-narrow separator form

Fix:

- broadened table separator detection so standard markdown table separators with whitespace are recognized

Impact:

- OCR specialist/fallback output is now interpreted more correctly by the extractor layer
- the matrix catches this class of regression going forward

## Legacy Test Alignment

Some older tests still mocked the old direct-Gemini path instead of the newer shared vision authority.

Updated test files:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint179_visual_rag.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint186_visual_memory.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_vision_runtime.py`

What changed:

- visual RAG tests now mock `analyze_image_for_query(...)`
- visual memory store test now mocks `describe_image_content(...)`
- OCR provider-order test now neutralizes persisted audit demotion noise so the expectation remains deterministic

This keeps older coverage aligned with the current architecture:

- one shared vision authority
- capability-aware routing
- specialist vs fallback OCR behavior

## Verification

Focused multimodal batch:

- `test_multimodal_lifecycle_e2e_matrix.py`
- `test_sprint179_visual_rag.py`
- `test_sprint186_visual_memory.py`
- `test_vision_runtime.py`
- `test_sprint50_vision_extractor.py`

Result:

- `168 passed`

## Current Truth

### What is now stronger

- multimodal runtime is no longer only covered by unit slices
- OCR specialist/fallback has its own regression matrix
- visual RAG enrichment has lifecycle coverage
- visual memory is now covered at chat-context assembly level

### What this means system-wide

- the gap between `chat core E2E` and `multimodal runtime reality` is smaller now
- the system has a more credible end-to-end story from:
  - image/document understanding
  - visual enrichment
  - memory/context injection
  - into chat processing

### What is still not fully closed

- product search full-path E2E
- code studio full-path E2E
- live provider benchmark parity for the multimodal matrix

## Practical Conclusion

This round did not rebuild foundations.

It did the more valuable thing:

- connected the multimodal authorities already built
- exposed a real OCR parsing bug
- fixed it
- and left behind a compact regression matrix so this part of the system is harder to silently break again.
