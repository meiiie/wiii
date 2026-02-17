# Requirements Document

## Introduction

Nâng cấp hệ thống Multimodal RAG từ **"1 page = 1 chunk"** sang **"Semantic Chunking"** để cải thiện chất lượng tìm kiếm và giảm chi phí. Hiện tại, mỗi trang PDF được xử lý như một đơn vị duy nhất với 1 embedding, dẫn đến semantic search kém chính xác. Feature này sẽ chia text thành nhiều chunks có nghĩa (500-800 chars) với maritime-specific intelligence.

## Glossary

- **Semantic_Chunker**: Service chia text thành các chunks có nghĩa dựa trên ngữ cảnh
- **Content_Type**: Loại nội dung của chunk (text, table, heading, diagram_reference, formula)
- **Confidence_Score**: Điểm tin cậy của chunk (0.0-1.0) dựa trên chất lượng extraction
- **Maritime_Pattern**: Các pattern đặc thù cho tài liệu hàng hải (Điều, Khoản, Rule, etc.)
- **Chunk_Index**: Thứ tự của chunk trong một trang
- **Hybrid_Processing**: Kết hợp PyMuPDF (text-only) và Vision API (visual content)
- **Document_Hierarchy**: Cấu trúc phân cấp của tài liệu (Chương → Điều → Khoản → Điểm)

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the ingestion pipeline to split extracted text into semantic chunks, so that each chunk contains focused content for better search accuracy.

#### Acceptance Criteria

1. WHEN text is extracted from a PDF page THEN the Semantic_Chunker SHALL split it into chunks of 500-800 characters with 100 character overlap
2. WHEN splitting text THEN the Semantic_Chunker SHALL preserve sentence boundaries and avoid cutting mid-sentence
3. WHEN a page contains multiple content types THEN the Semantic_Chunker SHALL create separate chunks for each content type
4. WHEN chunking completes THEN the Ingestion_Pipeline SHALL generate one embedding per chunk instead of one per page
5. IF a chunk is smaller than 50 characters THEN the Semantic_Chunker SHALL merge it with adjacent chunk

### Requirement 2

**User Story:** As a system administrator, I want the system to detect content types in maritime documents, so that different content types can be processed appropriately.

#### Acceptance Criteria

1. WHEN processing a chunk THEN the Semantic_Chunker SHALL classify it as one of: text, table, heading, diagram_reference, formula
2. WHEN a chunk contains Markdown table syntax (| and ---) THEN the Semantic_Chunker SHALL classify it as table
3. WHEN a chunk contains maritime legal patterns (Điều, Khoản, Rule) THEN the Semantic_Chunker SHALL classify it as heading
4. WHEN a chunk references figures or diagrams (Hình, Sơ đồ, Figure) THEN the Semantic_Chunker SHALL classify it as diagram_reference
5. WHEN content type is detected THEN the Semantic_Chunker SHALL store it in the content_type column

### Requirement 3

**User Story:** As a system administrator, I want the system to calculate confidence scores for each chunk, so that low-quality extractions can be identified and handled.

#### Acceptance Criteria

1. WHEN a chunk is created THEN the Semantic_Chunker SHALL calculate a confidence_score between 0.0 and 1.0
2. WHEN a chunk has fewer than 50 characters THEN the confidence_score SHALL be reduced to 0.6 or lower
3. WHEN a chunk has more than 1000 characters THEN the confidence_score SHALL be reduced to 0.7 or lower
4. WHEN a chunk contains structured content (heading, table) THEN the confidence_score SHALL be boosted by 20%
5. WHEN storing the chunk THEN the Ingestion_Pipeline SHALL save the confidence_score in the database

### Requirement 4

**User Story:** As a system administrator, I want the database schema to support multiple chunks per page, so that semantic chunking data can be stored efficiently.

#### Acceptance Criteria

1. WHEN migration runs THEN the Neon_Database SHALL add column content_type (VARCHAR 50) to knowledge_embeddings table
2. WHEN migration runs THEN the Neon_Database SHALL add column confidence_score (FLOAT) to knowledge_embeddings table
3. WHEN migration runs THEN the Neon_Database SHALL create index on (document_id, page_number, chunk_index)
4. WHEN storing chunks THEN the Ingestion_Pipeline SHALL use chunk_index to order chunks within a page
5. IF migration fails THEN the Neon_Database SHALL rollback to previous schema state

### Requirement 5

**User Story:** As a system administrator, I want the system to extract document hierarchy from maritime documents, so that search results can include context about article/clause structure.

#### Acceptance Criteria

1. WHEN processing a chunk THEN the Semantic_Chunker SHALL detect article numbers (Điều X, Article X)
2. WHEN processing a chunk THEN the Semantic_Chunker SHALL detect clause numbers (Khoản X, Clause X)
3. WHEN processing a chunk THEN the Semantic_Chunker SHALL detect point identifiers (Điểm a, Point a)
4. WHEN processing a chunk THEN the Semantic_Chunker SHALL detect rule numbers (Rule X)
5. WHEN hierarchy is detected THEN the Semantic_Chunker SHALL store it in the metadata JSONB column

### Requirement 6

**User Story:** As a system administrator, I want configuration settings for chunking parameters, so that the system can be tuned for different document types.

#### Acceptance Criteria

1. WHEN the system initializes THEN the Config SHALL load CHUNK_SIZE setting (default 800)
2. WHEN the system initializes THEN the Config SHALL load CHUNK_OVERLAP setting (default 100)
3. WHEN the system initializes THEN the Config SHALL load MIN_CHUNK_SIZE setting (default 50)
4. WHEN the system initializes THEN the Config SHALL load DPI_OPTIMIZED setting (default 100)
5. WHEN settings are changed THEN the Semantic_Chunker SHALL use the new values without restart

### Requirement 7

**User Story:** As a developer, I want the chunking service to integrate seamlessly with the existing ingestion pipeline, so that the upgrade is backward compatible.

#### Acceptance Criteria

1. WHEN processing a page THEN the Ingestion_Pipeline SHALL call Semantic_Chunker after Vision extraction
2. WHEN storing chunks THEN the Ingestion_Pipeline SHALL maintain the existing image_url reference for all chunks from the same page
3. WHEN an error occurs in chunking THEN the Ingestion_Pipeline SHALL fallback to storing the entire page as one chunk
4. WHEN querying knowledge THEN the Hybrid_Search SHALL return chunks with their associated image_url for evidence
5. IF Semantic_Chunker is unavailable THEN the Ingestion_Pipeline SHALL continue with legacy 1-page-1-chunk behavior

### Requirement 8

**User Story:** As a maritime student, I want search results to be more accurate and focused, so that I can find specific information quickly.

#### Acceptance Criteria

1. WHEN searching for a specific rule THEN the Hybrid_Search SHALL return chunks containing that rule with higher relevance
2. WHEN multiple chunks match a query THEN the Hybrid_Search SHALL rank them by similarity score
3. WHEN returning results THEN the Hybrid_Search SHALL include the content_type for each chunk
4. WHEN returning results THEN the Hybrid_Search SHALL include the document hierarchy (Điều, Khoản) if available
5. WHEN displaying evidence THEN the RAG_Tool SHALL show the image_url of the page containing the chunk

