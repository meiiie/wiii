"""041: Create admin_runtime_settings table

Stores persisted system-level runtime policy snapshots such as the
admin-managed LLM runtime configuration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name = 'admin_runtime_settings'"
        )
    )
    if result.fetchone() is None:
        op.create_table(
            "admin_runtime_settings",
            sa.Column("key", sa.Text(), nullable=False),
            sa.Column("settings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.PrimaryKeyConstraint("key"),
        )
        op.create_index(
            "ix_admin_runtime_settings_updated_at",
            "admin_runtime_settings",
            ["updated_at"],
        )


def downgrade():
    op.drop_index(
        "ix_admin_runtime_settings_updated_at",
        table_name="admin_runtime_settings",
    )
    op.drop_table("admin_runtime_settings")
