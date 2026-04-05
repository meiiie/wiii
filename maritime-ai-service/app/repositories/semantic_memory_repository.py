"""
Semantic Memory Repository for Wiii v0.3.

Facade class that keeps repository bootstrap/session ownership in one place
 while delegating specialized behavior to dedicated mixin modules:
- FactRepositoryMixin: Fact CRUD, semantic triples, deduplication
- InsightRepositoryMixin: Insight retrieval and management
- VectorMemoryRepositoryMixin: Vector similarity search
- SemanticMemoryRepositoryRuntimeMixin: core CRUD and running summary lifecycle
"""

import logging
from typing import List, Optional

from app.repositories.fact_repository import FactRepositoryMixin
from app.repositories.insight_repository import InsightRepositoryMixin
from app.repositories.semantic_memory_repository_runtime import (
    SemanticMemoryRepositoryRuntimeMixin,
)
from app.repositories.vector_memory_repository import VectorMemoryRepositoryMixin

logger = logging.getLogger(__name__)


class SemanticMemoryRepository(
    SemanticMemoryRepositoryRuntimeMixin,
    FactRepositoryMixin,
    InsightRepositoryMixin,
    VectorMemoryRepositoryMixin,
):
    """
    Repository facade for semantic memory CRUD operations with pgvector.

    The shell owns the shared engine/session bootstrap while concrete
    operations live in mixins so the class can keep growing without turning
    back into another god-file.
    """

    TABLE_NAME = "semantic_memories"
    DEFAULT_SEARCH_LIMIT = 5
    DEFAULT_SIMILARITY_THRESHOLD = 0.7

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize repository with SHARED database connection.

        Args:
            database_url: Ignored - uses shared engine for connection pooling
        """
        self._engine = None
        self._session_factory = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization using the shared database engine."""
        if not self._initialized:
            try:
                from app.core.database import (
                    get_shared_engine,
                    get_shared_session_factory,
                )

                self._engine = get_shared_engine()
                self._session_factory = get_shared_session_factory()
                self._initialized = True
                logger.info("SemanticMemoryRepository using SHARED database engine")
            except Exception as exc:
                logger.error("Failed to initialize SemanticMemoryRepository: %s", exc)
                raise

    def _format_embedding(self, embedding: List[float]) -> str:
        """Format embedding list as pgvector string."""
        if embedding is None or len(embedding) == 0:
            logger.warning("Received None or empty embedding, using empty vector")
            return "[]"
        return f"[{','.join(str(x) for x in embedding)}]"


def get_semantic_memory_repository() -> SemanticMemoryRepository:
    """Get a configured SemanticMemoryRepository instance."""
    return SemanticMemoryRepository()
