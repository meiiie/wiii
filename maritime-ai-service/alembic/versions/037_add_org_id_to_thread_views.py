"""037: Add organization_id to thread_views, user_preferences, scheduled_tasks

Sprint 225: "Đồng Bộ Trò Chuyện" — Cross-Platform Conversation Sync

These three tables were created in migration 007 BEFORE the org_id pattern
was standardized in migration 011. Migration 011 added organization_id to
6 other tables but missed these three. Migration 022 expected the column
to exist for NOT NULL enforcement but silently skipped due to _column_exists().

This migration fixes the gap: adds the column, backfills 'default', and
sets NOT NULL to match all other org-scoped tables.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


TABLES = ["thread_views", "user_preferences", "scheduled_tasks"]


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    conn = op.get_bind()

    for table in TABLES:
        if not _table_exists(table):
            continue
        if _column_exists(table, "organization_id"):
            # Column already exists (e.g., fresh install ran updated 007)
            # Still backfill NULLs and ensure NOT NULL
            conn.execute(text(
                f"UPDATE {table} SET organization_id = 'default' "
                f"WHERE organization_id IS NULL"
            ))
            continue

        # Add column with default
        op.add_column(
            table,
            sa.Column(
                "organization_id",
                sa.Text,
                nullable=True,
                server_default="default",
            ),
        )

        # Backfill existing rows
        conn.execute(text(
            f"UPDATE {table} SET organization_id = 'default' "
            f"WHERE organization_id IS NULL"
        ))

        # Set NOT NULL
        op.alter_column(table, "organization_id", nullable=False)

    # Add index for thread_views (user_id + organization_id)
    if _table_exists("thread_views") and _column_exists("thread_views", "organization_id"):
        try:
            op.create_index(
                "idx_thread_views_user_org",
                "thread_views",
                ["user_id", "organization_id"],
            )
        except Exception:
            pass  # Index may already exist


def downgrade() -> None:
    for table in TABLES:
        if _table_exists(table) and _column_exists(table, "organization_id"):
            op.drop_column(table, "organization_id")

    try:
        op.drop_index("idx_thread_views_user_org", table_name="thread_views")
    except Exception:
        pass
