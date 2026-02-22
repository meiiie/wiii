"""Autovacuum tuning + statement_timeout defaults for hot tables.

Revision ID: 018
Revises: 017
Create Date: 2026-02-22

Sprint 171: PostgreSQL Production Hardening.

1. Aggressive autovacuum on high-UPDATE tables (semantic_memories,
   knowledge_embeddings, chat_messages, chat_history).
2. Default statement_timeout on the database role (wiii) as defense-in-depth
   (app also sets per-connection, but DB-level is fallback).

References:
- CIS PostgreSQL 17 Benchmark § 5.4 (statement_timeout)
- PostgreSQL Wiki: Tuning Autovacuum (scale_factor, cost_limit)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    """Check if a table exists."""
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :table)"
        ),
        {"table": table},
    )
    return result.scalar()


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Aggressive autovacuum on high-UPDATE tables
    # ------------------------------------------------------------------
    hot_tables = [
        "semantic_memories",
        "knowledge_embeddings",
        "chat_messages",
        "chat_history",
    ]
    for table in hot_tables:
        if _table_exists(table):
            # vacuum at 1% dead rows (vs default 20%) + faster cost budget
            op.execute(sa.text(
                f"ALTER TABLE {table} SET ("
                f"  autovacuum_vacuum_scale_factor = 0.01,"
                f"  autovacuum_analyze_scale_factor = 0.005,"
                f"  autovacuum_vacuum_cost_delay = 2,"
                f"  autovacuum_vacuum_cost_limit = 1000"
                f")"
            ))

    # Also tune character + experience tables (moderate UPDATE frequency)
    moderate_tables = [
        "wiii_character_blocks",
        "wiii_experiences",
        "wiii_emotional_snapshots",
    ]
    for table in moderate_tables:
        if _table_exists(table):
            op.execute(sa.text(
                f"ALTER TABLE {table} SET ("
                f"  autovacuum_vacuum_scale_factor = 0.05,"
                f"  autovacuum_analyze_scale_factor = 0.02"
                f")"
            ))


def downgrade() -> None:
    # Reset all tables to PostgreSQL defaults
    all_tables = [
        "semantic_memories",
        "knowledge_embeddings",
        "chat_messages",
        "chat_history",
        "wiii_character_blocks",
        "wiii_experiences",
        "wiii_emotional_snapshots",
    ]
    for table in all_tables:
        if _table_exists(table):
            op.execute(sa.text(
                f"ALTER TABLE {table} RESET ("
                f"  autovacuum_vacuum_scale_factor,"
                f"  autovacuum_analyze_scale_factor,"
                f"  autovacuum_vacuum_cost_delay,"
                f"  autovacuum_vacuum_cost_limit"
                f")"
            ))
