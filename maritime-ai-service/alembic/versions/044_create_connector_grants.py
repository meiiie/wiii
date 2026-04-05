"""044: create connector_grants

Durable connector/workspace grants keep host-linked authority separate from
Wiii's canonical user identity. They model connected workspaces, not live page
sessions.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name = :table_name"
        ),
        {"table_name": table_name},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn, "connector_grants"):
        return

    op.create_table(
        "connector_grants",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("connector_id", sa.Text(), nullable=False),
        sa.Column("grant_key", sa.Text(), nullable=False),
        sa.Column("host_type", sa.Text(), nullable=False),
        sa.Column("host_name", sa.Text(), nullable=True),
        sa.Column("host_user_id", sa.Text(), nullable=True),
        sa.Column("host_workspace_id", sa.Text(), nullable=True),
        sa.Column("host_organization_id", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Text(), nullable=True),
        sa.Column(
            "granted_capabilities",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "auth_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "grant_key", name="uq_connector_grants_user_key"),
    )
    op.create_index("ix_connector_grants_user_id", "connector_grants", ["user_id"])
    op.create_index("ix_connector_grants_connector_id", "connector_grants", ["connector_id"])


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, "connector_grants"):
        return
    op.drop_index("ix_connector_grants_connector_id", table_name="connector_grants")
    op.drop_index("ix_connector_grants_user_id", table_name="connector_grants")
    op.drop_table("connector_grants")
