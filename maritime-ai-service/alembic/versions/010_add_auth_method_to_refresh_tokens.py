"""Add auth_method column to refresh_tokens table

Revision ID: 010
Revises: 009
Create Date: 2026-02-20

Sprint 158: "Tài Khoản" — User Management
- auth_method column tracks which provider issued the refresh token (google, lms, api_key)
- server_default='google' so existing Sprint 157 tokens get correct default
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        columns = [c["name"] for c in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def upgrade() -> None:
    """Add auth_method to refresh_tokens."""
    if not column_exists('refresh_tokens', 'auth_method'):
        op.add_column(
            'refresh_tokens',
            sa.Column('auth_method', sa.Text, server_default='google', nullable=True),
        )


def downgrade() -> None:
    """Remove auth_method from refresh_tokens."""
    if column_exists('refresh_tokens', 'auth_method'):
        op.drop_column('refresh_tokens', 'auth_method')
