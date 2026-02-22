"""Multi-tenant data layer hardening: org_id indexes + refresh_tokens column

Revision ID: 017
Revises: 016
Create Date: 2026-02-22

Sprint 170c: "Hang Rao Thep" — Multi-Tenant Data Layer Hardening.

Adds:
1. B-tree indexes on organization_id for 6 tables (org filtering performance)
2. organization_id column to refresh_tokens (was missing)
3. Composite user+org indexes for the most common query pattern

Idempotent: all operations use IF NOT EXISTS / _index_exists() checks.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def _index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = :name)"
        ),
        {"name": index_name},
    )
    return result.scalar()


def _column_exists(table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :column)"
        ),
        {"table": table, "column": column},
    )
    return result.scalar()


def _table_exists(table: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :table)"
        ),
        {"table": table},
    )
    return result.scalar()


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. B-tree indexes on organization_id (for org filtering performance)
    # ------------------------------------------------------------------
    org_id_indexes = [
        ("idx_semantic_memories_org_id", "semantic_memories", "organization_id"),
        ("idx_chat_messages_org_id", "chat_messages", "organization_id"),
        ("idx_chat_history_org_id", "chat_history", "organization_id"),
        ("idx_knowledge_embeddings_org_id", "knowledge_embeddings", "organization_id"),
        ("idx_chat_sessions_org_id", "chat_sessions", "organization_id"),
        ("idx_learning_profile_org_id", "learning_profile", "organization_id"),
    ]
    for idx_name, table, column in org_id_indexes:
        if (
            _table_exists(table)
            and _column_exists(table, column)
            and not _index_exists(idx_name)
        ):
            op.create_index(idx_name, table, [column])

    # ------------------------------------------------------------------
    # 2. Add organization_id to refresh_tokens (currently missing)
    # ------------------------------------------------------------------
    if _table_exists("refresh_tokens") and not _column_exists("refresh_tokens", "organization_id"):
        op.add_column(
            "refresh_tokens",
            sa.Column("organization_id", sa.Text(), nullable=True),
        )

    if _table_exists("refresh_tokens") and not _index_exists("idx_refresh_tokens_org_id"):
        if _column_exists("refresh_tokens", "organization_id"):
            op.create_index("idx_refresh_tokens_org_id", "refresh_tokens", ["organization_id"])

    # ------------------------------------------------------------------
    # 3. Composite user+org indexes (most common query pattern)
    # ------------------------------------------------------------------
    composite_indexes = [
        ("idx_semantic_memories_user_org", "semantic_memories", ["user_id", "organization_id"]),
        ("idx_chat_messages_user_org", "chat_messages", ["user_id", "organization_id"]),
    ]
    for idx_name, table, columns in composite_indexes:
        if (
            _table_exists(table)
            and all(_column_exists(table, c) for c in columns)
            and not _index_exists(idx_name)
        ):
            op.create_index(idx_name, table, columns)


def downgrade() -> None:
    # Drop composite indexes
    for idx_name in ["idx_chat_messages_user_org", "idx_semantic_memories_user_org"]:
        if _index_exists(idx_name):
            op.drop_index(idx_name)

    # Drop refresh_tokens org_id index and column
    if _index_exists("idx_refresh_tokens_org_id"):
        op.drop_index("idx_refresh_tokens_org_id")
    if _table_exists("refresh_tokens") and _column_exists("refresh_tokens", "organization_id"):
        op.drop_column("refresh_tokens", "organization_id")

    # Drop org_id B-tree indexes
    org_id_indexes = [
        "idx_learning_profile_org_id",
        "idx_chat_sessions_org_id",
        "idx_knowledge_embeddings_org_id",
        "idx_chat_history_org_id",
        "idx_chat_messages_org_id",
        "idx_semantic_memories_org_id",
    ]
    for idx_name in org_id_indexes:
        if _index_exists(idx_name):
            op.drop_index(idx_name)
