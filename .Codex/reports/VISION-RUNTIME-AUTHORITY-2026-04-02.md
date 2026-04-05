# Vision Runtime Authority - 2026-04-02

## Summary

Built a new shared `Vision Runtime authority` so the main Wiii vision lanes no longer each call provider-specific Gemini logic independently.

Primary migrated lanes:

- `visual_rag` query-time image understanding
- `vision_extractor` ingestion-time OCR/document extraction
- `visual_memory` image description for memory storage/retrieval

Core authority:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\vision_runtime.py`

## What Changed

### 1. Shared provider-neutral runtime

Added a new runtime with:

- capability routing:
  - `ocr_extract`
  - `visual_describe`
  - `grounded_visual_answer`
- provider order resolution from:
  - `vision_provider`
  - `vision_failover_chain`
  - fallback to `llm_failover_chain`
- fail-closed gating for unsupported/unverified backends
- image fetch + PIL conversion helpers
- unified `VisionResult` contract with provider/model/attempt metadata

### 2. Config surface

Added vision runtime settings:

- `vision_provider`
- `vision_failover_chain`
- `vision_timeout_seconds`

Files:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\config\_settings_base_fields.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\config\_settings.py`

### 3. Visual RAG migrated

`visual_rag` now delegates to vision runtime for:

- image fetch
- grounded visual analysis

File:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\agentic_rag\visual_rag.py`

### 4. Vision extractor migrated

`VisionExtractor` now prefers `vision_runtime.extract_document_markdown(...)` when running on the real runtime path.

Legacy `_client`-based Google seam is intentionally preserved for old unit tests and explicit legacy overrides.

File:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\vision_extractor.py`

### 5. Visual memory migrated

`VisualMemoryManager.describe_image(...)` now routes valid image payloads through `vision_runtime.describe_image_content(...)`.

A narrow compatibility path remains for invalid base64 / legacy mocked `google.genai.Client` tests.

File:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\semantic_memory\visual_memory.py`

### 6. CRAG contract drift fixed

While running visual RAG tests, a separate regression surfaced:

- `CorrectiveRAG.__init__` was resolving analyzer/grader/rewriter/verifier from `corrective_rag_setup.py`
- tests patched `app.engine.agentic_rag.corrective_rag.*`
- after refactor, those patches no longer affected runtime dependencies
- result: test accidentally invoked real query analysis LLM and hung

Fixed by threading module-level dependency factories and `settings` through `initialize_corrective_rag_impl(...)`.

Files:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\agentic_rag\corrective_rag.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\agentic_rag\corrective_rag_setup.py`

## Tests

Focused suites now passing:

- `tests/unit/test_vision_runtime.py`
- `tests/unit/test_sprint50_vision_extractor.py`
- `tests/unit/test_sprint53_vision_processor.py`
- `tests/unit/test_sprint179_visual_rag.py`
- `tests/unit/test_sprint186_visual_memory.py`

Result:

- `160 passed`

## Design Notes

This follows the same architectural direction already used elsewhere in Wiii:

- `Thinking Lifecycle authority`
- `Embedding Runtime authority`

The goal is the same:

- one backend authority
- provider-neutral contract
- explicit failover and capability gating
- no silent divergence between lanes

## Residuals

These are intentional for now:

1. `VisionExtractor` still keeps `_client` legacy compatibility
- Needed so old mocked tests and explicit Google-only override paths still work.

2. `VisualMemoryManager` keeps a narrow compatibility fallback
- Only used for invalid base64 or legacy mocked tests.
- Real valid image payloads now go through the shared authority.

3. Vision backend coverage is conservative
- `google` supported
- `openai/openrouter/ollama` supported behind capability checks
- `zhipu` remains fail-closed for vision until model contract is verified

## Recommended Next Steps

1. Build `vision selectability / audit snapshot` similar to embedding runtime.
2. Expose `vision_provider` policy in admin/runtime UI once provider contracts are stable.
3. Add a future `Vision Runtime smoke` script for live provider benchmarking.
