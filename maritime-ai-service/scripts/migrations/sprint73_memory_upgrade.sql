-- Sprint 73: Living Memory System — DB Migration
-- Additive only. Safe on live DB. No destructive changes.

-- 1. Add access_count column for importance decay reinforcement
ALTER TABLE semantic_memories ADD COLUMN IF NOT EXISTS access_count INTEGER DEFAULT 0;

-- 2. Add first_seen column for revision tracking
ALTER TABLE semantic_memories ADD COLUMN IF NOT EXISTS first_seen TIMESTAMPTZ DEFAULT NOW();

-- 3. Backfill first_seen from created_at for existing rows
UPDATE semantic_memories SET first_seen = created_at WHERE first_seen IS NULL;

-- 4. Ensure last_accessed exists (may already exist from v0.5 insight upgrade)
ALTER TABLE semantic_memories ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMPTZ;

-- 5. Composite index for importance decay queries
-- Filters on memory_type='user_fact' + sorts by importance desc, last_accessed desc
CREATE INDEX IF NOT EXISTS idx_sm_importance_decay
  ON semantic_memories(user_id, memory_type, importance DESC, last_accessed DESC NULLS LAST)
  WHERE memory_type = 'user_fact';

-- 6. Index for fast access_count updates
CREATE INDEX IF NOT EXISTS idx_sm_user_fact_type
  ON semantic_memories(user_id, (metadata->>'fact_type'))
  WHERE memory_type = 'user_fact';
