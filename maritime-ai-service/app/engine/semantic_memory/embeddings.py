"""
Embedding Generator for Semantic Memory.

Provides a centralized way to generate embeddings for fact storage
and retrieval. Uses the provider-agnostic semantic embedding backend.

Sprint 137: Created to enable semantic fact retrieval.
"""
import logging
from typing import List

logger = logging.getLogger(__name__)

_generator_instance = None


class EmbeddingGenerator:
    """Wrapper around the semantic embedding backend for backward compatibility."""

    def __init__(self):
        self._embeddings = None
        self._available = False
        self._init()

    def _init(self):
        try:
            from app.engine.embedding_runtime import get_semantic_embedding_backend

            self._embeddings = get_semantic_embedding_backend()
            self._available = bool(self._embeddings and self._embeddings.is_available())
            if self._available:
                logger.info(
                    "EmbeddingGenerator initialized with provider=%s model=%s dims=%s",
                    self._embeddings.provider,
                    self._embeddings.model_name,
                    self._embeddings.dimensions,
                )
            else:
                logger.warning("EmbeddingGenerator unavailable: no embedding backend resolved")
        except Exception as e:
            logger.warning("EmbeddingGenerator unavailable: %s", e)
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def generate(self, text: str) -> List[float]:
        """Generate embedding synchronously (for backward compat with fact_repository)."""
        if not self._available or not self._embeddings:
            return []
        try:
            return self._embeddings.embed_query(text)
        except Exception as e:
            logger.warning("Embedding generation failed: %s", e)
            return []

    async def agenerate(self, text: str) -> List[float]:
        """Generate embedding asynchronously."""
        if not self._available or not self._embeddings:
            return []
        try:
            return await self._embeddings.aembed_query(text)
        except Exception as e:
            logger.warning("Async embedding generation failed: %s", e)
            return []

    async def agenerate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts asynchronously."""
        if not self._available or not self._embeddings:
            return [[] for _ in texts]
        try:
            return await self._embeddings.aembed_documents(texts)
        except Exception as e:
            logger.warning("Batch embedding generation failed: %s", e)
            return [[] for _ in texts]


def get_embedding_generator() -> EmbeddingGenerator:
    """Get singleton EmbeddingGenerator instance."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = EmbeddingGenerator()
    return _generator_instance


def reset_embedding_generator() -> None:
    """Reset singleton generator for tests and runtime reconfiguration."""
    global _generator_instance
    _generator_instance = None
