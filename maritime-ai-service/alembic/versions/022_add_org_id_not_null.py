"""Backfill NULL organization_id and add NOT NULL constraints

Revision ID: 022
Revises: 021
Create Date: 2026-02-23

Sprint 175b: "Hàng Rào Thép" — Cache Fix + NOT NULL + RLS Foundation

Phase 1: Backfill remaining NULL organization_id → 'default'
Phase 2: ALTER COLUMN SET NOT NULL on org-scoped tables

SKIP NOT NULL on:
- knowledge_embeddings (intentionally NULL = shared KB)
- wiii_character_blocks, wiii_experiences (may be shared)
- refresh_tokens (auth, not org-scoped data)
- org_audit_log (already NOT NULL from creation)
"""
from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Check if table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def _column_is_nullable(table_name: str, column_name: str) -> bool:
    """Check if column is nullable."""
    bind = op.get_bind()
    inspector = inspect(bind)
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return col.get("nullable", True)
    return True


# Org-scoped tables that should have NOT NULL organization_id
ORG_SCOPED_TABLES = [
    "semantic_memories",
    "chat_history",
    "chat_sessions",
    "chat_messages",
    "learning_profile",
    "scheduled_tasks",
    "wiii_emotional_snapshots",
    "wiii_skills",
    "wiii_journal",
    "wiii_browsing_log",
    "wiii_heartbeat_audit",
    "wiii_pending_actions",
    "thread_views",
    "user_preferences",
]


def upgrade() -> None:
    """Backfill NULLs and add NOT NULL constraints."""
    conn = op.get_bind()

    # Phase 1: Backfill NULL → 'default' on all tables with organization_id
    for table in ORG_SCOPED_TABLES:
        if _table_exists(table) and _column_exists(table, "organization_id"):
            result = conn.execute(text(
                f"UPDATE {table} SET organization_id = 'default' "
                f"WHERE organization_id IS NULL"
            ))
            if result.rowcount > 0:
                print(f"  Backfilled {result.rowcount} rows in {table}")

    # Phase 2: SET NOT NULL (idempotent — skip if already NOT NULL)
    for table in ORG_SCOPED_TABLES:
        if not _table_exists(table):
            continue
        if not _column_exists(table, "organization_id"):
            continue
        if not _column_is_nullable(table, "organization_id"):
            continue  # Already NOT NULL

        op.alter_column(
            table,
            "organization_id",
            nullable=False,
            server_default="default",
        )
        print(f"  SET NOT NULL on {table}.organization_id")


def downgrade() -> None:
    """Revert NOT NULL constraints (make nullable again)."""
    for table in ORG_SCOPED_TABLES:
        if not _table_exists(table):
            continue
        if not _column_exists(table, "organization_id"):
            continue
        if _column_is_nullable(table, "organization_id"):
            continue  # Already nullable

        op.alter_column(
            table,
            "organization_id",
            nullable=True,
            server_default=None,
        )
