# Vision Local Model Selection — 2026-04-03

## Summary

After local benchmarking on the current workstation, `gemma3:4b` is the correct default local-first vision model for Wiii right now.

`qwen2.5vl:3b` is now supported by runtime recognition, but it is not a good default on this machine because it is dramatically slower and unstable under the current local stack.

## What Was Tested

Local models present after restart:

- `embeddinggemma:latest`
- `gemma3:4b`
- `qwen2.5vl:3b`

Images used:

- `docs/assets/screenshots/lms/lms-ai-chat-open.png`
- `docs/assets/screenshots/deploy/wiii-deploy-swagger.png`

Capabilities tested:

- `visual_describe`
- `grounded_visual_answer`

Artifacts:

- `E:/Sach/Sua/AI_v1/.Codex/reports/vision-local-model-benchmark-2026-04-03.json`
- `E:/Sach/Sua/AI_v1/.Codex/reports/vision-local-qwen25vl-rerun-2026-04-03.json`
- `E:/Sach/Sua/AI_v1/.Codex/reports/qwen25vl-direct-rest-2026-04-03.json`
- `E:/Sach/Sua/AI_v1/.Codex/reports/ollama-tags-after-restart-2026-04-03.json`

## Current Truth

### Gemma3

`gemma3:4b` works for both local general-vision lanes:

- `visual_describe`: success
- `grounded_visual_answer`: success

Observed benchmark summary:

- average latency: about `29.2s`
- success rate: `4/4`

Representative behavior:

- correctly recognizes LMS-style UI
- correctly recognizes Swagger/API documentation layout
- gives grounded answers that are usable for Wiii visual reasoning

### Qwen2.5-VL 3B

`qwen2.5vl:3b` is recognized by the runtime now, but it is not production-worthy on this workstation.

Observed behavior:

- runtime benchmark: `0/4` success within the Wiii path
- direct Ollama REST call: returned only after about `107.5s` on a single short caption request
- Wiii runtime calls timed out at the lane timeout before useful output came back

Meaning:

- the model is not "unsupported"
- it is simply too slow / too heavy for the current local operating point

## Architecture Decisions Taken

### 1. Runtime recognition widened

`vision_runtime` now recognizes:

- `gemma3`
- `qwen25vl`
- `qwen2.5vl`

for Ollama vision capability checks.

### 2. Autoselect made safer

Ollama autoselect no longer:

- upgrades a smaller family model to a fake family stem
- picks the wrong family/size because of overly broad substring matching

It now prefers exact installed tags and safer selection behavior.

### 3. Default local-first choice hardened

On this machine, autoselect currently resolves to:

- `ollama / gemma3:4b`

for both:

- `visual_describe`
- `grounded_visual_answer`

That is intentional and based on measured behavior, not preference by brand.

## Verification

Tests:

- `pytest tests/unit/test_vision_runtime.py -q -p no:capture`
- Result: `14 passed`

Live local status after final patch:

- `ollama + visual_describe` -> `available=True`, `model_name=gemma3:4b`
- `ollama + grounded_visual_answer` -> `available=True`, `model_name=gemma3:4b`

## Recommendation

For this workstation and current local stack:

- default local vision model:
  - `gemma3:4b`
- keep `qwen2.5vl:3b` as:
  - manual override / research candidate
  - not the default
- keep OCR separate:
  - general local VLM should not replace OCR-specialist routing

## Next Step

If we continue improving local multimodal quality, the most sensible path is:

1. keep `gemma3:4b` as the live local default now
2. benchmark a stronger local candidate later, such as:
   - `qwen2.5vl:7b`
   - `minicpm-v`
3. keep `ocr_extract` as a specialist lane instead of collapsing everything into one model
