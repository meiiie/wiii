# Chat Lifecycle E2E Matrix

Date: 2026-04-04

## Summary

Má»‘c nÃ y khÃ³a má»™t `E2E matrix` gÃ²n cho vÃ²ng Ä‘á»i `request -> auth projection -> orchestration -> sync/stream response surface` cá»§a Wiii, táº­p trung vÃ o cÃ¡c lane á»•n Ä‘á»‹nh vÃ  cáº§n giá»¯ parity.

Matrix nÃ y **khÃ´ng** trá»™n cÃ¡c case failover/provider recovery vÃ o chung vá»›i lane lifecycle. Pháº§n failover Ä‘Æ°á»£c giá»¯ á»Ÿ `endpoint smoke` riÃªng Ä‘á»ƒ trÃ¡nh nhiá»…u do runtime/provider side effects.

## Covered Matrix

### Sync
- `direct_selfhood`
  - explicit `provider=openrouter`
  - explicit `model=qwen/qwen3.6-plus:free`
  - verifies `thinking_content`, `thinking_lifecycle`, `routing_metadata.intent=selfhood`
- `memory_roundtrip`
  - explicit `provider=zhipu`
  - explicit `model=glm-5`
  - verifies `memory` lane + lifecycle phases
- `rag_lookup`
  - explicit `provider=openrouter`
  - explicit `model=qwen/qwen3.6-plus:free`
  - verifies `rag` lane + sources + lookup routing

### Stream
- `direct_origin_stream`
  - verifies `thinking_start -> thinking_delta -> thinking_end -> answer -> metadata -> done`
- `tutor_visual_stream`
  - verifies `status -> tool_call -> sources -> metadata -> done`
- `rag_lookup_stream`
  - verifies `thinking + answer + sources + routing_metadata.intent=lookup`

## Verification

### Lifecycle Matrix
- `tests/unit/test_chat_lifecycle_e2e_matrix.py`
- Result: `6 passed`

### Endpoint/Auth Projection Smoke
- `tests/unit/test_chat_identity_projection.py`
- `tests/unit/test_runtime_endpoint_smoke.py`
- Result: included in combined batch below

### Combined Backend Batch
- `tests/unit/test_chat_lifecycle_e2e_matrix.py`
- `tests/unit/test_chat_identity_projection.py`
- `tests/unit/test_runtime_endpoint_smoke.py`
- Result: `26 passed`

### Frontend Request Socket Batch
- `src/__tests__/model-store.test.ts`
- `src/__tests__/use-sse-stream-concurrency.test.ts`
- Result: `8 passed`

## Current Truth

- `provider + model` hiá»‡n Ä‘Ã£ lÃ  socket tháº­t tá»« desktop/API xuá»‘ng processing boundary.
- Sync + stream Ä‘á»u cÃ³ smoke/lifecycle coverage cho `direct`, `memory`, `rag`, `tutor visual`.
- `thinking_lifecycle` hiá»‡n Ä‘Ã£ Ä‘i qua Ä‘Æ°á»£c response surface thay vÃ¬ chá»‰ Ä‘Æ°á»£c test á»Ÿ unit runtime riÃªng láº».
- `RAG -> chat` á»Ÿ má»©c request/response surface Ä‘Ã£ cÃ³ E2E matrix gÃ²n vÃ  pass.

## Intentional Scope Boundary

Nhá»¯ng thá»© **chÆ°a** nÃªn xem lÃ  Ä‘Ã£ khÃ³a xong chÆ°a:

- Full live upstream E2E vá»›i provider tháº­t cho táº¥t cáº£ lane
- Product search / OCR / visual grounded / code studio trong cÃ¹ng má»™t E2E matrix chung
- Failover/recovery matrix trÃªn provider tháº­t

LÃ½ do:
- cÃ¡c case Ä‘Ã³ cÃ²n mang nhiá»u yáº¿u tá»‘ mÃ´i trÆ°á»ng (latency, quota, upstream availability)
- náº¿u trÃ¬nh bÃ y chÃºng nhÆ° lane-lifecycle test sáº½ lÃ m má» tín hiệu kiáº¿n trÃºc

## Recommended Next Steps

1. Giá»¯ `lifecycle matrix` nÃ y lÃ m regression core cho `chat`.
2. Duy trÃ¬ `failover/model-switch` á»Ÿ smoke suite riÃªng.
3. Náº¿u muá»‘n tiáº¿n tá»›i “full E2E toÃ n há»‡”, hÃ£y tÃ¡ch thÃªm 2 matrix riÃªng:
   - `multimodal lifecycle matrix`
   - `provider failover/recovery matrix`

## Bottom Line

VÃ²ng Ä‘á»i cốt lõi `RAG -> chat -> sync/stream surface` hiá»‡n Ä‘Ã£ cÃ³ E2E matrix pass á»Ÿ má»©c regression chuyÃªn nghiá»‡p.

NhÆ°ng toÃ n há»‡ Wiii chÆ°a nÃªn tuyÃªn bá»‘ “full E2E done” cho táº¥t cáº£ lane/provider. Tráº¡ng thÃ¡i Ä‘Ãºng nháº¥t hiá»‡n táº¡i lÃ :

- `core chat lifecycle`: khÃ³a khá cháº¯c
- `provider failover/live multimodal`: Ä‘Ã£ cÃ³ smoke/audit, nhÆ°ng chÆ°a gá»™p thÃ nh full-system live E2E matrix cuá»‘i cÃ¹ng
