"""Add organization_id to character tables

Revision ID: 012
Revises: 011
Create Date: 2026-02-20

Sprint 160b: "Hoàn Thiện" — Complete Isolation
- Add organization_id TEXT to wiii_character_blocks and wiii_experiences
- Backfill existing rows with 'default'
- Create indexes for query performance
- Idempotent: checks table and column existence before any DDL
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
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


def _add_org_id_column(table_name: str) -> None:
    """Add organization_id TEXT column with 'default' backfill if not present."""
    if not table_exists(table_name):
        return
    if column_exists(table_name, 'organization_id'):
        return

    op.add_column(
        table_name,
        sa.Column('organization_id', sa.Text, nullable=True),
    )
    op.execute(
        f"UPDATE {table_name} SET organization_id = 'default' "
        f"WHERE organization_id IS NULL"
    )


def upgrade() -> None:
    # 1. wiii_character_blocks
    _add_org_id_column('wiii_character_blocks')
    if table_exists('wiii_character_blocks') and column_exists('wiii_character_blocks', 'organization_id'):
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_character_blocks_org_id
            ON wiii_character_blocks (organization_id)
        """)

    # 2. wiii_experiences
    _add_org_id_column('wiii_experiences')
    if table_exists('wiii_experiences') and column_exists('wiii_experiences', 'organization_id'):
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_experiences_org_id
            ON wiii_experiences (organization_id)
        """)


def downgrade() -> None:
    for table_name, index_name in [
        ('wiii_experiences', 'idx_experiences_org_id'),
        ('wiii_character_blocks', 'idx_character_blocks_org_id'),
    ]:
        if not table_exists(table_name):
            continue
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        if column_exists(table_name, 'organization_id'):
            op.drop_column(table_name, 'organization_id')
