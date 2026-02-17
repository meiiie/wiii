-- =============================================================================
-- Migration: Add missing columns to knowledge_embeddings table
-- These columns are used by the codebase but were never added via migration.
-- Must run AFTER create_knowledge_embeddings_table.sql
-- =============================================================================

-- Content column for storing text chunks
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS content TEXT DEFAULT '';

-- Full-text search vector (sparse search via tsvector)
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- Document reference and page tracking
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS document_id VARCHAR(255) DEFAULT '';

ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS page_number INTEGER DEFAULT 0;

ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS chunk_index INTEGER DEFAULT 0;

-- Content type classification (text, table, heading, diagram_reference, formula)
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS content_type VARCHAR(50) DEFAULT 'text';

-- Confidence score for chunk quality (0.0 - 1.0)
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS confidence_score FLOAT DEFAULT 1.0;

-- Image URL for evidence images (Supabase/MinIO)
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT '';

-- Metadata JSONB for section_hierarchy, extraction_method, etc.
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Source identifier (document_id + page + chunk)
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS source VARCHAR(500) DEFAULT '';

-- Bounding boxes for source highlighting (Feature: source-highlight-citation)
ALTER TABLE knowledge_embeddings
ADD COLUMN IF NOT EXISTS bounding_boxes JSONB DEFAULT NULL;

-- =============================================================================
-- INDEXES for new columns
-- =============================================================================

-- GIN index for full-text search
CREATE INDEX IF NOT EXISTS idx_ke_search_vector
ON knowledge_embeddings USING gin(search_vector);

-- Index on document_id for document-level queries
CREATE INDEX IF NOT EXISTS idx_ke_document_id
ON knowledge_embeddings(document_id);

-- Composite index for chunk lookup (document + page + chunk)
CREATE INDEX IF NOT EXISTS idx_ke_doc_page_chunk
ON knowledge_embeddings(document_id, page_number, chunk_index);

-- Index on content_type for filtered searches
CREATE INDEX IF NOT EXISTS idx_ke_content_type
ON knowledge_embeddings(content_type);

-- =============================================================================
-- TRIGGER: Auto-update search_vector on content change
-- =============================================================================

CREATE OR REPLACE FUNCTION update_knowledge_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector = to_tsvector('simple', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ke_search_vector ON knowledge_embeddings;
CREATE TRIGGER trg_ke_search_vector
    BEFORE INSERT OR UPDATE OF content ON knowledge_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION update_knowledge_search_vector();

-- Backfill search_vector for existing rows
UPDATE knowledge_embeddings
SET search_vector = to_tsvector('simple', COALESCE(content, ''))
WHERE search_vector IS NULL AND content IS NOT NULL AND content != '';

-- =============================================================================
-- VERIFICATION
-- =============================================================================
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'knowledge_embeddings'
-- ORDER BY ordinal_position;
