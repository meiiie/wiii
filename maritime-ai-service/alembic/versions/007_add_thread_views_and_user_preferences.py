"""Add thread_views and user_preferences tables

Revision ID: 007
Revises: 006
Create Date: 2026-02-09

Sprint 16-17: Virtual Agent-per-User Architecture
- thread_views: Server-side conversation index for multi-device sync
- user_preferences: Structured user preferences for agent adaptation
- scheduled_tasks: Proactive agent scheduler (Sprint 19)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """
    Create thread_views, user_preferences, and scheduled_tasks tables.

    Sprint 16: Thread management for per-user conversation isolation
    Sprint 17: User preferences for agent adaptation
    Sprint 19: Scheduled tasks for proactive agent
    """

    # =========================================================================
    # THREAD VIEWS — Server-side conversation index
    # =========================================================================
    if not table_exists('thread_views'):
        op.create_table(
            'thread_views',
            sa.Column('thread_id', sa.Text, primary_key=True),
            sa.Column('user_id', sa.Text, nullable=False),
            sa.Column('domain_id', sa.Text, nullable=False, server_default='maritime'),
            sa.Column('title', sa.Text, nullable=True),
            sa.Column('message_count', sa.Integer, server_default='0'),
            sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('is_deleted', sa.Boolean, server_default='false'),
            sa.Column('extra_data', JSONB, server_default='{}'),
        )
        op.create_index('idx_thread_views_user', 'thread_views', ['user_id'])
        op.create_index(
            'idx_thread_views_updated',
            'thread_views',
            [sa.text('updated_at DESC')],
        )
        op.create_index(
            'idx_thread_views_user_active',
            'thread_views',
            ['user_id'],
            postgresql_where=sa.text("is_deleted = false"),
        )

    # =========================================================================
    # USER PREFERENCES — Structured preferences for agent adaptation
    # =========================================================================
    if not table_exists('user_preferences'):
        op.create_table(
            'user_preferences',
            sa.Column('user_id', sa.Text, primary_key=True),
            sa.Column('display_name', sa.Text, nullable=True),
            sa.Column('preferred_domain', sa.Text, server_default='maritime'),
            sa.Column('language', sa.Text, server_default='vi'),
            sa.Column('pronoun_style', sa.Text, server_default='auto'),
            sa.Column('learning_style', sa.Text, server_default='mixed'),
            sa.Column('difficulty', sa.Text, server_default='intermediate'),
            sa.Column('timezone', sa.Text, server_default='Asia/Ho_Chi_Minh'),
            sa.Column('extra_prefs', JSONB, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # =========================================================================
    # SCHEDULED TASKS — Proactive agent scheduler
    # =========================================================================
    if not table_exists('scheduled_tasks'):
        op.create_table(
            'scheduled_tasks',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('user_id', sa.Text, nullable=False),
            sa.Column('domain_id', sa.Text, nullable=False, server_default='maritime'),
            sa.Column('description', sa.Text, nullable=False),
            sa.Column('schedule_type', sa.Text, nullable=False),
            sa.Column('schedule_expr', sa.Text, nullable=False),
            sa.Column('next_run', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_run', sa.DateTime(timezone=True), nullable=True),
            sa.Column('run_count', sa.Integer, server_default='0'),
            sa.Column('max_runs', sa.Integer, nullable=True),
            sa.Column('status', sa.Text, server_default='active'),
            sa.Column('channel', sa.Text, server_default='websocket'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('extra_data', JSONB, server_default='{}'),
        )
        op.create_index(
            'idx_scheduled_next',
            'scheduled_tasks',
            ['next_run'],
            postgresql_where=sa.text("status = 'active'"),
        )
        op.create_index('idx_scheduled_user', 'scheduled_tasks', ['user_id'])


def downgrade() -> None:
    """Remove thread_views, user_preferences, and scheduled_tasks tables."""
    if table_exists('scheduled_tasks'):
        op.drop_table('scheduled_tasks')

    if table_exists('user_preferences'):
        op.drop_table('user_preferences')

    if table_exists('thread_views'):
        op.drop_table('thread_views')
