"""
Fact Repository Mixin for Semantic Memory
Extracted from semantic_memory_repository.py for modularity.

Contains fact CRUD operations:
- get_user_facts, get_all_user_facts
- find_fact_by_type, find_similar_fact_by_embedding
- update_fact, update_metadata_only
- delete_oldest_facts
- Semantic Triple operations (save_triple, find_by_predicate, upsert_triple)

Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4
"""
import json
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text

from app.models.semantic_memory import (
    MemoryType,
    Predicate,
    SemanticMemory,
    SemanticMemoryCreate,
    SemanticMemorySearchResult,
    SemanticTriple,
)

logger = logging.getLogger(__name__)


class FactRepositoryMixin:
    """
    Mixin class providing fact CRUD operations for SemanticMemoryRepository.

    Requires the host class to provide:
    - self._ensure_initialized() -> None
    - self._session_factory -> sessionmaker
    - self._format_embedding(embedding) -> str
    - self.TABLE_NAME -> str
    - self.save_memory(memory) -> Optional[SemanticMemory]
    """

    def get_user_facts(
        self,
        user_id: str,
        limit: int = 20,
        deduplicate: bool = True,
        apply_decay: bool = True,
    ) -> List[SemanticMemorySearchResult]:
        """
        Get all user facts for personalization across ALL sessions.

        Cross-session Memory Persistence (v0.2.1):
        - Queries by user_id ONLY (no session_id filter)
        - Deduplicates facts by fact_type (keeps most recent)
        - Applies importance decay (FadeMem Ebbinghaus curve)
        - Orders by effective importance DESC

        Args:
            user_id: User ID
            limit: Maximum number of facts to return
            deduplicate: If True, keep only most recent fact per fact_type
            apply_decay: If True, apply time-based importance decay

        Returns:
            List of user facts ordered by effective importance
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                # Sprint 160: Org-scoped filtering
                from app.core.org_filter import get_effective_org_id, org_where_clause
                eff_org_id = get_effective_org_id()
                org_filter = org_where_clause(eff_org_id)

                if deduplicate:
                    # Sprint 85: SQL-level dedup with DISTINCT ON — reduces network
                    # transfer by ~66% vs fetching 3x rows and deduplicating in Python
                    query = text(f"""
                        SELECT DISTINCT ON (metadata->>'fact_type')
                            id,
                            content,
                            memory_type,
                            importance,
                            metadata,
                            created_at,
                            updated_at,
                            last_accessed,
                            1.0 AS similarity
                        FROM {self.TABLE_NAME}
                        WHERE user_id = :user_id
                          AND memory_type = :memory_type
                          {org_filter}
                        ORDER BY metadata->>'fact_type', created_at DESC
                    """)
                else:
                    query = text(f"""
                        SELECT
                            id,
                            content,
                            memory_type,
                            importance,
                            metadata,
                            created_at,
                            updated_at,
                            last_accessed,
                            1.0 AS similarity
                        FROM {self.TABLE_NAME}
                        WHERE user_id = :user_id
                          AND memory_type = :memory_type
                          {org_filter}
                        ORDER BY importance DESC, created_at DESC
                        LIMIT :limit
                    """)

                params = {
                    "user_id": user_id,
                    "memory_type": MemoryType.USER_FACT.value,
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id
                if not deduplicate:
                    params["limit"] = limit

                result = session.execute(query, params)

                rows = result.fetchall()

                facts = []
                for row in rows:
                    facts.append(SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=1.0,
                        metadata=row.metadata or {},
                        created_at=row.created_at,
                        updated_at=getattr(row, "updated_at", None),
                    ))

                # Sprint 85: SQL DISTINCT ON handles deduplication — skip Python pass

                # Apply importance decay (FadeMem)
                if apply_decay and facts:
                    facts = self._apply_importance_decay(facts)

                # Apply final limit after deduplication + decay sort
                facts = facts[:limit]

                logger.debug("Found %d user facts for user %s (deduplicate=%s, decay=%s)", len(facts), user_id, deduplicate, apply_decay)
                return facts

        except Exception as e:
            logger.error("Failed to get user facts: %s", e)
            return []

    def _apply_importance_decay(
        self,
        facts: List[SemanticMemorySearchResult],
    ) -> List[SemanticMemorySearchResult]:
        """
        Apply FadeMem Ebbinghaus decay to fact importance and re-sort.

        Identity facts (name, age) never decay. Volatile facts (emotion,
        recent_topic) decay within hours. Re-sorts by effective importance.
        """
        try:
            from app.engine.semantic_memory.importance_decay import (
                calculate_effective_importance_from_timestamps,
            )
        except ImportError:
            return facts

        for fact in facts:
            fact_type = (fact.metadata or {}).get("fact_type", "unknown")
            access_count = (fact.metadata or {}).get("access_count", 0)
            last_accessed = (fact.metadata or {}).get("last_accessed")

            effective = calculate_effective_importance_from_timestamps(
                base_importance=fact.importance,
                fact_type=fact_type,
                last_accessed=last_accessed,
                created_at=fact.created_at,
                access_count=access_count,
            )
            # Store effective importance for sorting (override similarity field)
            fact.similarity = effective

        # Sort by effective importance (stored in similarity) descending
        facts.sort(key=lambda f: f.similarity, reverse=True)
        return facts

    def search_relevant_facts(
        self,
        user_id: str,
        query_embedding: List[float],
        limit: int = 5,
        min_similarity: float = 0.3,
    ) -> List[SemanticMemorySearchResult]:
        """
        Search user facts by semantic similarity to query (Sprint 137).

        Uses HNSW index on embedding column for efficient vector search.
        Combines importance, cosine similarity, and recency for scoring.

        Formula: alpha * effective_importance + beta * similarity + gamma * recency
        Where alpha=0.3, beta=0.5, gamma=0.2 (configurable in settings).

        Args:
            user_id: User ID
            query_embedding: Query embedding vector (768-dim)
            limit: Maximum facts to return
            min_similarity: Minimum cosine similarity threshold

        Returns:
            List of facts sorted by combined score (descending)
        """
        self._ensure_initialized()

        try:
            from app.core.config import settings
            alpha = settings.fact_retrieval_alpha
            beta = settings.fact_retrieval_beta
            gamma = settings.fact_retrieval_gamma
        except Exception:
            alpha, beta, gamma = 0.3, 0.5, 0.2

        try:
            with self._session_factory() as session:
                # Sprint 160: Org-scoped filtering
                from app.core.org_filter import get_effective_org_id, org_where_clause
                eff_org_id = get_effective_org_id()
                org_filter = org_where_clause(eff_org_id)

                query = text(f"""
                    SELECT
                        id,
                        content,
                        memory_type,
                        importance,
                        metadata,
                        created_at,
                        updated_at,
                        last_accessed,
                        1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND memory_type = :memory_type
                      AND embedding IS NOT NULL
                      AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_similarity
                      {org_filter}
                    ORDER BY similarity DESC
                    LIMIT :fetch_limit
                """)

                search_params = {
                    "user_id": user_id,
                    "memory_type": MemoryType.USER_FACT.value,
                    "embedding": str(query_embedding),
                    "min_similarity": min_similarity,
                    "fetch_limit": limit * 3,  # Fetch extra for re-ranking
                }
                if eff_org_id is not None:
                    search_params["org_id"] = eff_org_id

                result = session.execute(query, search_params)

                rows = result.fetchall()

                if not rows:
                    logger.debug("No similar facts found for user %s", user_id)
                    return []

                # Build results with combined scoring
                facts = []
                now = None
                try:
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                except Exception:
                    pass

                for row in rows:
                    similarity = float(row.similarity)
                    meta = row.metadata or {}
                    fact_type = meta.get("fact_type", "unknown")
                    access_count = meta.get("access_count", 0)

                    # Calculate effective importance (with decay)
                    effective_importance = float(row.importance)
                    try:
                        from app.engine.semantic_memory.importance_decay import (
                            calculate_effective_importance_from_timestamps,
                        )
                        effective_importance = calculate_effective_importance_from_timestamps(
                            base_importance=row.importance,
                            fact_type=fact_type,
                            last_accessed=meta.get("last_accessed"),
                            created_at=row.created_at,
                            access_count=access_count,
                        )
                    except ImportError:
                        pass

                    # Calculate recency score (0-1, higher = more recent)
                    recency_score = 0.5  # default
                    if now and row.created_at:
                        try:
                            created = row.created_at
                            if created.tzinfo is None:
                                from datetime import timezone
                                created = created.replace(tzinfo=timezone.utc)
                            hours_ago = (now - created).total_seconds() / 3600
                            # Exponential decay: 0.995^hours (Stanford pattern)
                            recency_score = 0.995 ** min(hours_ago, 2000)
                        except Exception:
                            recency_score = 0.5

                    # Combined score
                    combined = (
                        alpha * effective_importance
                        + beta * similarity
                        + gamma * recency_score
                    )

                    fact = SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=combined,  # Store combined score in similarity field
                        metadata=meta,
                        created_at=row.created_at,
                        updated_at=getattr(row, "updated_at", None),
                    )
                    facts.append(fact)

                # Sort by combined score descending
                facts.sort(key=lambda f: f.similarity, reverse=True)
                facts = facts[:limit]

                logger.debug(
                    "Semantic fact search returned %d facts for user %s "
                    "(alpha=%.1f, beta=%.1f, gamma=%.1f)",
                    len(facts), user_id, alpha, beta, gamma,
                )
                return facts

        except Exception as e:
            logger.error("Semantic fact search failed: %s", e)
            return []

    def get_all_user_facts(
        self,
        user_id: str
    ) -> List[SemanticMemorySearchResult]:
        """
        Get all facts for user (for API endpoint).

        Returns all USER_FACT entries without deduplication.

        Args:
            user_id: User ID

        Returns:
            List of all user facts ordered by created_at DESC

        **Validates: Requirements 3.1**
        """
        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                # Sprint 160: Org-scoped filtering
                from app.core.org_filter import get_effective_org_id, org_where_clause
                eff_org_id = get_effective_org_id()
                org_filter = org_where_clause(eff_org_id)

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
                      {org_filter}
                    ORDER BY created_at DESC
                    LIMIT 500
                """)

                get_all_params = {
                    "user_id": user_id,
                    "memory_type": MemoryType.USER_FACT.value,
                }
                if eff_org_id is not None:
                    get_all_params["org_id"] = eff_org_id

                result = session.execute(query, get_all_params)

                rows = result.fetchall()

                facts = []
                for row in rows:
                    facts.append(SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=1.0,
                        metadata=row.metadata or {},
                        created_at=row.created_at
                    ))

                logger.debug("Retrieved %d total facts for user %s", len(facts), user_id)
                return facts

        except Exception as e:
            logger.error("Failed to get all user facts: %s", e)
            return []

    # ========== v0.4 Methods (CHI THI 23) ==========

    def find_fact_by_type(
        self,
        user_id: str,
        fact_type: str
    ) -> Optional[SemanticMemorySearchResult]:
        """
        Find existing fact by user_id and fact_type.

        Used for upsert logic - check if fact of same type exists.

        Args:
            user_id: User ID
            fact_type: Type of fact (name, role, level, etc.)

        Returns:
            SemanticMemorySearchResult or None if not found

        **Validates: Requirements 2.1, 2.2**
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
                      AND metadata->>'fact_type' = :fact_type
                      {org_filter}
                    ORDER BY created_at DESC
                    LIMIT 1
                """)

                params = {
                    "user_id": user_id,
                    "memory_type": MemoryType.USER_FACT.value,
                    "fact_type": fact_type,
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)

                row = result.fetchone()

                if row:
                    return SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=1.0,
                        metadata=row.metadata or {},
                        created_at=row.created_at
                    )
                return None

        except Exception as e:
            logger.error("Failed to find fact by type: %s", e)
            return None

    def find_similar_fact_by_embedding(
        self,
        user_id: str,
        embedding: List[float],
        similarity_threshold: float = 0.90,
        memory_type: MemoryType = MemoryType.USER_FACT
    ) -> Optional[SemanticMemorySearchResult]:
        """
        SOTA: Find semantically similar fact using embedding cosine similarity.

        This enables detecting duplicate facts even when fact_type differs
        but content is semantically the same.

        Args:
            user_id: User ID
            embedding: Query embedding vector
            similarity_threshold: Minimum similarity (default: 0.90 for facts)
            memory_type: Type of memory to search

        Returns:
            SemanticMemorySearchResult if found, None otherwise

        **SOTA Enhancement: Semantic duplicate detection**
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
                        1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND memory_type = :memory_type
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:embedding AS vector)
                    LIMIT 1
                """)

                result = session.execute(query, {
                    "user_id": user_id,
                    "memory_type": memory_type.value,
                    "embedding": str(embedding)
                })

                row = result.fetchone()

                if row and row.similarity >= similarity_threshold:
                    logger.debug(
                        "Found similar fact with similarity %.3f "
                        "(threshold: %s)", row.similarity, similarity_threshold
                    )
                    return SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=row.similarity,
                        metadata=row.metadata or {},
                        created_at=row.created_at
                    )
                return None

        except Exception as e:
            logger.error("Failed to find similar fact by embedding: %s", e)
            return None

    def update_fact(
        self,
        fact_id: UUID,
        content: str,
        embedding: List[float],
        metadata: dict,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Full update of fact content, embedding, and metadata.

        SOTA Pattern: Explicit API - requires all fields for full update.
        For metadata-only updates (preserving embedding), use update_metadata_only().

        Args:
            fact_id: UUID of the fact to update
            content: New content (required)
            embedding: New embedding vector (REQUIRED, must be non-empty)
            metadata: New metadata (required)
            user_id: Optional user_id for defense-in-depth ownership check

        Returns:
            True if update successful

        Raises:
            ValueError: If embedding is None or empty

        **Validates: Requirements 2.2, 2.4**
        """
        # SOTA: Explicit validation - fail fast with clear error
        if embedding is None or len(embedding) == 0:
            raise ValueError(
                "embedding is required for update_fact(). "
                "Use update_metadata_only() for metadata-only updates."
            )

        self._ensure_initialized()

        try:
            with self._session_factory() as session:
                embedding_str = self._format_embedding(embedding)
                metadata_json = json.dumps(metadata)

                # Sprint 121: Defense-in-depth — include user_id in WHERE if provided
                if user_id:
                    query = text(f"""
                        UPDATE {self.TABLE_NAME}
                        SET content = :content,
                            embedding = CAST(:embedding AS vector),
                            metadata = CAST(:metadata AS jsonb),
                            updated_at = NOW()
                        WHERE id = :fact_id AND user_id = :user_id
                        RETURNING id
                    """)
                    params = {
                        "fact_id": str(fact_id),
                        "user_id": user_id,
                        "content": content,
                        "embedding": embedding_str,
                        "metadata": metadata_json,
                    }
                else:
                    query = text(f"""
                        UPDATE {self.TABLE_NAME}
                        SET content = :content,
                            embedding = CAST(:embedding AS vector),
                            metadata = CAST(:metadata AS jsonb),
                            updated_at = NOW()
                        WHERE id = :fact_id
                        RETURNING id
                    """)
                    params = {
                        "fact_id": str(fact_id),
                        "content": content,
                        "embedding": embedding_str,
                        "metadata": metadata_json,
                    }

                result = session.execute(query, params)

                row = result.fetchone()
                session.commit()

                if row:
                    logger.debug("Updated fact %s", fact_id)
                    return True
                return False

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error("Failed to update fact: %s", e)
            return False

    def update_metadata_only(
        self,
        fact_id: UUID,
        metadata: dict,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Update ONLY metadata, preserving content and embedding.

        SOTA Pattern: Explicit API for partial updates.
        Use this when merging insights or updating confidence without
        re-generating embeddings.

        Args:
            fact_id: UUID of the fact to update
            metadata: New metadata to set (will replace existing metadata)
            user_id: Optional user_id for defense-in-depth ownership check

        Returns:
            True if update successful

        **Feature: SOTA-explicit-api**
        """
        self._ensure_initialized()

        # BUGFIX: Validate fact_id to prevent psycopg2.errors.InvalidTextRepresentation
        # This can happen when merging insights with existing_fact that has no valid id
        if fact_id is None or str(fact_id) in ('None', '', 'null'):
            logger.warning("[BUGFIX] Invalid fact_id: %s, skipping metadata update", fact_id)
            return False

        try:
            with self._session_factory() as session:
                metadata_json = json.dumps(metadata)

                # Sprint 121: Defense-in-depth — include user_id in WHERE if provided
                if user_id:
                    query = text(f"""
                        UPDATE {self.TABLE_NAME}
                        SET metadata = CAST(:metadata AS jsonb),
                            updated_at = NOW()
                        WHERE id = :fact_id AND user_id = :user_id
                        RETURNING id
                    """)
                    params = {
                        "fact_id": str(fact_id),
                        "user_id": user_id,
                        "metadata": metadata_json,
                    }
                else:
                    query = text(f"""
                        UPDATE {self.TABLE_NAME}
                        SET metadata = CAST(:metadata AS jsonb),
                            updated_at = NOW()
                        WHERE id = :fact_id
                        RETURNING id
                    """)
                    params = {
                        "fact_id": str(fact_id),
                        "metadata": metadata_json,
                    }

                result = session.execute(query, params)

                row = result.fetchone()
                session.commit()

                if row:
                    logger.debug("Updated metadata for fact %s", fact_id)
                    return True
                return False

        except Exception as e:
            logger.error("Failed to update metadata: %s", e)
            return False

    def delete_oldest_facts(
        self,
        user_id: str,
        count: int
    ) -> int:
        """
        Delete N oldest USER_FACT entries for user (FIFO eviction).

        Used for memory capping - when user exceeds MAX_USER_FACTS.

        Args:
            user_id: User ID
            count: Number of oldest facts to delete

        Returns:
            Number of facts actually deleted

        **Validates: Requirements 1.2**
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
                # Delete oldest facts using subquery
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
                    "memory_type": MemoryType.USER_FACT.value,
                    "count": count,
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                result = session.execute(query, params)

                deleted_ids = result.fetchall()
                session.commit()

                deleted_count = len(deleted_ids)
                if deleted_count > 0:
                    logger.info("Deleted %d oldest facts for user %s (FIFO eviction)", deleted_count, user_id)

                return deleted_count

        except Exception as e:
            logger.error("Failed to delete oldest facts: %s", e)
            return 0

    # ========== Semantic Triples v1 (MemoriLabs Pattern) ==========

    def save_triple(
        self,
        triple: SemanticTriple,
        generate_embedding: bool = True
    ) -> Optional[SemanticMemory]:
        """
        Save a Semantic Triple to database.

        Converts triple to SemanticMemoryCreate format for storage.

        Args:
            triple: SemanticTriple to save
            generate_embedding: If True and no embedding, generate one

        Returns:
            Created SemanticMemory or None on failure

        Feature: semantic-triples-v1
        """
        self._ensure_initialized()

        try:
            # If no embedding, try to generate one
            embedding = triple.embedding
            if not embedding and generate_embedding:
                try:
                    from app.engine.semantic_memory.embeddings import get_embedding_generator
                    generator = get_embedding_generator()
                    if generator.is_available():
                        embedding = generator.generate(triple.object)
                except Exception as e:
                    logger.warning("Failed to generate embedding for triple: %s", e)
                    embedding = []

            # Convert triple to SemanticMemoryCreate
            memory = SemanticMemoryCreate(
                user_id=triple.subject,
                content=triple.to_content(),
                embedding=embedding,
                memory_type=MemoryType.USER_FACT,
                importance=triple.confidence,
                metadata=triple.to_metadata(),
                session_id=None  # Triples are cross-session
            )

            return self.save_memory(memory)

        except Exception as e:
            logger.error("Failed to save triple: %s", e)
            return None

    def find_by_predicate(
        self,
        user_id: str,
        predicate: Predicate
    ) -> Optional[SemanticMemorySearchResult]:
        """
        Find existing triple by user_id and predicate.

        Used for upsert logic - check if triple with same predicate exists.

        Args:
            user_id: User ID (subject)
            predicate: Predicate type

        Returns:
            SemanticMemorySearchResult or None if not found

        Feature: semantic-triples-v1
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
                        1.0 AS similarity
                    FROM {self.TABLE_NAME}
                    WHERE user_id = :user_id
                      AND memory_type = :memory_type
                      AND (
                          metadata->>'predicate' = :predicate
                          OR metadata->>'fact_type' = :fact_type
                      )
                    ORDER BY created_at DESC
                    LIMIT 1
                """)

                # Map predicate to fact_type for backward compatibility
                fact_type_map = {
                    Predicate.HAS_NAME: "name",
                    Predicate.HAS_ROLE: "role",
                    Predicate.HAS_LEVEL: "level",
                    Predicate.HAS_GOAL: "goal",
                    Predicate.PREFERS: "preference",
                    Predicate.WEAK_AT: "weakness",
                }

                result = session.execute(query, {
                    "user_id": user_id,
                    "memory_type": MemoryType.USER_FACT.value,
                    "predicate": predicate.value,
                    "fact_type": fact_type_map.get(predicate, predicate.value)
                })

                row = result.fetchone()

                if row:
                    return SemanticMemorySearchResult(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        similarity=1.0,
                        metadata=row.metadata or {},
                        created_at=row.created_at
                    )
                return None

        except Exception as e:
            logger.error("Failed to find by predicate: %s", e)
            return None

    def update_memory_content(
        self,
        memory_id: UUID,
        user_id: str,
        new_content: str,
        new_metadata: dict
    ) -> Optional[SemanticMemory]:
        """
        Update content, embedding, and metadata of an existing memory.

        Re-generates embedding from new_content for semantic search accuracy.

        Args:
            memory_id: UUID of the memory to update
            user_id: User ID (for security validation)
            new_content: New content string
            new_metadata: New metadata dict

        Returns:
            Updated SemanticMemory or None on failure

        Feature: semantic-triples-v1
        """
        self._ensure_initialized()

        try:
            # Re-generate embedding from new content
            embedding = []
            try:
                from app.engine.semantic_memory.embeddings import get_embedding_generator
                generator = get_embedding_generator()
                if generator.is_available():
                    embedding = generator.generate(new_content)
            except Exception as e:
                logger.warning("Failed to generate embedding for update: %s", e)

            if not embedding:
                # Fallback: update without embedding change
                success = self.update_metadata_only(memory_id, new_metadata, user_id=user_id)
                if success:
                    return self.get_by_id(memory_id, user_id)
                return None

            embedding_str = self._format_embedding(embedding)
            metadata_json = json.dumps(new_metadata)

            with self._session_factory() as session:
                query = text(f"""
                    UPDATE {self.TABLE_NAME}
                    SET content = :content,
                        embedding = CAST(:embedding AS vector),
                        metadata = CAST(:metadata AS jsonb),
                        importance = :importance,
                        updated_at = NOW()
                    WHERE id = :memory_id AND user_id = :user_id
                    RETURNING id, user_id, content, memory_type, importance,
                              metadata, session_id, created_at, updated_at
                """)

                result = session.execute(query, {
                    "memory_id": str(memory_id),
                    "user_id": user_id,
                    "content": new_content,
                    "embedding": embedding_str,
                    "metadata": metadata_json,
                    "importance": new_metadata.get("confidence", 0.5)
                })

                row = result.fetchone()
                session.commit()

                if row:
                    logger.debug("Updated memory content %s", memory_id)
                    return SemanticMemory(
                        id=row.id,
                        user_id=row.user_id,
                        content=row.content,
                        embedding=embedding,
                        memory_type=MemoryType(row.memory_type),
                        importance=row.importance,
                        metadata=row.metadata or {},
                        session_id=row.session_id,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                return None

        except Exception as e:
            logger.error("Failed to update memory content %s: %s", memory_id, e)
            return None

    def upsert_triple(
        self,
        triple: SemanticTriple
    ) -> Optional[SemanticMemory]:
        """
        Upsert a Semantic Triple (insert or update if exists).

        Logic:
        1. Find existing triple by predicate
        2. If exists: update content and metadata
        3. If not exists: insert new triple

        Args:
            triple: SemanticTriple to upsert

        Returns:
            Created/Updated SemanticMemory or None on failure

        Feature: semantic-triples-v1
        """
        existing = self.find_by_predicate(triple.subject, triple.predicate)

        if existing:
            # Update existing
            return self.update_memory_content(
                memory_id=existing.id,
                user_id=triple.subject,
                new_content=triple.to_content(),
                new_metadata=triple.to_metadata()
            )
        else:
            # Insert new
            return self.save_triple(triple, generate_embedding=True)
