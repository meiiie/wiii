"""Create missing character tables for living character state.

Revision ID: 038
Revises: 037
Create Date: 2026-03-07

Why this exists:
- Production/local code paths have relied on wiii_character_blocks and
  wiii_experiences since Sprint 93.
- Some databases reached head revision without ever having those tables.
- This migration is intentionally idempotent and only creates the tables when
  they are missing.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def upgrade() -> None:
    if not _table_exists("wiii_character_blocks"):
        op.create_table(
            "wiii_character_blocks",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
            sa.Column("char_limit", sa.Integer(), nullable=False, server_default=sa.text("1000")),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("user_id", sa.Text(), nullable=False, server_default=sa.text("'__global__'")),
            sa.Column(
                "organization_id",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'default'"),
            ),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "label", name="uq_character_blocks_user_label"),
        )
        op.create_index(
            "idx_character_blocks_user_id",
            "wiii_character_blocks",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "idx_character_blocks_user_label",
            "wiii_character_blocks",
            ["user_id", "label"],
            unique=False,
        )
        op.create_index(
            "idx_character_blocks_org_id",
            "wiii_character_blocks",
            ["organization_id"],
            unique=False,
        )

    if not _table_exists("wiii_experiences"):
        op.create_table(
            "wiii_experiences",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("experience_type", sa.Text(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("importance", sa.Float(), nullable=False, server_default=sa.text("0.5")),
            sa.Column("user_id", sa.Text(), nullable=True),
            sa.Column(
                "organization_id",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'default'"),
            ),
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint("importance >= 0.0 AND importance <= 1.0", name="ck_wiii_experiences_importance"),
        )
        op.create_index(
            "idx_experiences_user_id",
            "wiii_experiences",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "idx_experiences_org_id",
            "wiii_experiences",
            ["organization_id"],
            unique=False,
        )
        op.create_index(
            "idx_experiences_created_at",
            "wiii_experiences",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    if _table_exists("wiii_experiences"):
        op.drop_index("idx_experiences_created_at", table_name="wiii_experiences")
        op.drop_index("idx_experiences_org_id", table_name="wiii_experiences")
        op.drop_index("idx_experiences_user_id", table_name="wiii_experiences")
        op.drop_table("wiii_experiences")

    if _table_exists("wiii_character_blocks"):
        op.drop_index("idx_character_blocks_org_id", table_name="wiii_character_blocks")
        op.drop_index("idx_character_blocks_user_label", table_name="wiii_character_blocks")
        op.drop_index("idx_character_blocks_user_id", table_name="wiii_character_blocks")
        op.drop_table("wiii_character_blocks")
