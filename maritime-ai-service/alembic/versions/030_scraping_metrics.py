"""Sprint 190: Scraping Metrics Table

Tracks per-backend scraping performance for strategy optimization.
Used by ScrapingStrategyManager to make data-driven backend selection.

Revision ID: 030
Revises: 029
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS scraping_metrics (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            platform_id TEXT NOT NULL,
            backend TEXT NOT NULL,
            query TEXT,
            url TEXT,
            success BOOLEAN NOT NULL DEFAULT FALSE,
            result_count INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            error_message TEXT,
            organization_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_scraping_metrics_platform_created
        ON scraping_metrics(platform_id, created_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_scraping_metrics_backend
        ON scraping_metrics(backend, created_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_scraping_metrics_org
        ON scraping_metrics(organization_id, created_at);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_scraping_metrics_org;")
    op.execute("DROP INDEX IF EXISTS idx_scraping_metrics_backend;")
    op.execute("DROP INDEX IF EXISTS idx_scraping_metrics_platform_created;")
    op.execute("DROP TABLE IF EXISTS scraping_metrics;")
