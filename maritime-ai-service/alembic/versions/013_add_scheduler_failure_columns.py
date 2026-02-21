"""Add failure_count and last_error to scheduled_tasks

Revision ID: 013
Revises: 012
Create Date: 2026-02-21

Audit fix: These columns are referenced in scheduler_repository.py
(mark_failed, get_due_tasks) but were never created by any migration.
- failure_count INTEGER DEFAULT 0 — tracks consecutive failures
- last_error TEXT — stores last error message for debugging
- Idempotent: checks column existence before DDL
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return False
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not table_exists('scheduled_tasks'):
        return

    # 1. failure_count — tracks consecutive failures (auto-disable at 3)
    if not column_exists('scheduled_tasks', 'failure_count'):
        op.add_column(
            'scheduled_tasks',
            sa.Column('failure_count', sa.Integer, server_default='0', nullable=True),
        )
        op.execute(
            "UPDATE scheduled_tasks SET failure_count = 0 "
            "WHERE failure_count IS NULL"
        )

    # 2. last_error — stores last error message for debugging
    if not column_exists('scheduled_tasks', 'last_error'):
        op.add_column(
            'scheduled_tasks',
            sa.Column('last_error', sa.Text, nullable=True),
        )

    # 3. Index on expires_at for refresh_tokens cleanup queries
    if table_exists('refresh_tokens'):
        if not column_exists('refresh_tokens', 'expires_at'):
            pass  # Column doesn't exist, skip
        else:
            op.execute("""
                CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires
                ON refresh_tokens (expires_at)
            """)


def downgrade() -> None:
    if table_exists('refresh_tokens'):
        op.execute("DROP INDEX IF EXISTS idx_refresh_tokens_expires")

    if not table_exists('scheduled_tasks'):
        return

    if column_exists('scheduled_tasks', 'last_error'):
        op.drop_column('scheduled_tasks', 'last_error')
    if column_exists('scheduled_tasks', 'failure_count'):
        op.drop_column('scheduled_tasks', 'failure_count')
