"""Add living agent safety tables: heartbeat_audit, pending_actions

Revision ID: 016
Revises: 015
Create Date: 2026-02-22

Sprint 171: "Quyền Tự Chủ" — Grant Wiii Autonomous Capabilities Safely.
Creates 2 tables for safety and auditability:
- wiii_heartbeat_audit: Audit trail for every heartbeat cycle
- wiii_pending_actions: Human-approval queue for external actions

Idempotent: checks table existence before DDL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    """Check if table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # 1. wiii_heartbeat_audit — Audit trail for every heartbeat cycle
    if not table_exists('wiii_heartbeat_audit'):
        op.create_table(
            'wiii_heartbeat_audit',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('cycle_number', sa.Integer, nullable=False),
            sa.Column('actions_taken', sa.Text, server_default='[]'),  # JSON array
            sa.Column('insights_gained', sa.Integer, server_default='0'),
            sa.Column('duration_ms', sa.Integer, server_default='0'),
            sa.Column('error', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            'idx_heartbeat_audit_created',
            'wiii_heartbeat_audit',
            ['created_at'],
            postgresql_using='btree',
        )

    # 2. wiii_pending_actions — Human-approval queue for external actions
    if not table_exists('wiii_pending_actions'):
        op.create_table(
            'wiii_pending_actions',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('action_type', sa.Text, nullable=False),
            sa.Column('target', sa.Text, server_default=''),
            sa.Column('priority', sa.Float, server_default='0.5'),
            sa.Column('metadata', sa.Text, server_default='{}'),  # JSON object
            sa.Column('status', sa.Text, server_default='pending'),  # pending/approved/rejected/expired
            sa.Column('approved_by', sa.Text, nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            'idx_pending_actions_status',
            'wiii_pending_actions',
            ['status'],
        )
        op.create_index(
            'idx_pending_actions_created',
            'wiii_pending_actions',
            ['created_at'],
            postgresql_using='btree',
        )


def downgrade() -> None:
    for table in ['wiii_pending_actions', 'wiii_heartbeat_audit']:
        if table_exists(table):
            op.drop_table(table)
