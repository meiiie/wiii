"""
Insight Repository Mixin for Semantic Memory
Extracted from semantic_memory_repository.py for modularity.

Contains insight-related operations:
- get_user_insights
- delete_user_insights
- get_insights_by_category

Requirements: 3.3, 4.3, 4.4
"""
import logging
from typing import List

from sqlalchemy import text

from app.models.semantic_memory import (
    MemoryType,
    SemanticMemorySearchResult,
)

logger = logging.getLogger(__name__)


class InsightRepositoryMixin:
    """
    Mixin class providing insight operations for SemanticMemoryRepository.

    Requires the host class to provide:
    - self._ensure_initialized() -> None
    - self._session_factory -> sessionmaker
    - self.TABLE_NAME -> str
    """

    def get_user_insights(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[SemanticMemorySearchResult]:
        """
        Get all insights for user (for API endpoint).

        Returns all INSIGHT type entries.

        Args:
            user_id: User ID
            limit: Maximum number of insights

        Returns:
            List of all user insights ordered by created_at DESC

        **Validates: Requirements 4.3, 4.4**
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                query = text(f"""
                    SELECT
                        id,
                        content,
                        memory_type,
                        importance,
                        metadata,
                        created_at,
                        updated_at,
                        1.0 AS similarity
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND memory_type = :memory_type
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)

                result = session.execute(query, {
                    "user_id": user_id,
                    "memory_type": MemoryType.INSIGHT.value if hasattr(MemoryType, 'INSIGHT') else 'insight',
                    "limit": limit
                })

                rows = result.fetchall()

                insights = []
                for row in rows:
                    insights.append(SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType.INSIGHT if hasattr(MemoryType, 'INSIGHT') else MemoryType.USER_FACT,
                        importance=row.importance,
                        similarity=1.0,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    ))

                logger.debug("Retrieved %d insights for user %s", len(insights), user_id)
                return insights

        except Exception as e:
            logger.error("Failed to get user insights: %s", e)
            return []

    def delete_user_insights(self, user_id: str) -> int:
        """
        Delete all INSIGHT type memories for a user.

        Used during consolidation to replace old insights with consolidated ones.

        Args:
            user_id: User ID

        Returns:
            Number of deleted insights
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                query = text(f"""
                    DELETE FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND memory_type = :memory_type
                    RETURNING id
                """)

                result = session.execute(query, {
                    "user_id": user_id,
                    "memory_type": MemoryType.INSIGHT.value if hasattr(MemoryType, 'INSIGHT') else 'insight'
                })

                deleted = len(result.fetchall())
                session.commit()

                logger.info("Deleted %d insights for user %s", deleted, user_id)
                return deleted

        except Exception as e:
            logger.error("Failed to delete user insights: %s", e)
            return 0

    def get_insights_by_category(
        self,
        user_id: str,
        category: str,
        limit: int = 10
    ) -> List[SemanticMemorySearchResult]:
        """
        Get insights filtered by category.

        Args:
            user_id: User ID
            category: Insight category (learning_style, knowledge_gap, etc.)
            limit: Maximum number of results

        Returns:
            List of insights for the category
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                query = text(f"""
                    SELECT
                        id,
                        content,
                        memory_type,
                        importance,
                        metadata,
                        created_at,
                        last_accessed,
                        1.0 AS similarity
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND metadata->>'insight_category' = :category
                    ORDER BY last_accessed DESC NULLS LAST, created_at DESC
                    LIMIT :limit
                """)

                result = session.execute(query, {
                    "user_id": user_id,
                    "category": category,
                    "limit": limit
                })

                rows = result.fetchall()

                insights = []
                for row in rows:
                    insights.append(SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type) if row.memory_type in [m.value for m in MemoryType] else MemoryType.USER_FACT,
                        importance=row.importance,
                        similarity=1.0,
                        metadata=row.metadata or {},
                        created_at=row.created_at
                    ))

                return insights

        except Exception as e:
            logger.error("Failed to get insights by category: %s", e)
            return []
