"""036: Create magic_link_tokens table for passwordless email auth.

Sprint 224: Magic Link Email Authentication
"""
from alembic import op
import sqlalchemy as sa

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "magic_link_tokens",
        sa.Column("token_hash", sa.Text, primary_key=True),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("ws_session_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_magic_link_email", "magic_link_tokens", ["email"])
    op.create_index("ix_magic_link_ws_session", "magic_link_tokens", ["ws_session_id"])
    op.create_index("ix_magic_link_expires", "magic_link_tokens", ["expires_at"])


def downgrade():
    op.drop_table("magic_link_tokens")
