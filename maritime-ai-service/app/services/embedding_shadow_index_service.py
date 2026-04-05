"""Create dimension-specific shadow vector indexes for promoted spaces."""

from __future__ import annotations

import hashlib
import logging
from typing import Iterable

from sqlalchemy import text

from app.core.database import get_shared_session_factory
from app.services.embedding_space_guard import EmbeddingSpaceContract
from app.services.embedding_space_registry_service import upsert_embedding_space_registry_entry

logger = logging.getLogger(__name__)


def _normalize_tables(tables: Iterable[str] | None) -> tuple[str, ...]:
    normalized: list[str] = []
    for table_name in (tables or ("semantic_memories", "knowledge_embeddings")):
        clean = (table_name or "").strip().lower()
        if clean in {"semantic_memories", "knowledge_embeddings"} and clean not in normalized:
            normalized.append(clean)
    return tuple(normalized)


def build_shadow_index_name(*, entity_type: str, fingerprint: str) -> str:
    digest = hashlib.md5(fingerprint.encode("utf-8")).hexdigest()[:10]
    prefix = "smv" if entity_type == "semantic_memories" else "kev"
    return f"idx_{prefix}_shadow_hnsw_{digest}"


def ensure_shadow_vector_indexes(
    *,
    target_contract: EmbeddingSpaceContract,
    tables: Iterable[str] | None = None,
) -> tuple[str, ...]:
    session_factory = get_shared_session_factory()
    created_indexes: list[str] = []
    normalized_tables = _normalize_tables(tables)

    with session_factory() as session:
        for entity_type in normalized_tables:
            vector_table = (
                "semantic_memory_vectors"
                if entity_type == "semantic_memories"
                else "knowledge_embedding_vectors"
            )
            index_name = build_shadow_index_name(
                entity_type=entity_type,
                fingerprint=target_contract.fingerprint,
            )
            safe_fingerprint = target_contract.fingerprint.replace("'", "''")
            session.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON {vector_table}
                    USING hnsw (((embedding::vector({int(target_contract.dimensions)}))) vector_cosine_ops)
                    WHERE space_fingerprint = '{safe_fingerprint}'
                      AND dimensions = {int(target_contract.dimensions)}
                    """
                )
            )
            created_indexes.append(index_name)
        session.commit()

    for entity_type, index_name in zip(normalized_tables, created_indexes, strict=False):
        upsert_embedding_space_registry_entry(
            entity_type=entity_type,  # type: ignore[arg-type]
            contract=target_contract,
            storage_kind="shadow",
            state="shadow",
            reads_enabled=False,
            writes_enabled=True,
            index_ready=True,
            metadata={"index_name": index_name, "index_ready": True},
        )

    logger.info(
        "Ensured shadow vector indexes for %s: %s",
        target_contract.fingerprint,
        ", ".join(created_indexes) or "none",
    )
    return tuple(created_indexes)
