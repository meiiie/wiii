"""047: create session_events

Append-only event log per chat session. Phase 5 of the runtime migration
epic (#207). Borrows the Anthropic Managed Agents pattern: harness =
stateless control loop, session = durable event log, sandbox = pluggable
execution. The log lives outside the model context window so wake / replay
flows can rebuild conversation state without polluting prompts.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "047"
down_revision = "046"
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
    if _table_exists(conn, "session_events"):
        return

    op.create_table(
        "session_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("org_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "seq", name="session_events_seq_unique"),
    )

    op.create_index(
        "session_events_session_seq",
        "session_events",
        ["session_id", "seq"],
    )
    op.create_index(
        "session_events_org_session",
        "session_events",
        ["org_id", "session_id"],
    )


def downgrade():
    op.drop_index("session_events_org_session", table_name="session_events")
    op.drop_index("session_events_session_seq", table_name="session_events")
    op.drop_table("session_events")
