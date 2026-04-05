# Embedding Retrieval Benchmark

- Generated at: `2026-04-02T21:27:19.902374`
- Workspace: `E:\Sach\Sua\AI_v1`
- Database URL host: `localhost:5433`

## Summary

### ollama_local_first

- Active embedding backend: `ollama/embeddinggemma` `768d`
- Raw query embed: `5657.25 ms` (768 dims, ok=True)
- Raw document embed: `148.39 ms` (768 dims, ok=True)
- Semantic context: `210.77 ms`, memories=1, facts=1, tokens=36, threshold=0.3
- Hybrid search: `488.46 ms`, results=2, knowledge_embeddings=2, method=hybrid

Snapshot:
- `google` -> usable, model=`models/gemini-embedding-001`, active=False
- `openai` -> usable, model=`text-embedding-3-small`, active=False
- `openrouter` -> blocked:missing_api_key, model=`text-embedding-3-small`, active=False
- `ollama` -> usable, model=`embeddinggemma`, active=True
- `zhipu` -> blocked:model_unverified, model=`None`, active=False

Context preview:
- Fact: `name: Nam`
- Memory: `Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho có nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường.`

Hybrid preview:
- Result: `Quy t?c 15 c?a COLREGs m? t? t?nh hu?ng c?t ngang: khi hai t?u m?y ?ang ?i theo h??ng c?t nhau v? c? nguy c? va ch?m, t?u nh?n th?y t?u kia ? ph?a m?n ph?i ph?i`
- Result: `D?u hi?u th?c h?nh c?a Quy t?c 15 l? ph?i nh?n ra s?m m?n ph?i hay m?n tr?i, gi?m t?c ho?c ??i h??ng d?t kho?t ?? t?o CPA an to?n, ??ng th?i t?u ???c ?u ti?n v?`

### google_openai_auto

- Active embedding backend: `openai/text-embedding-3-small` `768d`
- Raw query embed: `3449.53 ms` (768 dims, ok=True)
- Raw document embed: `156.05 ms` (768 dims, ok=True)
- Semantic context: `236.87 ms`, memories=1, facts=1, tokens=36, threshold=0.3
- Hybrid search: `184.84 ms`, results=2, knowledge_embeddings=2, method=hybrid

Snapshot:
- `google` -> usable, model=`models/gemini-embedding-001`, active=False
- `openai` -> usable, model=`text-embedding-3-small`, active=True
- `openrouter` -> blocked:missing_api_key, model=`text-embedding-3-small`, active=False
- `ollama` -> usable, model=`embeddinggemma`, active=False
- `zhipu` -> blocked:model_unverified, model=`None`, active=False

Context preview:
- Fact: `name: Nam`
- Memory: `Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho có nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường.`

Hybrid preview:
- Result: `D?u hi?u th?c h?nh c?a Quy t?c 15 l? ph?i nh?n ra s?m m?n ph?i hay m?n tr?i, gi?m t?c ho?c ??i h??ng d?t kho?t ?? t?o CPA an to?n, ??ng th?i t?u ???c ?u ti?n v?`
- Result: `Quy t?c 15 c?a COLREGs m? t? t?nh hu?ng c?t ngang: khi hai t?u m?y ?ang ?i theo h??ng c?t nhau v? c? nguy c? va ch?m, t?u nh?n th?y t?u kia ? ph?a m?n ph?i ph?i`

Observations:
- `provider_promoted_to_openai`

### openai_large_768

- Active embedding backend: `openai/text-embedding-3-large` `768d`
- Raw query embed: `492.72 ms` (768 dims, ok=True)
- Raw document embed: `297.12 ms` (768 dims, ok=True)
- Semantic context: `269.61 ms`, memories=1, facts=1, tokens=36, threshold=0.3
- Hybrid search: `180.08 ms`, results=2, knowledge_embeddings=2, method=hybrid

Snapshot:
- `google` -> usable, model=`models/gemini-embedding-001`, active=False
- `openai` -> usable, model=`text-embedding-3-large`, active=True
- `openrouter` -> blocked:missing_api_key, model=`text-embedding-3-large`, active=False
- `ollama` -> usable, model=`embeddinggemma`, active=False
- `zhipu` -> blocked:model_unverified, model=`None`, active=False

Context preview:
- Fact: `name: Nam`
- Memory: `Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho có nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường.`

Hybrid preview:
- Result: `D?u hi?u th?c h?nh c?a Quy t?c 15 l? ph?i nh?n ra s?m m?n ph?i hay m?n tr?i, gi?m t?c ho?c ??i h??ng d?t kho?t ?? t?o CPA an to?n, ??ng th?i t?u ???c ?u ti?n v?`
- Result: `Quy t?c 15 c?a COLREGs m? t? t?nh hu?ng c?t ngang: khi hai t?u m?y ?ang ?i theo h??ng c?t nhau v? c? nguy c? va ch?m, t?u nh?n th?y t?u kia ? ph?a m?n ph?i ph?i`
