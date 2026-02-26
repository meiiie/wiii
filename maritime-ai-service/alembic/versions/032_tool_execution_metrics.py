"""Sprint 191: Tool Execution Metrics Table

Tracks per-skill/tool execution metrics for intelligent selection
and performance monitoring. Used by SkillMetricsTracker.

Revision ID: 032
Revises: 031
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tool_execution_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            skill_id TEXT NOT NULL,
            skill_type TEXT NOT NULL,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            latency_ms INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            query_snippet TEXT,
            error_message TEXT,
            organization_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_metrics_skill
        ON tool_execution_metrics(skill_id, created_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_metrics_org
        ON tool_execution_metrics(organization_id, created_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_metrics_type
        ON tool_execution_metrics(skill_type, created_at);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tool_metrics_type;")
    op.execute("DROP INDEX IF EXISTS idx_tool_metrics_org;")
    op.execute("DROP INDEX IF EXISTS idx_tool_metrics_skill;")
    op.execute("DROP TABLE IF EXISTS tool_execution_metrics;")
