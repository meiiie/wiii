# Vision Local Gemma3 Smoke — 2026-04-03

## Summary

After machine restart, local Ollama is alive and Wiii can now use a real local vision model for general vision lanes.

Current local outcome:

- `visual_describe` on Ollama: works
- `grounded_visual_answer` on Ollama: works
- selected local model: `gemma3:4b`
- OCR specialist lane is still separate and not solved by this local Gemma path

## Local Environment Truth

`/api/tags` currently reports these relevant local models:

- `embeddinggemma:latest`
- `gemma3:4b`

Text-only / cloud stubs also exist, but there is no local `qwen2.5vl` or `minicpm-v` yet.

## Runtime Hardening Added

Updated `vision_runtime` so Ollama local vision is no longer blocked when:

- global `ollama_model` is text-only
- a real local vision model is installed

New behavior:

- `gemma3` is recognized as an Ollama vision-capable model
- Ollama vision probe can auto-select an installed local VLM for describe/grounded lanes
- with current machine state, default local selection becomes `gemma3:4b`

Main file:

- `maritime-ai-service/app/engine/vision_runtime.py`

Regression tests:

- `maritime-ai-service/tests/unit/test_vision_runtime.py`

## Verification

Backend tests:

- `pytest tests/unit/test_vision_runtime.py tests/unit/test_vision_runtime_audit_service.py tests/unit/test_vision_selectability_service.py -q -p no:capture`
- Result: `17 passed`

Provider status sanity:

- `ollama + visual_describe` -> `available=True`, `model_name=gemma3:4b`
- `ollama + grounded_visual_answer` -> `available=True`, `model_name=gemma3:4b`

## Live Local Smoke

Image used:

- `docs/assets/screenshots/lms/lms-ai-chat-open.png`

Result:

- Describe succeeded on `ollama / gemma3:4b`
- Grounded answer succeeded on `ollama / gemma3:4b`

Representative outputs:

- describe: recognized the LMS learning interface and summarized the empty-course state correctly
- grounded: identified it as an LMS/Wiii-style learning UI and gave concrete visual cues from the screenshot

## Architectural Interpretation

This means Wiii now has a clean split:

- general local vision path can run today via `gemma3:4b`
- OCR-specialist path should still remain a dedicated lane, e.g. `GLM-OCR`

So:

- `visual_describe` and `grounded_visual_answer` can already be local-first on this machine
- `ocr_extract` should not be forced onto Gemma3 just because it can see images

## Recommended Next Step

If we continue optimizing local multimodal quality:

1. add and benchmark `qwen2.5vl` or `minicpm-v`
2. keep `gemma3:4b` as safe local fallback
3. keep OCR as a separate specialist lane instead of collapsing everything into one model
