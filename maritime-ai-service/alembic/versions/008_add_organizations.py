"""Add organizations and user_organizations tables

Revision ID: 008
Revises: 007
Create Date: 2026-02-09

Sprint 24: Multi-Organization (Multi-Tenant) Architecture
- organizations: Organization registry with domain scoping
- user_organizations: Many-to-many user-org membership
- organization_id columns on thread_views, user_preferences, scheduled_tasks
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
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
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """
    Create organizations, user_organizations tables.
    Add organization_id to existing tables.
    Seed default organization.
    """

    # =========================================================================
    # ORGANIZATIONS — Organization registry
    # =========================================================================
    if not table_exists('organizations'):
        op.create_table(
            'organizations',
            sa.Column('id', sa.Text, primary_key=True),
            sa.Column('name', sa.Text, nullable=False),
            sa.Column('display_name', sa.Text, nullable=True),
            sa.Column('description', sa.Text, nullable=True),
            sa.Column('allowed_domains', ARRAY(sa.Text), server_default='{}'),
            sa.Column('default_domain', sa.Text, nullable=True),
            sa.Column('settings', JSONB, server_default='{}'),
            sa.Column('is_active', sa.Boolean, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    # =========================================================================
    # USER_ORGANIZATIONS — Many-to-many membership
    # =========================================================================
    if not table_exists('user_organizations'):
        op.create_table(
            'user_organizations',
            sa.Column('user_id', sa.Text, nullable=False),
            sa.Column(
                'organization_id', sa.Text,
                sa.ForeignKey('organizations.id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('role', sa.Text, server_default='member'),
            sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('user_id', 'organization_id'),
        )
        op.create_index('ix_user_orgs_user', 'user_organizations', ['user_id'])
        op.create_index('ix_user_orgs_org', 'user_organizations', ['organization_id'])

    # =========================================================================
    # ADD organization_id TO EXISTING TABLES (nullable for backward compat)
    # =========================================================================
    if table_exists('thread_views') and not column_exists('thread_views', 'organization_id'):
        op.add_column(
            'thread_views',
            sa.Column(
                'organization_id', sa.Text,
                sa.ForeignKey('organizations.id'),
                nullable=True,
            ),
        )
        op.create_index('ix_thread_views_org', 'thread_views', ['organization_id'])

    if table_exists('user_preferences') and not column_exists('user_preferences', 'organization_id'):
        op.add_column(
            'user_preferences',
            sa.Column(
                'organization_id', sa.Text,
                sa.ForeignKey('organizations.id'),
                nullable=True,
            ),
        )

    if table_exists('scheduled_tasks') and not column_exists('scheduled_tasks', 'organization_id'):
        op.add_column(
            'scheduled_tasks',
            sa.Column(
                'organization_id', sa.Text,
                sa.ForeignKey('organizations.id'),
                nullable=True,
            ),
        )
        op.create_index('ix_scheduled_tasks_org', 'scheduled_tasks', ['organization_id'])

    # =========================================================================
    # SEED DEFAULT ORGANIZATION
    # =========================================================================
    op.execute(
        "INSERT INTO organizations (id, name, display_name, allowed_domains, default_domain) "
        "VALUES ('default', 'Default', 'Wiii Default Organization', "
        "ARRAY['maritime', 'traffic_law'], 'maritime') "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    """Remove organization_id columns and drop new tables."""
    # Remove columns from existing tables
    if table_exists('scheduled_tasks') and column_exists('scheduled_tasks', 'organization_id'):
        op.drop_index('ix_scheduled_tasks_org', table_name='scheduled_tasks')
        op.drop_column('scheduled_tasks', 'organization_id')

    if table_exists('user_preferences') and column_exists('user_preferences', 'organization_id'):
        op.drop_column('user_preferences', 'organization_id')

    if table_exists('thread_views') and column_exists('thread_views', 'organization_id'):
        op.drop_index('ix_thread_views_org', table_name='thread_views')
        op.drop_column('thread_views', 'organization_id')

    # Drop tables
    if table_exists('user_organizations'):
        op.drop_table('user_organizations')

    if table_exists('organizations'):
        op.drop_table('organizations')
