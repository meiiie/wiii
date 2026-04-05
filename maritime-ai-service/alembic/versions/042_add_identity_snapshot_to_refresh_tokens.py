"""042: Add identity_snapshot to refresh_tokens

Persist additive Identity V2 claims alongside refresh tokens so refreshed
access tokens preserve host-local role context and platform-role separation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :table_name AND column_name = :column_name"
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()

    if not _column_exists(conn, "refresh_tokens", "identity_snapshot"):
        op.add_column(
            "refresh_tokens",
            sa.Column(
                "identity_snapshot",
                JSONB(),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, "refresh_tokens", "identity_snapshot"):
        op.drop_column("refresh_tokens", "identity_snapshot")
