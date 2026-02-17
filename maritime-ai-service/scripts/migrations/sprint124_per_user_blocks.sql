-- Sprint 124: Per-User Character Blocks — User Isolation
-- Adds user_id column to wiii_character_blocks so each user gets their own blocks.
-- Existing rows get '__global__' as default (backward compat).

-- Step 1: Add user_id column with default for existing rows
ALTER TABLE wiii_character_blocks
  ADD COLUMN IF NOT EXISTS user_id VARCHAR(255) NOT NULL DEFAULT '__global__';

-- Step 2: Drop old unique constraint on label alone
ALTER TABLE wiii_character_blocks
  DROP CONSTRAINT IF EXISTS wiii_character_blocks_label_key;

-- Step 3: New unique constraint: (user_id, label) — each user has their own set
ALTER TABLE wiii_character_blocks
  ADD CONSTRAINT wiii_character_blocks_user_label_key UNIQUE (user_id, label);

-- Step 4: Index for query performance
CREATE INDEX IF NOT EXISTS idx_character_blocks_user_id
  ON wiii_character_blocks(user_id);
