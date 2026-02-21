"""Add living agent tables: skills, journal, browsing_log, emotional_snapshots

Revision ID: 014
Revises: 013
Create Date: 2026-02-22

Sprint 170: "Linh Hồn Sống" — Autonomous Living Agent.
Creates 4 tables for Wiii's autonomous life:
- wiii_skills: Self-built knowledge and skill tracking
- wiii_journal: Daily journal entries (life narrative)
- wiii_browsing_log: Autonomous browsing history
- wiii_emotional_snapshots: Emotional state snapshots

All tables have organization_id for multi-tenant support.
Idempotent: checks table existence before DDL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # 1. wiii_skills — Self-built knowledge tracking
    if not table_exists('wiii_skills'):
        op.create_table(
            'wiii_skills',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('skill_name', sa.Text, nullable=False),
            sa.Column('domain', sa.Text, server_default='general'),
            sa.Column('status', sa.Text, server_default='discovered'),
            sa.Column('confidence', sa.Float, server_default='0.0'),
            sa.Column('notes', sa.Text, server_default=''),
            sa.Column('sources', sa.Text, server_default='[]'),  # JSON array
            sa.Column('usage_count', sa.Integer, server_default='0'),
            sa.Column('success_rate', sa.Float, server_default='0.0'),
            sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('last_practiced', sa.DateTime(timezone=True), nullable=True),
            sa.Column('mastered_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('organization_id', sa.Text, nullable=True),
            sa.Column('metadata', sa.Text, server_default='{}'),  # JSON object
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index('idx_skills_status', 'wiii_skills', ['status'])
        op.create_index('idx_skills_domain', 'wiii_skills', ['domain'])
        op.create_index('idx_skills_org', 'wiii_skills', ['organization_id'])

    # 2. wiii_journal — Daily journal entries
    if not table_exists('wiii_journal'):
        op.create_table(
            'wiii_journal',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('entry_date', sa.Date, nullable=False),
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('mood_summary', sa.Text, server_default=''),
            sa.Column('energy_avg', sa.Float, server_default='0.5'),
            sa.Column('notable_events', sa.Text, server_default='[]'),  # JSON array
            sa.Column('learnings', sa.Text, server_default='[]'),  # JSON array
            sa.Column('goals_next', sa.Text, server_default='[]'),  # JSON array
            sa.Column('organization_id', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index('idx_journal_date', 'wiii_journal', ['entry_date'])
        op.create_index('idx_journal_org', 'wiii_journal', ['organization_id'])

    # 3. wiii_browsing_log — Autonomous browsing history
    if not table_exists('wiii_browsing_log'):
        op.create_table(
            'wiii_browsing_log',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('platform', sa.Text, nullable=False),
            sa.Column('url', sa.Text, nullable=True),
            sa.Column('title', sa.Text, server_default=''),
            sa.Column('summary', sa.Text, server_default=''),
            sa.Column('relevance_score', sa.Float, server_default='0.0'),
            sa.Column('emotional_reaction', sa.Text, nullable=True),
            sa.Column('saved_as_insight', sa.Boolean, server_default='false'),
            sa.Column('browsed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('organization_id', sa.Text, nullable=True),
            sa.Column('metadata', sa.Text, server_default='{}'),  # JSON object
        )
        op.create_index('idx_browsing_platform', 'wiii_browsing_log', ['platform'])
        op.create_index('idx_browsing_date', 'wiii_browsing_log', ['browsed_at'])
        op.create_index('idx_browsing_org', 'wiii_browsing_log', ['organization_id'])

    # 4. wiii_emotional_snapshots — Emotional state history
    if not table_exists('wiii_emotional_snapshots'):
        op.create_table(
            'wiii_emotional_snapshots',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('primary_mood', sa.Text, nullable=False),
            sa.Column('energy_level', sa.Float, nullable=False),
            sa.Column('social_battery', sa.Float, nullable=False),
            sa.Column('engagement', sa.Float, nullable=False),
            sa.Column('trigger_event', sa.Text, nullable=True),
            sa.Column('snapshot_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('organization_id', sa.Text, nullable=True),
            sa.Column('state_json', sa.Text, server_default='{}'),  # Full EmotionalState JSON
        )
        op.create_index('idx_emotional_date', 'wiii_emotional_snapshots', ['snapshot_at'])
        op.create_index('idx_emotional_org', 'wiii_emotional_snapshots', ['organization_id'])


def downgrade() -> None:
    for table in ['wiii_emotional_snapshots', 'wiii_browsing_log', 'wiii_journal', 'wiii_skills']:
        if table_exists(table):
            op.drop_table(table)
