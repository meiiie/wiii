-- ============================================
-- DEBUG QUERIES FOR SQL TEAM
-- Run these on Neon PostgreSQL database
-- ============================================

-- Query 1: Check if knowledge_embeddings table has data
SELECT 
    COUNT(*) as total_rows,
    COUNT(DISTINCT document_id) as unique_documents
FROM knowledge_embeddings;

-- Query 2: List all documents
SELECT DISTINCT 
    document_id, 
    COUNT(*) as chunk_count
FROM knowledge_embeddings 
GROUP BY document_id
ORDER BY chunk_count DESC;

-- Query 3: Check Rule 15 / COLREGs content
SELECT 
    id,
    document_id,
    title,
    page_number,
    LEFT(content, 200) as content_preview
FROM knowledge_embeddings 
WHERE 
    content ILIKE '%rule 15%' 
    OR content ILIKE '%crossing%'
    OR title ILIKE '%rule 15%'
    OR title ILIKE '%colregs%'
LIMIT 10;

-- Query 4: Check embedding dimensions
SELECT 
    id,
    array_length(embedding, 1) as embedding_dim
FROM knowledge_embeddings 
LIMIT 5;

-- Query 5: Check search_vector column (for sparse search)
SELECT 
    id,
    document_id,
    CASE WHEN search_vector IS NULL THEN 'NULL' ELSE 'EXISTS' END as search_vector_status
FROM knowledge_embeddings 
LIMIT 10;

-- Query 6: Check semantic_memories table (for user facts)
SELECT 
    COUNT(*) as total_memories,
    COUNT(DISTINCT user_id) as unique_users
FROM semantic_memories;

-- Query 7: Check specific test user memories
SELECT 
    id,
    user_id,
    content,
    memory_type,
    created_at
FROM semantic_memories 
WHERE user_id = 'test_user_refactor_check'
ORDER BY created_at DESC
LIMIT 10;

-- Query 8: Check chat_messages for test user
SELECT 
    COUNT(*) as message_count,
    MIN(created_at) as first_message,
    MAX(created_at) as last_message
FROM chat_messages 
WHERE user_id = 'test_user_refactor_check';
