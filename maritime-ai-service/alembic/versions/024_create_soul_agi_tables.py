"""024: Create Soul AGI tables

Sprint 176: "Wiii Soul AGI" — All phases

Creates tables for:
- wiii_briefings: Briefing delivery records
- wiii_user_routines: User behavior patterns
- wiii_reflections: Weekly reflection entries
- wiii_goals: Dynamic goal lifecycle
- wiii_proactive_messages: Proactive message log
- wiii_proactive_preferences: User opt-out state
- wiii_autonomy_state: Autonomy level + graduation state

All tables are idempotent (IF NOT EXISTS).

Revision ID: 024
Revises: 023
"""

from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # =========================================================================
    # Briefings (Phase 2A)
    # =========================================================================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS wiii_briefings (
            id TEXT PRIMARY KEY,
            briefing_type TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            weather_summary TEXT DEFAULT '',
            news_highlights JSONB DEFAULT '[]',
            delivered_to JSONB DEFAULT '[]',
            organization_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_briefings_type_date
        ON wiii_briefings (briefing_type, created_at DESC)
    """))

    # =========================================================================
    # User Routines (Phase 3B)
    # =========================================================================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS wiii_user_routines (
            user_id TEXT PRIMARY KEY,
            typical_active_hours JSONB DEFAULT '[]',
            preferred_briefing_time INTEGER DEFAULT 7,
            conversation_frequency FLOAT DEFAULT 0.0,
            common_topics JSONB DEFAULT '[]',
            last_seen TIMESTAMPTZ,
            total_messages INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    # =========================================================================
    # Reflections (Phase 4A)
    # =========================================================================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS wiii_reflections (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL DEFAULT '',
            insights JSONB DEFAULT '[]',
            goals_next_week JSONB DEFAULT '[]',
            patterns_noticed JSONB DEFAULT '[]',
            emotion_trend TEXT DEFAULT '',
            reflection_date TIMESTAMPTZ DEFAULT NOW(),
            organization_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_reflections_date
        ON wiii_reflections (reflection_date DESC)
    """))

    # =========================================================================
    # Goals (Phase 4B)
    # =========================================================================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS wiii_goals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'proposed',
            priority TEXT DEFAULT 'medium',
            progress FLOAT DEFAULT 0.0,
            source TEXT DEFAULT 'reflection',
            milestones JSONB DEFAULT '[]',
            completed_milestones JSONB DEFAULT '[]',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            target_date TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            organization_id TEXT,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_goals_status
        ON wiii_goals (status)
    """))

    # =========================================================================
    # Proactive Messages (Phase 5A)
    # =========================================================================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS wiii_proactive_messages (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'messenger',
            content TEXT NOT NULL DEFAULT '',
            trigger TEXT DEFAULT '',
            priority FLOAT DEFAULT 0.5,
            delivered BOOLEAN DEFAULT false,
            delivered_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_proactive_user_date
        ON wiii_proactive_messages (user_id, created_at DESC)
    """))

    # =========================================================================
    # Proactive Preferences (Phase 5A)
    # =========================================================================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS wiii_proactive_preferences (
            user_id TEXT PRIMARY KEY,
            opted_out BOOLEAN DEFAULT false,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))

    # =========================================================================
    # Autonomy State (Phase 5B)
    # =========================================================================
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS wiii_autonomy_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS wiii_autonomy_state"))
    conn.execute(sa.text("DROP TABLE IF EXISTS wiii_proactive_preferences"))
    conn.execute(sa.text("DROP TABLE IF EXISTS wiii_proactive_messages"))
    conn.execute(sa.text("DROP TABLE IF EXISTS wiii_goals"))
    conn.execute(sa.text("DROP TABLE IF EXISTS wiii_reflections"))
    conn.execute(sa.text("DROP TABLE IF EXISTS wiii_user_routines"))
    conn.execute(sa.text("DROP TABLE IF EXISTS wiii_briefings"))
