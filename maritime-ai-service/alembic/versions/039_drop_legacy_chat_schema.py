"""Drop legacy chat schema and consolidate everything on chat_history.

Revision ID: 039
Revises: 038
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE indexname = :index_name)"
        ),
        {"index_name": index_name},
    )
    return bool(result.scalar())


def _ensure_chat_history_table() -> None:
    if _table_exists("chat_history"):
        return

    op.create_table(
        "chat_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("organization_id", sa.Text(), nullable=True),
        sa.Column("user_name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_chat_history_user_id", "chat_history", ["user_id"], unique=False)
    op.create_index("idx_chat_history_session_id", "chat_history", ["session_id"], unique=False)
    op.create_index("idx_chat_history_created_at", "chat_history", ["created_at"], unique=False)
    op.create_index("idx_chat_history_is_blocked", "chat_history", ["is_blocked"], unique=False)
    op.create_index("idx_chat_history_org_id", "chat_history", ["organization_id"], unique=False)


def _create_legacy_tables() -> None:
    if not _table_exists("chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("user_name", sa.Text(), nullable=True),
            sa.Column("organization_id", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("session_id"),
        )
        op.create_index("idx_chat_sessions_user_id", "chat_sessions", ["user_id"], unique=False)
        op.create_index("idx_chat_sessions_org_id", "chat_sessions", ["organization_id"], unique=False)
        op.create_index(
            "idx_chat_sessions_user_org",
            "chat_sessions",
            ["user_id", "organization_id"],
            unique=False,
        )

    if not _table_exists("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=True),
            sa.Column("organization_id", sa.Text(), nullable=True),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "is_blocked",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("block_reason", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(
                ["session_id"],
                ["chat_sessions.session_id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_chat_messages_session_id",
            "chat_messages",
            ["session_id"],
            unique=False,
        )
        op.create_index(
            "idx_chat_messages_created_at",
            "chat_messages",
            ["created_at"],
            unique=False,
        )
        op.create_index(
            "idx_chat_messages_is_blocked",
            "chat_messages",
            ["is_blocked"],
            unique=False,
        )
        op.create_index(
            "idx_chat_messages_user_id",
            "chat_messages",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            "idx_chat_messages_org_id",
            "chat_messages",
            ["organization_id"],
            unique=False,
        )
        op.create_index(
            "idx_chat_messages_user_org",
            "chat_messages",
            ["user_id", "organization_id"],
            unique=False,
        )


def upgrade() -> None:
    _ensure_chat_history_table()

    if not _column_exists("chat_history", "user_name"):
        op.add_column("chat_history", sa.Column("user_name", sa.Text(), nullable=True))

    if _table_exists("chat_sessions") and _column_exists("chat_sessions", "user_name"):
        op.execute(
            sa.text(
                """
                UPDATE chat_history AS h
                SET user_name = s.user_name
                FROM chat_sessions AS s
                WHERE h.session_id = s.session_id
                  AND NULLIF(s.user_name, '') IS NOT NULL
                  AND NULLIF(h.user_name, '') IS NULL
                """
            )
        )

    if _table_exists("chat_messages"):
        user_id_expr = (
            "m.user_id"
            if _column_exists("chat_messages", "user_id")
            else (
                "s.user_id"
                if _table_exists("chat_sessions") and _column_exists("chat_sessions", "user_id")
                else "m.session_id::text"
            )
        )
        org_expr_parts = []
        if _column_exists("chat_messages", "organization_id"):
            org_expr_parts.append("m.organization_id")
        if _table_exists("chat_sessions") and _column_exists("chat_sessions", "organization_id"):
            org_expr_parts.append("s.organization_id")
        org_expr = (
            f"COALESCE({', '.join(org_expr_parts)})"
            if org_expr_parts
            else "NULL"
        )
        is_blocked_expr = (
            "COALESCE(m.is_blocked, FALSE)"
            if _column_exists("chat_messages", "is_blocked")
            else "FALSE"
        )
        block_reason_expr = (
            "m.block_reason"
            if _column_exists("chat_messages", "block_reason")
            else "NULL"
        )
        user_name_expr = (
            "s.user_name"
            if _table_exists("chat_sessions") and _column_exists("chat_sessions", "user_name")
            else "NULL"
        )
        join_sql = (
            "LEFT JOIN chat_sessions AS s ON s.session_id = m.session_id"
            if _table_exists("chat_sessions")
            else ""
        )

        op.execute(
            sa.text(
                f"""
                INSERT INTO chat_history (
                    id,
                    user_id,
                    session_id,
                    role,
                    content,
                    created_at,
                    is_blocked,
                    block_reason,
                    organization_id,
                    user_name
                )
                SELECT
                    m.id,
                    {user_id_expr},
                    m.session_id,
                    m.role,
                    m.content,
                    m.created_at,
                    {is_blocked_expr},
                    {block_reason_expr},
                    {org_expr},
                    {user_name_expr}
                FROM chat_messages AS m
                {join_sql}
                WHERE NOT EXISTS (
                    SELECT 1 FROM chat_history AS h WHERE h.id = m.id
                )
                """
            )
        )

    if _table_exists("chat_messages"):
        op.drop_table("chat_messages")
    if _table_exists("chat_sessions"):
        op.drop_table("chat_sessions")


def downgrade() -> None:
    _create_legacy_tables()

    if _table_exists("chat_history"):
        op.execute(
            sa.text(
                """
                INSERT INTO chat_sessions (
                    session_id,
                    user_id,
                    user_name,
                    organization_id,
                    created_at
                )
                SELECT DISTINCT ON (session_id)
                    session_id,
                    user_id,
                    user_name,
                    organization_id,
                    created_at
                FROM chat_history
                ORDER BY session_id, created_at ASC
                ON CONFLICT (session_id) DO NOTHING
                """
            )
        )

        op.execute(
            sa.text(
                """
                INSERT INTO chat_messages (
                    id,
                    session_id,
                    user_id,
                    organization_id,
                    role,
                    content,
                    created_at,
                    is_blocked,
                    block_reason
                )
                SELECT
                    id,
                    session_id,
                    user_id,
                    organization_id,
                    role,
                    content,
                    created_at,
                    COALESCE(is_blocked, FALSE),
                    block_reason
                FROM chat_history
                ON CONFLICT (id) DO NOTHING
                """
            )
        )

        if _column_exists("chat_history", "user_name"):
            op.drop_column("chat_history", "user_name")

