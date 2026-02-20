"""Add users, user_identities, and refresh_tokens tables

Revision ID: 009
Revises: 008
Create Date: 2026-02-20

Sprint 157: "Đăng Nhập" — Google OAuth + Identity Federation
- users: Canonical user table (replaces implicit learning_profile-only)
- user_identities: Multi-provider identity linking (Google, LTI, etc.)
- refresh_tokens: JWT refresh token storage for session management
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
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
    """Create users, user_identities, refresh_tokens tables."""

    # =========================================================================
    # USERS — Canonical user table
    # =========================================================================
    if not table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Text, primary_key=True),  # UUID as text for compat
            sa.Column('email', sa.Text, nullable=True),
            sa.Column('name', sa.Text, nullable=True),
            sa.Column('avatar_url', sa.Text, nullable=True),
            sa.Column('role', sa.Text, server_default='student'),
            sa.Column('is_active', sa.Boolean, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index('ix_users_email', 'users', ['email'], unique=False)

    # =========================================================================
    # USER_IDENTITIES — Multi-provider identity linking
    # =========================================================================
    if not table_exists('user_identities'):
        op.create_table(
            'user_identities',
            sa.Column('id', sa.Text, primary_key=True),  # UUID
            sa.Column(
                'user_id', sa.Text,
                sa.ForeignKey('users.id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('provider', sa.Text, nullable=False),  # 'google', 'lti'
            sa.Column('provider_sub', sa.Text, nullable=False),  # Provider's user ID
            sa.Column('provider_issuer', sa.Text, nullable=True),  # LTI issuer URL
            sa.Column('email', sa.Text, nullable=True),
            sa.Column('display_name', sa.Text, nullable=True),
            sa.Column('avatar_url', sa.Text, nullable=True),
            sa.Column('linked_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index('ix_identity_user', 'user_identities', ['user_id'])
        op.create_index(
            'ix_identity_provider_sub',
            'user_identities',
            ['provider', 'provider_sub', 'provider_issuer'],
            unique=True,
        )
        op.create_index('ix_identity_email', 'user_identities', ['email'])

    # =========================================================================
    # REFRESH_TOKENS — JWT refresh token storage
    # =========================================================================
    if not table_exists('refresh_tokens'):
        op.create_table(
            'refresh_tokens',
            sa.Column('id', sa.Text, primary_key=True),  # Token ID (jti)
            sa.Column(
                'user_id', sa.Text,
                sa.ForeignKey('users.id', ondelete='CASCADE'),
                nullable=False,
            ),
            sa.Column('token_hash', sa.Text, nullable=False),  # SHA-256 hash
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_refresh_user', 'refresh_tokens', ['user_id'])
        op.create_index('ix_refresh_hash', 'refresh_tokens', ['token_hash'])

    # =========================================================================
    # LINK learning_profile to users (optional FK for gradual migration)
    # =========================================================================
    if table_exists('learning_profile') and not column_exists('learning_profile', 'auth_user_id'):
        op.add_column(
            'learning_profile',
            sa.Column(
                'auth_user_id', sa.Text,
                sa.ForeignKey('users.id', ondelete='SET NULL'),
                nullable=True,
            ),
        )
        op.create_index('ix_lp_auth_user', 'learning_profile', ['auth_user_id'])


def downgrade() -> None:
    """Remove Sprint 157 tables."""
    if table_exists('learning_profile') and column_exists('learning_profile', 'auth_user_id'):
        op.drop_index('ix_lp_auth_user', table_name='learning_profile')
        op.drop_column('learning_profile', 'auth_user_id')

    if table_exists('refresh_tokens'):
        op.drop_table('refresh_tokens')

    if table_exists('user_identities'):
        op.drop_table('user_identities')

    if table_exists('users'):
        op.drop_table('users')
