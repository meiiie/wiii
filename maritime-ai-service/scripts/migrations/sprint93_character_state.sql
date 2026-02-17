-- =============================================================================
-- Sprint 93: Living Character Card — Database Migration
-- Wiii's self-evolving character state tables
--
-- Additive only. Safe on live DB. No destructive changes.
-- Run: psql -f scripts/migrations/sprint93_character_state.sql
-- =============================================================================

-- Enable UUID generation (should already exist)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- TABLE: wiii_character_blocks
-- Self-editable memory blocks for Wiii's living character state.
-- Global (not per-user) — this is Wiii's own personality state.
-- Inspired by Letta/MemGPT Block model with version tracking.
-- =============================================================================

CREATE TABLE IF NOT EXISTS wiii_character_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Block identity
    label VARCHAR(100) NOT NULL UNIQUE,  -- 'learned_lessons', 'favorite_topics', etc.
    content TEXT NOT NULL DEFAULT '',     -- Markdown/text content (self-edited by AI)
    char_limit INT NOT NULL DEFAULT 1000, -- Max characters for this block

    -- Version tracking (optimistic locking)
    version INT NOT NULL DEFAULT 1,

    -- Additional metadata
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast label lookup (UNIQUE constraint already creates an index)
-- No additional indexes needed for this small table

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_character_block_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_character_block_timestamp ON wiii_character_blocks;
CREATE TRIGGER trigger_update_character_block_timestamp
    BEFORE UPDATE ON wiii_character_blocks
    FOR EACH ROW
    EXECUTE FUNCTION update_character_block_timestamp();


-- =============================================================================
-- TABLE: wiii_experiences
-- Experience log — milestones, learnings, funny moments, feedback.
-- Global (not per-user) — Wiii's collective experience.
-- =============================================================================

CREATE TABLE IF NOT EXISTS wiii_experiences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Experience details
    experience_type VARCHAR(50) NOT NULL,  -- 'milestone', 'learning', 'funny', 'feedback', 'reflection'
    content TEXT NOT NULL,                  -- What happened
    importance FLOAT DEFAULT 0.5,           -- 0.0-1.0

    -- Context
    user_id VARCHAR(255),                   -- Which user triggered this (optional)
    metadata JSONB DEFAULT '{}',

    -- Timestamp
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for recent experiences query
CREATE INDEX IF NOT EXISTS idx_wiii_experiences_created
    ON wiii_experiences(created_at DESC);

-- Index for filtering by type
CREATE INDEX IF NOT EXISTS idx_wiii_experiences_type
    ON wiii_experiences(experience_type, created_at DESC);

-- Index for user-specific experience lookup
CREATE INDEX IF NOT EXISTS idx_wiii_experiences_user
    ON wiii_experiences(user_id, created_at DESC)
    WHERE user_id IS NOT NULL;


-- =============================================================================
-- SEED DATA: Default character blocks (empty, ready for AI to fill)
-- =============================================================================

INSERT INTO wiii_character_blocks (label, content, char_limit)
VALUES
    ('learned_lessons', '', 1500),
    ('favorite_topics', '', 800),
    ('user_patterns', '', 800),
    ('self_notes', '', 1000)
ON CONFLICT (label) DO NOTHING;


-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- SELECT * FROM wiii_character_blocks;
-- SELECT COUNT(*) FROM wiii_experiences;

COMMENT ON TABLE wiii_character_blocks IS 'Wiii living character state — self-editable memory blocks (Sprint 93)';
COMMENT ON TABLE wiii_experiences IS 'Wiii experience log — milestones, learnings, feedback (Sprint 93)';
