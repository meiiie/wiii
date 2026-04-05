# Embedding Policy Local-First Verify

- timestamp: 2026-04-02-213438
- embedding_provider: google
- embedding_failover_chain: ['google', 'openai', 'ollama', 'openrouter']
- embedding_model: models/gemini-embedding-001
- embedding_dimensions: 768

## Selectability
- google: available=True, active=True, reason=None, model=models/gemini-embedding-001, dims=768
- openai: available=False, active=False, reason=missing_api_key, model=text-embedding-3-small, dims=768
- openrouter: available=False, active=False, reason=missing_api_key, model=text-embedding-3-small, dims=768
- ollama: available=True, active=False, reason=None, model=embeddinggemma, dims=768
- zhipu: available=False, active=False, reason=model_unverified, model=None, dims=None
