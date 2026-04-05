"""043: Add platform_role to users

Splits Wiii platform authority from the legacy compatibility role so host-local
roles from LMS or other plugins do not need to overload `users.role`.
"""

from alembic import op
import sqlalchemy as sa


revision = "043"
down_revision = "042"
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

    if not _column_exists(conn, "users", "platform_role"):
        op.add_column(
            "users",
            sa.Column(
                "platform_role",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'user'"),
            ),
        )
        op.execute(
            """
            UPDATE users
            SET platform_role = 'platform_admin'
            WHERE LOWER(COALESCE(role, 'student')) = 'admin'
            """
        )


def downgrade():
    conn = op.get_bind()
    if _column_exists(conn, "users", "platform_role"):
        op.drop_column("users", "platform_role")
