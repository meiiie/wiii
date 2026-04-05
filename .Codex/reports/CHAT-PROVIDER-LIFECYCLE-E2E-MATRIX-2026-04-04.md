# Chat Provider Lifecycle E2E Matrix

Date: 2026-04-04

## Summary

Má»‘c nÃ y thÃªm má»™t `E2E matrix` riÃªng cho `provider lifecycle` cá»§a chat: unavailable surface, auto failover surface, vÃ  model-switch prompt surface. Matrix nÃ y táº¡ch khá»i `lane lifecycle` Ä‘á»ƒ signal khÃ´ng bá»‹ nhiá»…u bá»Ÿ latency/upstream behavior.

## Covered Matrix

### Sync
- `explicit_provider_unavailable`
  - requested `provider=google`
  - verifies HTTP `503`, `PROVIDER_UNAVAILABLE`, `reason_code`, vÃ  `model_switch_prompt`
- `auto_failover_success_surface`
  - requested `provider=auto`
  - verifies success payload surface for `google -> zhipu`
  - checks normalized `failover` metadata on sync response

### Stream
- `explicit_provider_unavailable_stream`
  - requested `provider=google`
  - verifies `event:error` + `reason_code` + `model_switch_prompt` + `event:done`
- `auto_failover_stream_surface`
  - verifies stream metadata can surface `failover` + `hard_failover` model-switch prompt on success path

## Verification

### Provider Matrix
- `tests/unit/test_chat_failover_e2e_matrix.py`
- Result: `4 passed`

### Combined Chat Regression Batch
- `tests/unit/test_chat_lifecycle_e2e_matrix.py`
- `tests/unit/test_chat_failover_e2e_matrix.py`
- `tests/unit/test_chat_identity_projection.py`
- `tests/unit/test_runtime_endpoint_smoke.py`
- Result: `30 passed`

## Current Truth

- Chat hiá»‡n Ä‘Ã£ cÃ³ hai lá»›p E2E regression riÃªng:
  - `lane lifecycle`
  - `provider/failover lifecycle`
- Explicit provider outage surface hiá»‡n Ä‘Æ°á»£c chá»©ng minh á»•n Ä‘á»‹nh cho cáº£ sync lÃªn payload JSON vÃ  stream lÃªn SSE.
- Auto failover surface hiá»‡n Ä‘Æ°á»£c chá»©ng minh á»Ÿ má»©c metadata contract, khÃ´ng cÃ²n chỉ lÃ  unit riÃªng cho runtime internals.
- `model_switch_prompt` hiá»‡n Ä‘Ã£ cÃ³ regression cho cáº£:
  - unavailable provider
  - hard failover continuation

## Scope Notes

Matrix nÃ y lÃ  deterministic boundary regression, khÃ´ng phá»¥ thuá»™c vÃ o upstream provider tháº­t. Äiá»u Ä‘Ã³ lÃ  chá»§ Ä‘Ã­ch:

- lane/payload contract pháº£i á»•n Ä‘á»‹nh dÃ¹ upstream cháº­m hay quota
- live provider smoke váº«n cÃ³ giÃ¡ trá»‹, nhÆ°ng khÃ´ng nÃªn lÃ  regression gate duy nháº¥t

## Bottom Line

Äá»‘i vá»›i `chat` theo nghÄ©a hÄƒp `request -> auth projection -> orchestration boundary -> sync/stream surface`, Wiii hiá»‡n Ä‘Ã£ cÃ³ regression E2E khÃ¡ trÃ²n:

- `lane lifecycle matrix`: pass
- `provider lifecycle matrix`: pass
- `endpoint smoke`: pass

Pháº§n chÆ°a nÃªn tuyÃªn bá»‘ “done toÃ n há»‡” váº«n lÃ :
- full live provider E2E
- multimodal/vision/OCR E2E trong cÃ¹ng chuáº©n regression
- product search/code studio full-path E2E
