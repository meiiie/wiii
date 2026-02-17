"""
Vector Memory Repository Mixin for Semantic Memory
Extracted from semantic_memory_repository.py for modularity.

Contains vector search operations:
- search_similar (cosine similarity search via pgvector)
- _stanford_rerank (Sprint 98: Stanford Generative Agents hybrid re-ranking)

Requirements: 2.2, 2.3, 2.4, 4.2
"""
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.models.semantic_memory import (
    MemoryType,
    SemanticMemorySearchResult,
)

logger = logging.getLogger(__name__)


class VectorMemoryRepositoryMixin:
    """
    Mixin class providing vector search operations for SemanticMemoryRepository.

    Requires the host class to provide:
    - self._ensure_initialized() -> None
    - self._session_factory -> sessionmaker
    - self._format_embedding(embedding) -> str
    - self.TABLE_NAME -> str
    - self.DEFAULT_SEARCH_LIMIT -> int
    - self.DEFAULT_SIMILARITY_THRESHOLD -> float
    """

    def search_similar(
        self,
        user_id: str,
        query_embedding: List[float],
        limit: int = 5,
        threshold: float = 0.7,
        memory_types: Optional[List[MemoryType]] = None,
        include_all_sessions: bool = True,
        use_stanford_ranking: bool = False,
    ) -> List[SemanticMemorySearchResult]:
        """
        Search for similar memories using cosine similarity.

        Cross-session Memory Persistence (v0.2.1):
        - By default, searches across ALL sessions for the user_id
        - Uses pgvector's <=> operator for cosine distance
        - Results are ordered by similarity (descending)

        Sprint 98: Stanford Generative Agents re-ranking
        - When use_stanford_ranking=True, fetches 3x candidates
        - Re-ranks by weighted sum: alpha*recency + beta*importance + gamma*relevance
        - Uses Ebbinghaus retention from importance_decay.py

        Args:
            user_id: User ID to filter memories
            query_embedding: Query vector (768 dimensions)
            limit: Maximum number of results
            threshold: Minimum similarity threshold (0.0 - 1.0)
            memory_types: Optional filter by memory types
            include_all_sessions: If True (default), search across all sessions
            use_stanford_ranking: If True, apply Stanford hybrid re-ranking

        Returns:
            List of SemanticMemorySearchResult ordered by similarity (or Stanford score)

        Requirements: 2.2, 2.3, 2.4, 4.2
        **Feature: cross-session-memory, Property 6: Search Across All Sessions**
        """
        self._ensure_initialized()

        # Stanford ranking fetches more candidates for re-ranking
        fetch_limit = limit * 3 if use_stanford_ranking else limit

        try:
            with self._session_factory() as session:
                embedding_str = self._format_embedding(query_embedding)

                # Build type filter if specified
                type_filter = ""
                params = {
                    "user_id": user_id,
                    "embedding": embedding_str,
                    "threshold": threshold,
                    "limit": fetch_limit
                }

                if memory_types:
                    type_values = [t.value for t in memory_types]
                    type_filter = "AND memory_type = ANY(:memory_types)"
                    params["memory_types"] = type_values

                # Cosine similarity = 1 - cosine distance
                # pgvector <=> returns cosine distance
                # Sprint 98: Also fetch last_accessed, access_count for Stanford ranking
                query = text(f"""
                    SELECT
                        id,
                        content,
                        memory_type,
                        importance,
                        metadata,
                        created_at,
                        last_accessed,
                        access_count,
                        1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :threshold
                      {type_filter}
                    ORDER BY embedding <=> CAST(:embedding AS vector)
                    LIMIT :limit
                """)

                result = session.execute(query, params)
                rows = result.fetchall()

                memories = []
                for row in rows:
                    # Handle NaN similarity (can happen with zero vectors)
                    similarity = float(row.similarity) if row.similarity is not None else 0.0
                    if math.isnan(similarity) or math.isinf(similarity):
                        similarity = 0.0
                    # Clamp to valid range [0, 1]
                    similarity = max(0.0, min(1.0, similarity))

                    memories.append(SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=similarity,
                        metadata=row.metadata or {},
                        created_at=row.created_at
                    ))

                # Sprint 98: Stanford Generative Agents hybrid re-ranking
                if use_stanford_ranking and memories:
                    # Build row data for reranking (need last_accessed, access_count)
                    row_data = []
                    for i, row in enumerate(rows):
                        last_accessed = getattr(row, "last_accessed", None)
                        access_count = getattr(row, "access_count", None) or 0
                        row_data.append({
                            "last_accessed": last_accessed,
                            "access_count": access_count,
                        })
                    memories = self._stanford_rerank(memories, row_data, limit)

                logger.debug("Found %d similar memories for user %s", len(memories), user_id)
                return memories

        except Exception as e:
            logger.error("Failed to search similar memories: %s", e)
            return []

    def _stanford_rerank(
        self,
        memories: List[SemanticMemorySearchResult],
        row_data: List[Dict[str, Any]],
        limit: int,
    ) -> List[SemanticMemorySearchResult]:
        """
        Re-rank memories using Stanford Generative Agents formula.

        score = alpha * recency + beta * importance + gamma * relevance

        Recency uses Ebbinghaus forgetting curve from importance_decay.py.
        All components normalized to [0, 1].

        Args:
            memories: Candidate memories from similarity search
            row_data: Parallel list with last_accessed, access_count per memory
            limit: Final number of results to return

        Returns:
            Top `limit` memories sorted by Stanford composite score
        """
        try:
            from app.core.config import settings
            alpha = settings.stanford_recency_weight
            beta = settings.stanford_importance_weight
            gamma = settings.stanford_relevance_weight
        except Exception:
            alpha, beta, gamma = 0.3, 0.3, 0.4

        try:
            from app.engine.semantic_memory.importance_decay import calculate_retention, get_stability_hours
        except ImportError:
            # Fallback: skip reranking if decay module unavailable
            return memories[:limit]

        now = datetime.now(timezone.utc)
        scored = []

        for i, mem in enumerate(memories):
            # Relevance = similarity (already 0-1)
            relevance = mem.similarity

            # Importance (already 0-1)
            importance = mem.importance

            # Recency via Ebbinghaus retention
            data = row_data[i] if i < len(row_data) else {}
            last_accessed = data.get("last_accessed")
            access_count = data.get("access_count", 0) or 0

            reference_time = last_accessed or mem.created_at
            if reference_time is not None:
                if reference_time.tzinfo is None:
                    reference_time = reference_time.replace(tzinfo=timezone.utc)
                hours_elapsed = max((now - reference_time).total_seconds() / 3600.0, 0.0)
            else:
                hours_elapsed = 0.0

            # Get fact_type from metadata for stability calculation
            fact_type = mem.metadata.get("fact_type", "preference")
            stability = get_stability_hours(fact_type)
            recency = calculate_retention(hours_elapsed, stability, access_count)

            score = alpha * recency + beta * importance + gamma * relevance
            scored.append((score, mem))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:limit]]
