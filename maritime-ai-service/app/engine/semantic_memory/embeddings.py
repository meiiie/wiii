"""
Embedding Generator for Semantic Memory.

Provides a centralized way to generate embeddings for fact storage
and retrieval. Uses GeminiOptimizedEmbeddings as the backend.

Sprint 137: Created to enable semantic fact retrieval.
"""
import logging
from typing import List

logger = logging.getLogger(__name__)

_generator_instance = None


class EmbeddingGenerator:
    """Wrapper around GeminiOptimizedEmbeddings for semantic memory use."""

    def __init__(self):
        self._embeddings = None
        self._available = False
        self._init()

    def _init(self):
        try:
            from app.engine.gemini_embedding import GeminiOptimizedEmbeddings
            self._embeddings = GeminiOptimizedEmbeddings()
            self._available = True
            logger.info("EmbeddingGenerator initialized with GeminiOptimizedEmbeddings")
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
