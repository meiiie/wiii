"""027: Create auth_events table

Sprint 176: "Bao Mat Dang Nhap" — Auth Hardening

Stores auth audit events: login, logout, token_refresh, token_revoked,
token_replay_detected, identity_linked, identity_unlinked, login_failed, auth_failed.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Check if table already exists (idempotent)
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name = 'auth_events'"
    ))
    if result.fetchone() is not None:
        return

    op.create_table(
        "auth_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_auth_events_user", "auth_events", ["user_id"])
    op.create_index("ix_auth_events_type", "auth_events", ["event_type"])
    op.create_index("ix_auth_events_created", "auth_events", ["created_at"])


def downgrade():
    op.drop_index("ix_auth_events_created", table_name="auth_events")
    op.drop_index("ix_auth_events_type", table_name="auth_events")
    op.drop_index("ix_auth_events_user", table_name="auth_events")
    op.drop_table("auth_events")
