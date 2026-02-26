"""026: Create otp_link_codes table

Sprint 176: "Bao Mat Dang Nhap" — Auth Hardening

Moves OTP codes from in-memory dict to persistent DB table.
Cluster-safe, survives restarts.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Check if table already exists (idempotent)
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'otp_link_codes'"
    ))
    if result.fetchone() is not None:
        return

    op.create_table(
        "otp_link_codes",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("linked_platform_sender_id", sa.Text(), nullable=True),
    )
    op.create_index("ix_otp_user_channel", "otp_link_codes", ["user_id", "channel_type"])
    op.create_index("ix_otp_expires", "otp_link_codes", ["expires_at"])


def downgrade():
    op.drop_index("ix_otp_expires", table_name="otp_link_codes")
    op.drop_index("ix_otp_user_channel", table_name="otp_link_codes")
    op.drop_table("otp_link_codes")
