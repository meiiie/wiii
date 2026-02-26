"""Add organization_id to wiii_heartbeat_audit and wiii_pending_actions.

Revision ID: 019
Revises: 018
Create Date: 2026-02-23

Sprint 173b: heartbeat.py writes organization_id to both tables but
migration 016 did not include this column — INSERT fails silently.

Idempotent: checks table and column existence before DDL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


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
    targets = [
        ("wiii_heartbeat_audit", "idx_heartbeat_audit_org"),
        ("wiii_pending_actions", "idx_pending_actions_org"),
    ]
    for table, idx_name in targets:
        if _table_exists(table) and not _column_exists(table, "organization_id"):
            op.add_column(
                table,
                sa.Column("organization_id", sa.Text(), nullable=True),
            )
        if _table_exists(table) and not _index_exists(idx_name):
            op.create_index(idx_name, table, ["organization_id"])


def downgrade() -> None:
    targets = [
        ("wiii_heartbeat_audit", "idx_heartbeat_audit_org"),
        ("wiii_pending_actions", "idx_pending_actions_org"),
    ]
    for table, idx_name in targets:
        if _table_exists(table):
            if _index_exists(idx_name):
                op.drop_index(idx_name, table_name=table)
            if _column_exists(table, "organization_id"):
                op.drop_column(table, "organization_id")
