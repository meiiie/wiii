"""Semantic triple helpers for the fact repository."""

from __future__ import annotations

import json
import logging
from typing import Optional
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


class FactRepositoryTripleMixin:
    """Semantic triple operations for SemanticMemoryRepository."""

    def save_triple(
        self,
        triple: SemanticTriple,
        generate_embedding: bool = True,
    ) -> Optional[SemanticMemory]:
        self._ensure_initialized()

        try:
            embedding = triple.embedding
            if not embedding and generate_embedding:
                try:
                    from app.engine.semantic_memory.embeddings import get_embedding_generator

                    generator = get_embedding_generator()
                    if generator.is_available():
                        embedding = generator.generate(triple.object)
                except Exception as exc:
                    logger.warning("Failed to generate embedding for triple: %s", exc)
                    embedding = []

            memory = SemanticMemoryCreate(
                user_id=triple.subject,
                content=triple.to_content(),
                embedding=embedding,
                memory_type=MemoryType.USER_FACT,
                importance=triple.confidence,
                metadata=triple.to_metadata(),
                session_id=None,
            )
            return self.save_memory(memory)
        except Exception as exc:
            logger.error("Failed to save triple: %s", exc)
            return None

    def find_by_predicate(
        self,
        user_id: str,
        predicate: Predicate,
    ) -> Optional[SemanticMemorySearchResult]:
        self._ensure_initialized()

        from app.core.org_filter import get_effective_org_id, org_where_clause

        eff_org_id = get_effective_org_id()
        org_filter = org_where_clause(eff_org_id)

        try:
            with self._session_factory() as session:
                query = text(
                    f"""
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
                      {org_filter}
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                )

                fact_type_map = {
                    Predicate.HAS_NAME: "name",
                    Predicate.HAS_ROLE: "role",
                    Predicate.HAS_LEVEL: "level",
                    Predicate.HAS_GOAL: "goal",
                    Predicate.PREFERS: "preference",
                    Predicate.WEAK_AT: "weakness",
                }

                params = {
                    "user_id": user_id,
                    "memory_type": MemoryType.USER_FACT.value,
                    "predicate": predicate.value,
                    "fact_type": fact_type_map.get(predicate, predicate.value),
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                row = session.execute(query, params).fetchone()
                if not row:
                    return None
                return SemanticMemorySearchResult(
                    id=row.id,
                    content=row.content,
                    memory_type=MemoryType(row.memory_type),
                    importance=row.importance,
                    similarity=1.0,
                    metadata=row.metadata or {},
                    created_at=row.created_at,
                )
        except Exception as exc:
            logger.error("Failed to find by predicate: %s", exc)
            return None

    def update_memory_content(
        self,
        memory_id: UUID,
        user_id: str,
        new_content: str,
        new_metadata: dict,
    ) -> Optional[SemanticMemory]:
        self._ensure_initialized()

        try:
            embedding = []
            try:
                from app.engine.semantic_memory.embeddings import get_embedding_generator

                generator = get_embedding_generator()
                if generator.is_available():
                    embedding = generator.generate(new_content)
            except Exception as exc:
                logger.warning("Failed to generate embedding for update: %s", exc)

            if not embedding:
                success = self.update_fact_preserve_embedding(
                    fact_id=memory_id,
                    content=new_content,
                    metadata=new_metadata,
                    user_id=user_id,
                )
                if success:
                    return self.get_by_id(memory_id, user_id)
                return None

            embedding_str = self._format_embedding(embedding)
            from app.services.embedding_space_guard import stamp_embedding_metadata

            metadata_json = json.dumps(stamp_embedding_metadata(new_metadata))

            from app.core.org_filter import get_effective_org_id, org_where_clause

            eff_org_id = get_effective_org_id()
            org_filter = org_where_clause(eff_org_id)

            with self._session_factory() as session:
                query = text(
                    f"""
                    UPDATE {self.TABLE_NAME}
                    SET content = :content,
                        embedding = CAST(:embedding AS vector),
                        metadata = CAST(:metadata AS jsonb),
                        importance = :importance,
                        updated_at = NOW()
                    WHERE id = :memory_id AND user_id = :user_id
                    {org_filter}
                    RETURNING id, user_id, content, memory_type, importance,
                              metadata, session_id, created_at, updated_at
                """
                )

                params = {
                    "memory_id": str(memory_id),
                    "user_id": user_id,
                    "content": new_content,
                    "embedding": embedding_str,
                    "metadata": metadata_json,
                    "importance": new_metadata.get("confidence", 0.5),
                }
                if eff_org_id is not None:
                    params["org_id"] = eff_org_id

                row = session.execute(query, params).fetchone()
                session.commit()
                if not row:
                    return None
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
                    updated_at=row.updated_at,
                )
        except Exception as exc:
            logger.error("Failed to update memory content %s: %s", memory_id, exc)
            return None

    def upsert_triple(
        self,
        triple: SemanticTriple,
    ) -> Optional[SemanticMemory]:
        existing = self.find_by_predicate(triple.subject, triple.predicate)
        if existing:
            return self.update_memory_content(
                memory_id=existing.id,
                user_id=triple.subject,
                new_content=triple.to_content(),
                new_metadata=triple.to_metadata(),
            )
        return self.save_triple(triple, generate_embedding=True)
