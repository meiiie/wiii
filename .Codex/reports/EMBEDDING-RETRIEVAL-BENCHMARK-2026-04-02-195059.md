# Embedding Retrieval Benchmark

- Generated at: `2026-04-02T19:50:59.731541`
- Workspace: `E:\Sach\Sua\AI_v1`
- Database URL host: `localhost:5433`

## Summary

### google_first

- Active embedding backend: `google/models/gemini-embedding-001` `768d`
- Raw query embed: `3197.24 ms` (0 dims, ok=False)
- Raw document embed: `148.08 ms` (768 dims, ok=True)
- Semantic context: `264.28 ms`, memories=0, facts=1, tokens=2, threshold=0.3
- Hybrid search: `485.96 ms`, results=0, knowledge_embeddings=0, method=None

Snapshot:
- `google` -> usable, model=`models/gemini-embedding-001`, active=True
- `openai` -> blocked:missing_api_key, model=`text-embedding-3-small`, active=False
- `openrouter` -> blocked:missing_api_key, model=`text-embedding-3-small`, active=False
- `ollama` -> usable, model=`embeddinggemma`, active=False
- `zhipu` -> blocked:model_unverified, model=`None`, active=False

Context preview:
- Fact: `name: Nam`

Observations:
- `query_embedding_failed_or_empty`
- `knowledge_embedding_store_empty`

### ollama_local_first

- Active embedding backend: `ollama/embeddinggemma` `768d`
- Raw query embed: `1632.84 ms` (768 dims, ok=True)
- Raw document embed: `146.47 ms` (768 dims, ok=True)
- Semantic context: `193.87 ms`, memories=1, facts=1, tokens=36, threshold=0.3
- Hybrid search: `152.52 ms`, results=0, knowledge_embeddings=0, method=None

Snapshot:
- `google` -> usable, model=`models/gemini-embedding-001`, active=False
- `openai` -> blocked:missing_api_key, model=`text-embedding-3-small`, active=False
- `openrouter` -> blocked:missing_api_key, model=`text-embedding-3-small`, active=False
- `ollama` -> usable, model=`embeddinggemma`, active=True
- `zhipu` -> blocked:model_unverified, model=`None`, active=False

Context preview:
- Fact: `name: Nam`
- Memory: `Quy tắc 15 là tình huống hai tàu máy đi theo hướng cắt nhau sao cho có nguy cơ va chạm; tàu thấy tàu kia ở phía mạn phải phải tránh đường.`

Observations:
- `knowledge_embedding_store_empty`
