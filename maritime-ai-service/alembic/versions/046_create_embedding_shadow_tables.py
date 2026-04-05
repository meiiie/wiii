"""Create embedding shadow tables and registry for zero-downtime migrations.

Revision ID: 046
Revises: 045
Create Date: 2026-04-02

This introduces:
- embedding_space_registry: active/shadow/retired space control per entity
- semantic_memory_vectors: side-table vectors for semantic_memories
- knowledge_embedding_vectors: side-table vectors for knowledge_embeddings

The design keeps legacy inline vector(768) columns intact while enabling
dual-write and shadow-read promotion for new embedding spaces.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = :name)"
        ),
        {"name": index_name},
    )
    return bool(result.scalar())


def upgrade() -> None:
    if not _table_exists("embedding_space_registry"):
        op.execute(
            sa.text(
                """
                CREATE TABLE embedding_space_registry (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    entity_type TEXT NOT NULL,
                    space_fingerprint TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    storage_kind TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reads_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    writes_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    index_ready BOOLEAN NOT NULL DEFAULT FALSE,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ,
                    CONSTRAINT uq_embedding_space_registry_entity_space
                        UNIQUE (entity_type, space_fingerprint),
                    CONSTRAINT ck_embedding_space_registry_storage_kind
                        CHECK (storage_kind IN ('inline', 'shadow')),
                    CONSTRAINT ck_embedding_space_registry_state
                        CHECK (state IN ('active', 'shadow', 'retired')),
                    CONSTRAINT ck_embedding_space_registry_dimensions
                        CHECK (dimensions > 0)
                )
                """
            )
        )

    if not _table_exists("semantic_memory_vectors"):
        op.execute(
            sa.text(
                """
                CREATE TABLE semantic_memory_vectors (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    memory_id UUID NOT NULL REFERENCES semantic_memories(id) ON DELETE CASCADE,
                    space_fingerprint TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding DOUBLE PRECISION[] NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ,
                    CONSTRAINT uq_semantic_memory_vectors_space
                        UNIQUE (memory_id, space_fingerprint),
                    CONSTRAINT ck_semantic_memory_vectors_dimensions
                        CHECK (dimensions > 0)
                )
                """
            )
        )

    if not _table_exists("knowledge_embedding_vectors"):
        op.execute(
            sa.text(
                """
                CREATE TABLE knowledge_embedding_vectors (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    knowledge_embedding_id UUID NOT NULL REFERENCES knowledge_embeddings(id) ON DELETE CASCADE,
                    space_fingerprint TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    dimensions INTEGER NOT NULL,
                    embedding DOUBLE PRECISION[] NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ,
                    CONSTRAINT uq_knowledge_embedding_vectors_space
                        UNIQUE (knowledge_embedding_id, space_fingerprint),
                    CONSTRAINT ck_knowledge_embedding_vectors_dimensions
                        CHECK (dimensions > 0)
                )
                """
            )
        )

    index_statements = {
        "idx_embedding_space_registry_entity_state": """
            CREATE INDEX idx_embedding_space_registry_entity_state
            ON embedding_space_registry (entity_type, state, reads_enabled, writes_enabled)
        """,
        "idx_embedding_space_registry_entity_storage": """
            CREATE INDEX idx_embedding_space_registry_entity_storage
            ON embedding_space_registry (entity_type, storage_kind, space_fingerprint)
        """,
        "idx_semantic_memory_vectors_space_memory": """
            CREATE INDEX idx_semantic_memory_vectors_space_memory
            ON semantic_memory_vectors (space_fingerprint, memory_id)
        """,
        "idx_semantic_memory_vectors_model": """
            CREATE INDEX idx_semantic_memory_vectors_model
            ON semantic_memory_vectors (model, dimensions)
        """,
        "idx_knowledge_embedding_vectors_space_node": """
            CREATE INDEX idx_knowledge_embedding_vectors_space_node
            ON knowledge_embedding_vectors (space_fingerprint, knowledge_embedding_id)
        """,
        "idx_knowledge_embedding_vectors_model": """
            CREATE INDEX idx_knowledge_embedding_vectors_model
            ON knowledge_embedding_vectors (model, dimensions)
        """,
    }
    for index_name, ddl in index_statements.items():
        if not _index_exists(index_name):
            op.execute(sa.text(ddl))


def downgrade() -> None:
    index_names = (
        "idx_knowledge_embedding_vectors_model",
        "idx_knowledge_embedding_vectors_space_node",
        "idx_semantic_memory_vectors_model",
        "idx_semantic_memory_vectors_space_memory",
        "idx_embedding_space_registry_entity_storage",
        "idx_embedding_space_registry_entity_state",
    )
    for index_name in index_names:
        if _index_exists(index_name):
            op.execute(sa.text(f"DROP INDEX {index_name}"))

    if _table_exists("knowledge_embedding_vectors"):
        op.execute(sa.text("DROP TABLE knowledge_embedding_vectors CASCADE"))
    if _table_exists("semantic_memory_vectors"):
        op.execute(sa.text("DROP TABLE semantic_memory_vectors CASCADE"))
    if _table_exists("embedding_space_registry"):
        op.execute(sa.text("DROP TABLE embedding_space_registry CASCADE"))
