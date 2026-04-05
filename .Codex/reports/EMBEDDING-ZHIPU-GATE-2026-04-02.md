# Embedding Zhipu Gate

Date: 2026-04-02

## Summary
- Hardened the shared embedding runtime so `provider="zhipu"` now fails closed.
- Reason: the current Wiii embedding catalog has no explicit verified Zhipu embedding model contract yet.
- This does **not** affect GLM chat/runtime support. It only blocks the embedding backend from pretending it is ready.

## Changes
- `model_catalog.get_default_embedding_model_for_provider("zhipu")` now returns `None`
- `embedding_runtime._build_backend("zhipu")` now skips initialization with a clear warning
- Added tests covering:
  - no default Zhipu embedding model
  - `SemanticEmbeddingBackend` unavailable when forced to `zhipu`

## Verification
- Focused suite:
  - `11 passed`
- Runtime smoke:
  - forcing `embedding_provider='zhipu'` now yields:
    - `available=False`
    - `provider=None`
    - `model=None`

## Notes
- This keeps Wiii honest while the embedding layer is being generalized.
- Once there is an explicit official Zhipu embedding model contract and we can catalog dimensions/compatibility cleanly, this gate can be reopened with tests instead of guesses.
