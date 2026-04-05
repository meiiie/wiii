# Vision Post-Reset OCR Checkpoint — 2026-04-03

## Summary

Sau khi máy restart, mình đã kéo lại runtime và xác nhận lại state thật của `vision + embeddings` trước khi tiếp tục sửa.

Kết quả hiện tại:

- `wiii-postgres` và `wiii-app` đã lên lại, health endpoint sống.
- Runtime policy thực tế của app vẫn đúng với hướng local-first đã chốt:
  - `embedding_provider=auto`
  - `embedding_failover_chain=[ollama, openai, google]`
  - `embedding_model=embeddinggemma`
  - `vision_describe_provider=ollama`
  - `vision_describe_model=gemma3:4b`
  - `vision_ocr_provider=auto`
  - `vision_ocr_model=glm-ocr`
  - `vision_grounded_provider=ollama`
  - `vision_grounded_model=gemma3:4b`

## Verified Current Truth

### 1. Local general vision is live again

Host-side smoke on `docs/assets/screenshots/lms/lms-ai-chat-open.png` succeeded:

- `visual_describe` → `ollama / gemma3:4b`
- `grounded_visual_answer` → `ollama / gemma3:4b`

The local outputs are imperfect in wording, but they are real model outputs and confirm the lane is alive after reboot.

### 2. Local-first embeddings are alive inside app container

Container-side embed query succeeded with:

- `provider=ollama`
- `model=embeddinggemma`
- `dimensions=768`
- `vector_len=768`

This confirms the canonical embedding space is still healthy after reboot.

### 3. GLM-OCR root cause has been fixed

The old OCR failure was **not** because `GLM-OCR` itself was broken.

Root cause:

- `_run_zhipu_layout_parsing_request()` was sending raw base64 in `file`
- Zhipu `layout_parsing` accepts URL or `data:<mime>;base64,...`
- raw base64 caused `400 Bad Request`

Patch applied:

- `app/engine/vision_runtime.py`

Changes:

- added `_build_image_data_url(...)`
- `GLM-OCR` requests now send `file="data:image/...;base64,..."` instead of raw base64
- added a shorter connect timeout for Zhipu OCR so failover happens faster when upstream is unstable

Regression coverage:

- `tests/unit/test_vision_runtime.py`
- focused suite result: `17 passed`

## Live OCR Reality After The Fix

After the payload fix, the failure mode changed:

- direct `layout_parsing` probe with a `data:` URL can return `200 OK`
- the previous `400` is gone

But current live upstream behavior is unstable:

- one direct probe succeeded quickly
- later probes hit `ConnectTimeout` / `ConnectError`

Inside Wiii runtime this now looks like:

- `zhipu / glm-ocr` is attempted first for OCR
- if upstream is unavailable, the lane falls back to `ollama / gemma3:4b`
- recent measured end-to-end OCR call completed in about `32.3s`
- the result succeeded through local fallback, not through Zhipu

So the current truth is:

- **payload contract bug is fixed**
- **remaining OCR instability is now upstream/network/provider behavior**
- **Wiii still completes the turn thanks to fallback**

## Vision Audit Snapshot

I refreshed the live vision audit after reboot. The persisted audit now reflects:

- `ollama`: current live probes degraded mostly by timeout
- `zhipu OCR`: current live probe degraded by temporary provider unavailability
- `zhipu general vision`: still intentionally fail-closed except for OCR-specialist lane

## Practical Conclusion

The system is in a much better state than before reboot:

- local general vision is back
- local-first embeddings are back
- OCR contract with `GLM-OCR` is corrected
- the main residual issue is **Zhipu OCR availability**, not internal request formatting anymore

If continuing from here, the next highest-value step is not another broad refactor.
It is to harden OCR routing against transient upstream instability:

- either recent-failure-aware provider demotion for `zhipu OCR`
- or a stricter fast-fail policy so local fallback engages sooner
