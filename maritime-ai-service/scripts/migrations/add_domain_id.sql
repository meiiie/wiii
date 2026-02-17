-- =============================================================================
-- Migration: Add domain_id column for multi-domain knowledge isolation
-- Pattern: Shared DB + domain_id column (Pool pattern)
-- Reference: AWS multi-tenant RAG, pgvector best practices
-- =============================================================================

-- knowledge_embeddings: Add domain_id with default 'maritime'
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS domain_id VARCHAR(50) DEFAULT 'maritime' NOT NULL;

-- Index for domain-filtered queries
CREATE INDEX IF NOT EXISTS idx_ke_domain ON knowledge_embeddings(domain_id);

-- Composite index for domain + search_vector (sparse search performance)
CREATE INDEX IF NOT EXISTS idx_ke_domain_search ON knowledge_embeddings(domain_id)
WHERE search_vector IS NOT NULL;

-- semantic_memories: Add domain_id (nullable for backward compat)
ALTER TABLE semantic_memories
ADD COLUMN IF NOT EXISTS domain_id VARCHAR(50) DEFAULT 'maritime';

CREATE INDEX IF NOT EXISTS idx_sm_domain ON semantic_memories(domain_id);

-- Backfill existing data as 'maritime'
UPDATE knowledge_embeddings SET domain_id = 'maritime' WHERE domain_id IS NULL;
UPDATE semantic_memories SET domain_id = 'maritime' WHERE domain_id IS NULL;
