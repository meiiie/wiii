"""Sprint 194c: Add updated_at column to otp_link_codes for exponential backoff.

Tracks last failed attempt time, enabling per-code cooldown periods.

Revision ID: 034
Revises: 033
"""
from alembic import op


# revision identifiers
revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE otp_link_codes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE otp_link_codes DROP COLUMN IF EXISTS updated_at")
