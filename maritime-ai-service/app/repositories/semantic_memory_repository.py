"""
Semantic Memory Repository for Wiii v0.3
CHI THI KY THUAT SO 06

Repository for semantic memory operations with pgvector on Supabase.
Facade class that delegates to specialized mixin modules:
- FactRepositoryMixin: Fact CRUD, semantic triples, deduplication
- InsightRepositoryMixin: Insight retrieval and management
- VectorMemoryRepositoryMixin: Vector similarity search

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
"""
import json
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text

from app.models.semantic_memory import (
    MemoryType,
    SemanticMemory,
    SemanticMemoryCreate,
)

# Import mixin modules
from app.repositories.fact_repository import FactRepositoryMixin
from app.repositories.insight_repository import InsightRepositoryMixin
from app.repositories.vector_memory_repository import VectorMemoryRepositoryMixin

logger = logging.getLogger(__name__)


class SemanticMemoryRepository(
    FactRepositoryMixin,
    InsightRepositoryMixin,
    VectorMemoryRepositoryMixin,
):
    """
    Repository for semantic memory CRUD operations with pgvector.

    Uses Supabase PostgreSQL with pgvector extension for vector similarity search.
    Implements cosine similarity search with HNSW index.

    Delegates specialized operations to mixin modules:
    - FactRepositoryMixin: Fact CRUD, semantic triples, deduplication
    - InsightRepositoryMixin: Insight retrieval and management
    - VectorMemoryRepositoryMixin: Vector similarity search

    Requirements: 2.1, 2.2, 2.3, 2.4
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
        """Lazy initialization using SHARED database engine."""
        if not self._initialized:
            try:
                # Use SHARED engine to minimize connections (Supabase Free Tier)
                from app.core.database import get_shared_engine, get_shared_session_factory

                self._engine = get_shared_engine()
                self._session_factory = get_shared_session_factory()
                self._initialized = True
                logger.info("SemanticMemoryRepository using SHARED database engine")
            except Exception as e:
                logger.error("Failed to initialize SemanticMemoryRepository: %s", e)
                raise

    def _format_embedding(self, embedding: List[float]) -> str:
        """Format embedding list as pgvector string."""
        if embedding is None or len(embedding) == 0:
            # Return empty vector array - pgvector will handle as null or empty
            logger.warning("Received None or empty embedding, using empty vector")
            return "[]"
        return f"[{','.join(str(x) for x in embedding)}]"

    def save_memory(
        self,
        memory: SemanticMemoryCreate
    ) -> Optional[SemanticMemory]:
        """
        Save a new semantic memory to the database.

        Args:
            memory: SemanticMemoryCreate object with content and embedding

        Returns:
            Created SemanticMemory object or None on failure

        Requirements: 2.1
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                embedding_str = self._format_embedding(memory.embedding)
                metadata_json = json.dumps(memory.metadata)

                # Sprint 160: Include organization_id for multi-tenant isolation
                from app.core.org_filter import get_effective_org_id
                eff_org_id = get_effective_org_id()

                query = text(f"""
                    INSERT INTO {self.TABLE_NAME}
                    (user_id, content, embedding, memory_type, importance, metadata, session_id, organization_id)
                    VALUES
                    (:user_id, :content, CAST(:embedding AS vector), :memory_type, :importance, CAST(:metadata AS jsonb), :session_id, :org_id)
                    RETURNING id, user_id, content, memory_type, importance, metadata, session_id, created_at, updated_at
                """)

                result = session.execute(query, {
                    "user_id": memory.user_id,
                    "content": memory.content,
                    "embedding": embedding_str,
                    "memory_type": memory.memory_type.value,
                    "importance": memory.importance,
                    "metadata": metadata_json,
                    "session_id": memory.session_id,
                    "org_id": eff_org_id,
                })

                row = result.fetchone()
                session.commit()

                if row:
                    logger.debug("Saved memory %s for user %s", row.id, memory.user_id)
                    return SemanticMemory(
                        id=row.id,
                        user_id=row.user_id,
                        content=row.content,
                        embedding=memory.embedding,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        metadata=row.metadata or {},
                        session_id=row.session_id,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                return None

        except Exception as e:
            logger.error("Failed to save memory: %s", e)
            return None

    def get_by_id(
        self,
        memory_id: UUID,
        user_id: str
    ) -> Optional[SemanticMemory]:
        """
        Get a specific memory by ID.

        Args:
            memory_id: Memory UUID
            user_id: User ID (for RLS verification)

        Returns:
            SemanticMemory or None if not found
        """
        self._ensure_initialized()

        # Org-scoped filtering (audit fix: was missing)
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                query = text(f"""
                    SELECT
                        id, user_id, content, memory_type, importance,
                        metadata, session_id, created_at, updated_at
                    FROM {self.TABLE_NAME}
                    WHERE id = :memory_id AND user_id = :user_id
                    {org_filter}
                """)

                params = {
                    "memory_id": str(memory_id),
                    "user_id": user_id,
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)

                row = result.fetchone()

                if row:
                    return SemanticMemory(
                        id=row.id,
                        user_id=row.user_id,
                        content=row.content,
                        embedding=[],  # Don't fetch embedding for simple get
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        metadata=row.metadata or {},
                        session_id=row.session_id,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                return None

        except Exception as e:
            logger.error("Failed to get memory by ID: %s", e)
            return None

    def delete_by_session(
        self,
        user_id: str,
        session_id: str
    ) -> int:
        """
        Delete all memories for a session (used after summarization).

        Args:
            user_id: User ID
            session_id: Session ID

        Returns:
            Number of deleted memories
        """
        self._ensure_initialized()

        # Org-scoped filtering (audit fix: was missing)
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                query = text(f"""
                    DELETE FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND session_id = :session_id
                      AND memory_type = :memory_type
                      {org_filter}
                    RETURNING id
                """)

                params = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "memory_type": MemoryType.MESSAGE.value,
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)

                deleted = len(result.fetchall())
                session.commit()

                logger.info("Deleted %d messages for session %s", deleted, session_id)
                return deleted

        except Exception as e:
            logger.error("Failed to delete session memories: %s", e)
            return 0

    def count_user_memories(
        self,
        user_id: str,
        memory_type: Optional[MemoryType] = None
    ) -> int:
        """
        Count memories for a user.

        Args:
            user_id: User ID
            memory_type: Optional filter by type

        Returns:
            Count of memories
        """
        self._ensure_initialized()

        # Org-scoped filtering (audit fix: was missing)
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                type_filter = ""
                params = {"user_id": user_id}

                if memory_type:
                    type_filter = "AND memory_type = :memory_type"
                    params["memory_type"] = memory_type.value

                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                query = text(f"""
                    SELECT COUNT(*) as count
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id {type_filter}
                    {org_filter}
                """)

                result = session.execute(query, params)
                row = result.fetchone()

                return row.count if row else 0

        except Exception as e:
            logger.error("Failed to count memories: %s", e)
            return 0

    def is_available(self) -> bool:
        """
        Check if the repository is available and connected.

        Returns:
            True if database is accessible
        """
        try:
            self._ensure_initialized()
            with self._session_factory() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.warning("SemanticMemoryRepository not available: %s", e)
            return False

    # ========== v0.5 Methods (CHI THI 23 CAI TIEN - Insight Engine) ==========

    def update_last_accessed(self, memory_id: UUID, user_id: Optional[str] = None) -> bool:
        """
        Update last_accessed timestamp and increment access_count for a memory.

        Sprint 122 (Bug F2): Also increments metadata.access_count.
        The Ebbinghaus decay formula uses access_count for reinforcement:
        retention(t) = e^(-t / (stability * (1 + access_count * 0.3)))
        Without incrementing, the reinforcement term was always 0.

        Args:
            memory_id: UUID of the memory
            user_id: Optional user_id for defense-in-depth ownership check

        Returns:
            True if update successful

        **Validates: Requirements 3.3**
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                # Sprint 122: Increment access_count in metadata alongside last_accessed
                if user_id:
                    query = text(f"""
                        UPDATE {self.TABLE_NAME}
                        SET last_accessed = NOW(),
                            metadata = jsonb_set(
                                COALESCE(metadata, '{{}}'::jsonb),
                                '{{access_count}}',
                                (COALESCE((metadata->>'access_count')::int, 0) + 1)::text::jsonb
                            )
                        WHERE id = :memory_id AND user_id = :user_id
                        RETURNING id
                    """)
                    params = {"memory_id": str(memory_id), "user_id": user_id}
                else:
                    query = text(f"""
                        UPDATE {self.TABLE_NAME}
                        SET last_accessed = NOW(),
                            metadata = jsonb_set(
                                COALESCE(metadata, '{{}}'::jsonb),
                                '{{access_count}}',
                                (COALESCE((metadata->>'access_count')::int, 0) + 1)::text::jsonb
                            )
                        WHERE id = :memory_id
                        RETURNING id
                    """)
                    params = {"memory_id": str(memory_id)}

                result = session.execute(query, params)
                row = result.fetchone()
                session.commit()

                return row is not None

        except Exception as e:
            logger.error("Failed to update last_accessed: %s", e)
            return False

    def get_memories_by_type(
        self,
        user_id: str,
        memory_type: MemoryType,
        limit: int = 1000,
        session_id: Optional[str] = None,
    ) -> List["SemanticMemorySearchResult"]:
        """
        Get memories filtered by type WITHOUT cosine similarity.

        Sprint 27: Replaces the anti-pattern of using search_similar()
        with a zero-vector ([0.0]*768), which caused NaN in pgvector
        cosine distance and silently returned empty results.

        Args:
            user_id: User ID
            memory_type: Type of memory to retrieve
            limit: Maximum results
            session_id: Optional session filter

        Returns:
            List of matching memories ordered by created_at DESC
        """
        from app.models.semantic_memory import SemanticMemorySearchResult

        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                session_filter = ""
                params = {
                    "user_id": user_id,
                    "memory_type": memory_type.value,
                    "limit": limit,
                }

                if session_id:
                    session_filter = "AND session_id = :session_id"
                    params["session_id"] = session_id

                # Sprint 160: Org-scoped filtering
                from app.core.org_filter import get_effective_org_id, org_where_clause
                eff_org_id = get_effective_org_id()
                org_filter = org_where_clause(eff_org_id)
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                query = text(f"""
                    SELECT
                        id,
                        content,
                        memory_type,
                        importance,
                        metadata,
                        created_at,
                        1.0 AS similarity
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND memory_type = :memory_type
                      {session_filter}
                      {org_filter}
                    ORDER BY created_at DESC
                    LIMIT :limit
                """)

                result = session.execute(query, params)
                rows = result.fetchall()

                memories = []
                for row in rows:
                    memories.append(SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=1.0,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                    ))

                return memories

        except Exception as e:
            logger.error("Failed to get memories by type: %s", e)
            return []

    def delete_memories_by_keyword(
        self,
        user_id: str,
        keyword: str
    ) -> int:
        """
        Delete memories matching a keyword in content for a user.

        Sprint 26: Enables tool_forget to actually delete from PostgreSQL.

        Args:
            user_id: User ID
            keyword: Keyword to match in content (case-insensitive)

        Returns:
            Number of memories deleted
        """
        self._ensure_initialized()

        # Org-scoped filtering (audit fix: was missing)
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                query = text(f"""
                    DELETE FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND LOWER(content) LIKE LOWER(:keyword_pattern)
                      {org_filter}
                    RETURNING id
                """)

                params = {
                    "user_id": user_id,
                    "keyword_pattern": f"%{keyword}%",
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)
                deleted_ids = result.fetchall()
                session.commit()

                deleted_count = len(deleted_ids)
                if deleted_count > 0:
                    logger.info(
                        "Deleted %d memories matching '%s' "
                        "for user %s", deleted_count, keyword, user_id
                    )
                return deleted_count

        except Exception as e:
            logger.error("Failed to delete memories by keyword: %s", e)
            return 0

    def delete_all_user_memories(self, user_id: str) -> int:
        """
        Delete ALL memories for a user (factory reset).

        Sprint 26: Enables tool_clear_all_memories to actually clear PostgreSQL.

        Args:
            user_id: User ID

        Returns:
            Number of memories deleted
        """
        self._ensure_initialized()

        # Org-scoped filtering (audit fix: was missing)
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                query = text(f"""
                    DELETE FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                    {org_filter}
                    RETURNING id
                """)

                params = {"user_id": user_id}
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)
                deleted_ids = result.fetchall()
                session.commit()

                deleted_count = len(deleted_ids)
                logger.info("Deleted ALL %d memories for user %s", deleted_count, user_id)
                return deleted_count

        except Exception as e:
            logger.error("Failed to delete all memories for user %s: %s", user_id, e)
            return 0

    def delete_oldest_insights(
        self,
        user_id: str,
        count: int
    ) -> int:
        """
        Delete N oldest INSIGHT entries for user (FIFO eviction).

        Sprint 26: Fix for InsightProvider._fifo_eviction which was
        incorrectly calling delete_oldest_facts (USER_FACT type).

        Args:
            user_id: User ID
            count: Number of oldest insights to delete

        Returns:
            Number of insights actually deleted
        """
        self._ensure_initialized()

        if count <= 0:
            return 0

        # Org-scoped filtering (audit fix: was missing)
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                query = text(f"""
                    DELETE FROM {self.TABLE_NAME}
                    WHERE id IN (
                        SELECT id FROM {self.TABLE_NAME}
                        WHERE user_id = :user_id
                          AND memory_type = :memory_type
                          {org_filter}
                        ORDER BY created_at ASC
                        LIMIT :count
                    )
                    RETURNING id
                """)

                params = {
                    "user_id": user_id,
                    "memory_type": MemoryType.INSIGHT.value,
                    "count": count,
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)

                deleted_ids = result.fetchall()
                session.commit()

                deleted_count = len(deleted_ids)
                if deleted_count > 0:
                    logger.info(
                        "Deleted %d oldest insights for user "
                        "%s (FIFO eviction)", deleted_count, user_id
                    )
                return deleted_count

        except Exception as e:
            logger.error("Failed to delete oldest insights: %s", e)
            return 0

    def delete_memory(self, user_id: str, memory_id: str) -> bool:
        """
        Delete a specific memory by ID.

        Args:
            user_id: User ID who owns the memory (for RLS verification)
            memory_id: UUID of the memory to delete

        Returns:
            True if deletion successful
        """
        self._ensure_initialized()

        # Org-scoped filtering (audit fix: was missing)
        from app.core.org_filter import get_effective_org_id, org_where_clause
        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                query = text(f"""
                    DELETE FROM {self.TABLE_NAME}
                    WHERE id = :memory_id AND user_id = :user_id
                    {org_filter}
                    RETURNING id
                """)

                params = {
                    "memory_id": str(memory_id),
                    "user_id": user_id,
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)
                row = result.fetchone()
                session.commit()

                return row is not None

        except Exception as e:
            logger.error("Failed to delete memory: %s", e)
            return False


    # ========== Sprint 79: Running Summary Persistence ==========

    def upsert_running_summary(self, session_id: str, summary: str) -> bool:
        """
        Upsert running summary for a session.

        Sprint 122 (Bug F1): Uses memory_type='running_summary' consistently.
        Previously used 'summary' with metadata content_type='running_summary',
        which was invisible to ConversationCompactor that queried 'running_summary'.

        Args:
            session_id: Session ID
            summary: Running summary text

        Returns:
            True if upsert successful
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                # Try update first
                update_query = text(f"""
                    UPDATE {self.TABLE_NAME}
                    SET content = :content, updated_at = NOW()
                    WHERE session_id = :session_id
                      AND memory_type = :memory_type
                    RETURNING id
                """)

                result = session.execute(update_query, {
                    "content": summary,
                    "session_id": session_id,
                    "memory_type": MemoryType.RUNNING_SUMMARY.value,
                })
                row = result.fetchone()

                if row:
                    session.commit()
                    return True

                # No existing row — insert new
                metadata = json.dumps({"content_type": "running_summary", "source": "repository"})
                insert_query = text(f"""
                    INSERT INTO {self.TABLE_NAME}
                    (user_id, content, embedding, memory_type, importance, metadata, session_id)
                    VALUES
                    ('__system__', :content, CAST(:embedding AS vector), :memory_type, :importance, CAST(:metadata AS jsonb), :session_id)
                    RETURNING id
                """)

                result = session.execute(insert_query, {
                    "content": summary,
                    "embedding": "[]",
                    "memory_type": MemoryType.RUNNING_SUMMARY.value,
                    "importance": 0.9,
                    "metadata": metadata,
                    "session_id": session_id,
                })
                session.commit()
                return result.fetchone() is not None

        except Exception as e:
            logger.error("Failed to upsert running summary: %s", e)
            return False

    def get_running_summary(self, session_id: str) -> Optional[str]:
        """
        Load running summary for a session.

        Sprint 122 (Bug F1): Queries memory_type='running_summary' consistently.

        Args:
            session_id: Session ID

        Returns:
            Summary text or None if not found
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                query = text(f"""
                    SELECT content
                    FROM {self.TABLE_NAME}
                    WHERE session_id = :session_id
                      AND memory_type = :memory_type
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 1
                """)

                result = session.execute(query, {
                    "session_id": session_id,
                    "memory_type": MemoryType.RUNNING_SUMMARY.value,
                })
                row = result.fetchone()
                return row.content if row else None

        except Exception as e:
            logger.error("Failed to get running summary: %s", e)
            return None

    def delete_running_summary(self, session_id: str) -> bool:
        """Delete running summary for a session. Sprint 122: Uses RUNNING_SUMMARY type."""
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                query = text(f"""
                    DELETE FROM {self.TABLE_NAME}
                    WHERE session_id = :session_id
                      AND memory_type = :memory_type
                    RETURNING id
                """)

                result = session.execute(query, {
                    "session_id": session_id,
                    "memory_type": MemoryType.RUNNING_SUMMARY.value,
                })
                session.commit()
                return result.fetchone() is not None

        except Exception as e:
            logger.error("Failed to delete running summary: %s", e)
            return False


# Factory function
def get_semantic_memory_repository() -> SemanticMemoryRepository:
    """Get a configured SemanticMemoryRepository instance."""
    return SemanticMemoryRepository()
