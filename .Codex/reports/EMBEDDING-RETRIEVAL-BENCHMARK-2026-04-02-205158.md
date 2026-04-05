# Embedding Retrieval Benchmark

- Generated at: `2026-04-02T20:51:58.247814`
- Workspace: `E:\Sach\Sua\AI_v1`
- Database URL host: `localhost:5433`

## Summary

### google_openai_auto

- Active embedding backend: `openai/text-embedding-3-small` `768d`
- Raw query embed: `4889.34 ms` (768 dims, ok=True)
- Raw document embed: `655.95 ms` (768 dims, ok=True)
- Semantic context: `2050.69 ms`, memories=1, facts=1, tokens=36, threshold=0.3
- Hybrid search: `673.9 ms`, results=2, knowledge_embeddings=2, method=hybrid

Snapshot:
- `google` -> usable, model=`models/gemini-embedding-001`, active=False
- `openai` -> usable, model=`text-embedding-3-small`, active=True
- `openrouter` -> usable, model=`text-embedding-3-small`, active=False
- `ollama` -> blocked:host_down, model=`embeddinggemma`, active=False
- `zhipu` -> blocked:model_unverified, model=`None`, active=False

Context preview:
- Fact: `name: Nam`
- Memory: `Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho có nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường.`

Hybrid preview:
- Result: `D?u hi?u th?c h?nh c?a Quy t?c 15 l? ph?i nh?n ra s?m m?n ph?i hay m?n tr?i, gi?m t?c ho?c ??i h??ng d?t kho?t ?? t?o CPA an to?n, ??ng th?i t?u ???c ?u ti?n v?`
- Result: `Quy t?c 15 c?a COLREGs m? t? t?nh hu?ng c?t ngang: khi hai t?u m?y ?ang ?i theo h??ng c?t nhau v? c? nguy c? va ch?m, t?u nh?n th?y t?u kia ? ph?a m?n ph?i ph?i`

Observations:
- `provider_promoted_to_openai`

### ollama_local_first

- Active embedding backend: `openai/text-embedding-3-small` `768d`
- Raw query embed: `2207.31 ms` (768 dims, ok=True)
- Raw document embed: `728.08 ms` (768 dims, ok=True)
- Semantic context: `364.17 ms`, memories=1, facts=1, tokens=36, threshold=0.3
- Hybrid search: `318.83 ms`, results=2, knowledge_embeddings=2, method=hybrid

Snapshot:
- `google` -> usable, model=`models/gemini-embedding-001`, active=False
- `openai` -> usable, model=`text-embedding-3-small`, active=True
- `openrouter` -> usable, model=`text-embedding-3-small`, active=False
- `ollama` -> blocked:host_down, model=`embeddinggemma`, active=False
- `zhipu` -> blocked:model_unverified, model=`None`, active=False

Context preview:
- Fact: `name: Nam`
- Memory: `Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho có nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường.`

Hybrid preview:
- Result: `D?u hi?u th?c h?nh c?a Quy t?c 15 l? ph?i nh?n ra s?m m?n ph?i hay m?n tr?i, gi?m t?c ho?c ??i h??ng d?t kho?t ?? t?o CPA an to?n, ??ng th?i t?u ???c ?u ti?n v?`
- Result: `Quy t?c 15 c?a COLREGs m? t? t?nh hu?ng c?t ngang: khi hai t?u m?y ?ang ?i theo h??ng c?t nhau v? c? nguy c? va ch?m, t?u nh?n th?y t?u kia ? ph?a m?n ph?i ph?i`

Observations:
- `provider_promoted_to_openai`
