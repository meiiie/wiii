"""Create RLS policies (dormant until manually enabled)

Revision ID: 023
Revises: 022
Create Date: 2026-02-23

Sprint 175b: "Hàng Rào Thép" — RLS Foundation

Creates Row-Level Security policies on org-scoped tables.
Policies are DORMANT — they only activate when:
  1. ALTER TABLE ... ENABLE ROW LEVEL SECURITY is run (manual)
  2. App sets session variable: SET app.current_org_id = 'org_id'

Policy logic:
- Allow access when organization_id matches app.current_org_id
- Allow access when app.current_org_id is empty/NULL (no org context)
- This ensures backward compat: no org context = see everything

To activate RLS in production, run: python scripts/enable_rls.py
"""
from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Check if table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if column exists in table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def _policy_exists(table_name: str, policy_name: str) -> bool:
    """Check if RLS policy exists."""
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT 1 FROM pg_policies WHERE tablename = :table AND policyname = :policy"
    ), {"table": table_name, "policy": policy_name})
    return result.fetchone() is not None


# Org-scoped tables for RLS
ORG_SCOPED_TABLES = [
    "semantic_memories",
    "chat_history",
    "chat_sessions",
    "chat_messages",
    "learning_profile",
    "scheduled_tasks",
    "wiii_emotional_snapshots",
    "wiii_skills",
    "wiii_journal",
    "wiii_browsing_log",
    "wiii_heartbeat_audit",
    "wiii_pending_actions",
    "thread_views",
    "user_preferences",
]

POLICY_TEMPLATE = """
CREATE POLICY org_isolation_{table} ON {table}
    FOR ALL
    USING (
        organization_id = current_setting('app.current_org_id', true)
        OR current_setting('app.current_org_id', true) IS NULL
        OR current_setting('app.current_org_id', true) = ''
    )
"""


def upgrade() -> None:
    """Create dormant RLS policies on org-scoped tables."""
    conn = op.get_bind()

    # Step 1: Create custom GUC variable (idempotent)
    # current_setting('app.current_org_id', true) returns NULL if not set
    # The 'true' flag means "return NULL on missing" instead of error

    # Step 2: Create RLS policies (dormant until ENABLE ROW LEVEL SECURITY)
    for table in ORG_SCOPED_TABLES:
        if not _table_exists(table):
            continue
        if not _column_exists(table, "organization_id"):
            continue

        policy_name = f"org_isolation_{table}"
        if _policy_exists(table, policy_name):
            continue  # Already exists

        conn.execute(text(POLICY_TEMPLATE.format(table=table)))
        print(f"  Created RLS policy: {policy_name}")


def downgrade() -> None:
    """Drop RLS policies."""
    conn = op.get_bind()

    for table in ORG_SCOPED_TABLES:
        if not _table_exists(table):
            continue

        policy_name = f"org_isolation_{table}"
        if not _policy_exists(table, policy_name):
            continue

        # Disable RLS first (in case it was enabled)
        conn.execute(text(
            f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"
        ))
        conn.execute(text(
            f"DROP POLICY {policy_name} ON {table}"
        ))
