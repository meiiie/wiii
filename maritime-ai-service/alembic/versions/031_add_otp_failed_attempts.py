"""Sprint 192: Add failed_attempts column to otp_link_codes for brute-force lockout.

Also ensures created_at column exists (needed for rate limiting).

Revision ID: 031
Revises: 030
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE otp_link_codes ADD COLUMN IF NOT EXISTS failed_attempts INTEGER DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE otp_link_codes ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE otp_link_codes DROP COLUMN IF EXISTS failed_attempts")
    op.execute("ALTER TABLE otp_link_codes DROP COLUMN IF EXISTS created_at")
