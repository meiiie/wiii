"""Add organization_id to data tables for multi-tenant isolation

Revision ID: 011
Revises: 010
Create Date: 2026-02-20

Sprint 160: "Hàng Rào" — Multi-Tenant Data Isolation
- Add organization_id TEXT to: semantic_memories, chat_messages, chat_sessions,
  chat_history, learning_profile
- Backfill existing rows with 'default' (except knowledge_embeddings stays NULL = shared KB)
- Composite indexes for query performance
- org_audit_log table for admin operation tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
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


def _add_org_id_column(table_name: str, backfill_default: bool = True) -> None:
    """Add organization_id TEXT column to a table if not already present.

    Args:
        table_name: Target table.
        backfill_default: If True, UPDATE existing NULL rows to 'default'.
    """
    if not table_exists(table_name):
        return
    if column_exists(table_name, 'organization_id'):
        return

    op.add_column(
        table_name,
        sa.Column('organization_id', sa.Text, nullable=True),
    )

    if backfill_default:
        op.execute(
            f"UPDATE {table_name} SET organization_id = 'default' "
            f"WHERE organization_id IS NULL"
        )


def upgrade() -> None:
    # =========================================================================
    # 1. Add organization_id to semantic_memories
    # =========================================================================
    _add_org_id_column('semantic_memories', backfill_default=True)
    if table_exists('semantic_memories') and column_exists('semantic_memories', 'organization_id'):
        # Composite index for (user_id, organization_id) — most common query pattern
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_semantic_memories_user_org
            ON semantic_memories (user_id, organization_id)
        """)

    # =========================================================================
    # 2. Add organization_id to chat_messages (legacy schema)
    # =========================================================================
    _add_org_id_column('chat_messages', backfill_default=True)
    if table_exists('chat_messages') and column_exists('chat_messages', 'organization_id'):
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session_org
            ON chat_messages (session_id, organization_id)
        """)

    # =========================================================================
    # 3. Add organization_id to chat_sessions (legacy schema)
    # =========================================================================
    _add_org_id_column('chat_sessions', backfill_default=True)
    if table_exists('chat_sessions') and column_exists('chat_sessions', 'organization_id'):
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_org
            ON chat_sessions (user_id, organization_id)
        """)

    # =========================================================================
    # 4. Add organization_id to chat_history (new schema, CHỈ THỊ SỐ 04)
    # =========================================================================
    _add_org_id_column('chat_history', backfill_default=True)
    if table_exists('chat_history') and column_exists('chat_history', 'organization_id'):
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_history_session_org
            ON chat_history (session_id, organization_id)
        """)
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_history_user_org
            ON chat_history (user_id, organization_id)
        """)

    # =========================================================================
    # 5. Add organization_id to learning_profile
    # =========================================================================
    _add_org_id_column('learning_profile', backfill_default=True)

    # =========================================================================
    # 6. knowledge_embeddings — NO backfill (NULL = shared KB)
    # =========================================================================
    _add_org_id_column('knowledge_embeddings', backfill_default=False)
    if table_exists('knowledge_embeddings') and column_exists('knowledge_embeddings', 'organization_id'):
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_org
            ON knowledge_embeddings (organization_id)
        """)

    # =========================================================================
    # 7. org_audit_log — Admin operation tracking
    # =========================================================================
    if not table_exists('org_audit_log'):
        op.create_table(
            'org_audit_log',
            sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
            sa.Column('organization_id', sa.Text, nullable=False),
            sa.Column('actor_user_id', sa.Text, nullable=False),
            sa.Column('action', sa.Text, nullable=False),
            sa.Column('resource_type', sa.Text, nullable=True),
            sa.Column('resource_id', sa.Text, nullable=True),
            sa.Column('details', sa.JSON, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_audit_log_org_created
            ON org_audit_log (organization_id, created_at DESC)
        """)


def downgrade() -> None:
    # Drop audit log table
    if table_exists('org_audit_log'):
        op.drop_table('org_audit_log')

    # Drop indexes then columns (reverse order)
    for table_name, index_names in [
        ('knowledge_embeddings', ['idx_knowledge_embeddings_org']),
        ('learning_profile', []),
        ('chat_history', ['idx_chat_history_session_org', 'idx_chat_history_user_org']),
        ('chat_sessions', ['idx_chat_sessions_user_org']),
        ('chat_messages', ['idx_chat_messages_session_org']),
        ('semantic_memories', ['idx_semantic_memories_user_org']),
    ]:
        if not table_exists(table_name):
            continue
        for idx_name in index_names:
            op.execute(f"DROP INDEX IF EXISTS {idx_name}")
        if column_exists(table_name, 'organization_id'):
            op.drop_column(table_name, 'organization_id')
