# Implementation Plan

## Semantic Chunking - Nâng cấp Multimodal RAG

- [x] 1. Database Schema Update

  - [x] 1.1 Tạo Alembic migration 003_add_chunking_columns.py
    - Thêm column `content_type VARCHAR(50) DEFAULT 'text'`
    - Thêm column `confidence_score FLOAT DEFAULT 1.0`

    - Tạo index `idx_knowledge_chunks_ordering` trên (document_id, page_number, chunk_index)
    - Tạo index `idx_knowledge_chunks_content_type` trên content_type
    - _Requirements: 4.1, 4.2, 4.3_
  - [x] 1.2 Chạy migration trên Neon database

    - Backup data trước khi migrate
    - Execute migration

    - Verify schema changes





    - _Requirements: 4.1, 4.2_


- [x] 2. Configuration Settings
  - [x] 2.1 Cập nhật app/core/config.py với chunking settings
    - Thêm `chunk_size: int = 800`

    - Thêm `chunk_overlap: int = 100`
    - Thêm `min_chunk_size: int = 50`




    - Thêm `dpi_optimized: int = 100`
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [x] 3. Checkpoint - Đảm bảo infrastructure ready

  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement SemanticChunker Service
  - [x] 4.1 Tạo file app/services/chunking_service.py
    - Implement SemanticChunker class

    - Sử dụng LangChain RecursiveCharacterTextSplitter
    - Method: chunk_page_content(text, page_metadata) → List[ChunkResult]
    - _Requirements: 1.1, 1.2_
  - [x]* 4.2 Write property test cho chunk size bounds



    - **Property 1: Chunk Size Bounds**
    - **Validates: Requirements 1.1, 1.5**
  - [x]* 4.3 Write property test cho chunk count proportional

    - **Property 2: Chunk Count Increases with Text Length**
    - **Validates: Requirements 1.4**
  - [x] 4.4 Implement content type detection
    - Method: _detect_content_type(text) → str
    - Detect: text, table, heading, diagram_reference, formula
    - Maritime-specific patterns (Điều, Khoản, Rule)


    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 4.5 Write property test cho content type valid enum
    - **Property 3: Content Type Valid Enum**
    - **Validates: Requirements 2.1**
  - [ ]* 4.6 Write property test cho table detection
    - **Property 4: Table Detection Accuracy**
    - **Validates: Requirements 2.2**
  - [x]* 4.7 Write property test cho heading detection

    - **Property 5: Heading Detection for Maritime Patterns**
    - **Validates: Requirements 2.3, 2.4**
  - [x] 4.8 Implement confidence scoring
    - Method: _calculate_confidence(chunk, content_type) → float
    - Base score from length, boost for structured content
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x]* 4.9 Write property test cho confidence score bounds



    - **Property 6: Confidence Score Bounds**
    - **Validates: Requirements 3.1**
  - [ ]* 4.10 Write property test cho short chunk penalty
    - **Property 7: Short Chunk Confidence Penalty**

    - **Validates: Requirements 3.2**
  - [x]* 4.11 Write property test cho long chunk penalty

    - **Property 8: Long Chunk Confidence Penalty**
    - **Validates: Requirements 3.3**
  - [ ]* 4.12 Write property test cho structured content boost
    - **Property 9: Structured Content Confidence Boost**
    - **Validates: Requirements 3.4**
  - [x] 4.13 Implement document hierarchy extraction






    - Method: _extract_document_hierarchy(chunk) → Dict


    - Extract: article, clause, point, rule numbers

    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 4.14 Write property test cho article extraction
    - **Property 11: Article Number Extraction**
    - **Validates: Requirements 5.1**




  - [ ]* 4.15 Write property test cho clause extraction
    - **Property 12: Clause Number Extraction**


    - **Validates: Requirements 5.2**


- [x] 5. Checkpoint - Đảm bảo SemanticChunker hoạt động


  - Ensure all tests pass, ask the user if questions arise.



- [x] 6. Integrate với MultimodalIngestionService
  - [x] 6.1 Cập nhật app/services/multimodal_ingestion_service.py

    - Import SemanticChunker


    - Modify _process_page() để gọi chunker sau Vision extraction
    - Store multiple chunks per page với chunk_index
    - _Requirements: 7.1, 7.2_

  - [x]* 6.2 Write property test cho chunk index sequential





    - **Property 10: Chunk Index Sequential**
    - **Validates: Requirements 4.4**
  - [x] 6.3 Cập nhật _store_in_database() method
    - Thêm parameters: chunk_index, content_type, confidence_score
    - Update SQL INSERT/UPDATE statements
    - _Requirements: 2.5, 3.5, 5.5_
  - [ ]* 6.4 Write property test cho database round-trip
    - **Property 13: Database Round-Trip Consistency**
    - **Validates: Requirements 2.5, 3.5, 5.5**
  - [x] 6.5 Implement fallback behavior
    - If chunking fails, store entire page as one chunk
    - Log warning for fallback cases
    - _Requirements: 7.3_

- [x] 7. Checkpoint - Đảm bảo integration hoạt động
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Update Dense Search Repository
  - [x] 8.1 Cập nhật app/repositories/dense_search_repository.py
    - Add method: store_document_chunk() với full parameters
    - Update search() để return content_type và confidence_score
    - _Requirements: 8.1, 8.2, 8.3_
  - [x] 8.2 Cập nhật Hybrid Search Service
    - Include content_type trong search results
    - Include document hierarchy trong metadata
    - _Requirements: 8.4_

- [x] 9. Update RAG Tool
  - [x] 9.1 Cập nhật app/engine/tools/rag_tool.py
    - Format search results với content_type
    - Include document hierarchy (Điều, Khoản) trong output
    - Maintain image_url reference cho evidence
    - _Requirements: 8.4, 8.5_

- [x] 10. Checkpoint - Đảm bảo search hoạt động
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Re-ingestion Script
  - [x] 11.1 Tạo script scripts/reingest_with_chunking.py
    - Truncate old data (backup first)
    - Re-ingest với new chunking pipeline
    - Log progress và summary
    - _Requirements: 7.1, 7.2_

- [x] 12. Documentation
  - [x] 12.1 Cập nhật docs/MULTIMODAL_RAG_GUIDE.md
    - Document semantic chunking feature
    - Document new config settings
    - Document content type classification
    - _Requirements: Documentation_

- [x] 13. Final Checkpoint - Đảm bảo toàn bộ hệ thống hoạt động

  - Ensure all tests pass, ask the user if questions arise.

