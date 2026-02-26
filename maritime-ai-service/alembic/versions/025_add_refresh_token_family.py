"""025: Add refresh token family_id for replay detection

Sprint 176: "Bao Mat Dang Nhap" — Auth Hardening

Adds family_id column to refresh_tokens for refresh-token rotation
replay detection. NULL = legacy tokens (no detection).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Check if column already exists (idempotent)
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'refresh_tokens' AND column_name = 'family_id'"
    ))
    if result.fetchone() is None:
        op.add_column("refresh_tokens", sa.Column("family_id", sa.Text(), nullable=True))
        op.create_index("ix_refresh_family", "refresh_tokens", ["family_id"])


def downgrade():
    op.drop_index("ix_refresh_family", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "family_id")
