"""Create semantic_memories table — the core memory store.

Revision ID: 020
Revises: 019
Create Date: 2026-02-23

Sprint 173: The semantic_memories table was never created by any migration.
Migration 001 created `memori_store` (legacy), but the codebase evolved to
use `semantic_memories`. Migrations 011, 015, 017, 018 reference this table
(adding columns, indexes, autovacuum) but it never existed — those DDL
statements silently failed while Alembic stamped their versions.

This migration creates the table from scratch with ALL columns and indexes
that the codebase expects, including those from migrations 011/015/017/018.

Idempotent: checks table existence before CREATE.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'
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
    return result.scalar()


def upgrade() -> None:
    # Ensure pgvector extension exists
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    if _table_exists("semantic_memories"):
        # Table already exists (e.g. manually created) — skip CREATE
        return

    # ------------------------------------------------------------------
    # Create semantic_memories table with ALL columns the codebase uses
    # ------------------------------------------------------------------
    op.execute(sa.text("""
        CREATE TABLE semantic_memories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id TEXT NOT NULL,
            organization_id TEXT,
            content TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            embedding vector(768),
            importance FLOAT NOT NULL DEFAULT 0.5,
            access_count INTEGER DEFAULT 0,
            metadata JSONB,
            session_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ,
            last_accessed TIMESTAMPTZ
        )
    """))

    # ------------------------------------------------------------------
    # Indexes (consolidated from migrations 011, 015, 017, 018)
    # ------------------------------------------------------------------

    # Basic lookup indexes
    op.execute(sa.text(
        "CREATE INDEX idx_sm_user_id ON semantic_memories (user_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX idx_sm_org_id ON semantic_memories (organization_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX idx_sm_user_org ON semantic_memories (user_id, organization_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX idx_sm_user_type ON semantic_memories (user_id, memory_type)"
    ))
    op.execute(sa.text(
        "CREATE INDEX idx_sm_session ON semantic_memories (session_id)"
    ))

    # HNSW vector index for cosine similarity (from migration 015 pattern)
    op.execute(sa.text(
        "CREATE INDEX idx_sm_hnsw ON semantic_memories "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    ))

    # ------------------------------------------------------------------
    # Autovacuum tuning (from migration 018 pattern — high-UPDATE table)
    # ------------------------------------------------------------------
    op.execute(sa.text(
        "ALTER TABLE semantic_memories SET ("
        "  autovacuum_vacuum_scale_factor = 0.01,"
        "  autovacuum_analyze_scale_factor = 0.005,"
        "  autovacuum_vacuum_cost_delay = 2,"
        "  autovacuum_vacuum_cost_limit = 1000"
        ")"
    ))


def downgrade() -> None:
    if _table_exists("semantic_memories"):
        op.execute(sa.text("DROP TABLE semantic_memories CASCADE"))
