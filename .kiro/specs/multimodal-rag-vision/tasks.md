# Implementation Plan

## Multimodal RAG Vision - CHỈ THỊ KỸ THUẬT SỐ 26

- [x] 1. Setup Infrastructure và Dependencies




  - [ ] 1.1 Cập nhật requirements.txt với pdf2image và supabase
    - Thêm `pdf2image>=1.16.3`
    - Thêm `supabase>=2.0.0`


    - Thêm `Pillow>=10.0.0` (nếu chưa có)
    - _Requirements: 2.1, 4.1_


  - [ ] 1.2 Cập nhật Dockerfile với poppler-utils
    - Thêm `RUN apt-get update && apt-get install -y poppler-utils`
    - Test build Docker image locally

    - _Requirements: 2.1_

  - [x] 1.3 Tạo Supabase Storage bucket "maritime-docs"




    - Tạo bucket với public access
    - Cấu hình CORS cho frontend access
    - Thêm SUPABASE_URL và SUPABASE_KEY vào .env
    - _Requirements: 2.2, 4.3_
  - [ ] 1.4 Cập nhật config.py với Supabase settings
    - Thêm SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET

    - Validate required environment variables
    - _Requirements: 4.1_

- [x] 2. Database Migration

  - [ ] 2.1 Tạo Alembic migration cho multimodal columns
    - Thêm cột `image_url TEXT` vào knowledge_embeddings




    - Thêm cột `page_number INTEGER` vào knowledge_embeddings
    - Tạo index cho page_number và document_id
    - _Requirements: 5.1, 5.2_
  - [ ]* 2.2 Write property test cho database schema
    - **Property 10: Schema Contains Required Fields**
    - **Validates: Requirements 4.2**
  - [ ] 2.3 Chạy migration trên Neon database
    - Backup data trước khi migrate
    - Execute migration
    - Verify schema changes
    - _Requirements: 5.1, 5.2_





- [ ] 3. Checkpoint - Đảm bảo infrastructure ready
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement SupabaseStorageClient
  - [ ] 4.1 Tạo file app/services/supabase_storage.py
    - Implement SupabaseStorageClient class
    - Method: upload_image(image_data, path) → public_url
    - Method: get_public_url(path) → url
    - Method: delete_image(path) → bool
    - Implement retry logic (3 attempts)
    - _Requirements: 2.2, 2.3_
  - [ ]* 4.2 Write property test cho upload returns valid URL
    - **Property 7: Upload Returns Valid Public URL**
    - **Validates: Requirements 2.2, 2.3**
  - [ ]* 4.3 Write property test cho storage folder structure
    - **Property 9: Storage Folder Structure**



    - **Validates: Requirements 4.3**


- [ ] 5. Implement VisionExtractor
  - [ ] 5.1 Tạo file app/engine/vision_extractor.py
    - Implement VisionExtractor class
    - Define MARITIME_EXTRACTION_PROMPT
    - Method: extract(image_url) → ExtractionResult
    - Method: validate_extraction(result) → bool
    - Handle API errors và rate limiting
    - _Requirements: 3.1, 3.2, 3.3, 8.1_
  - [ ]* 5.2 Write property test cho table to markdown conversion
    - **Property 1: Table to Markdown Conversion**
    - **Validates: Requirements 1.2, 3.2, 8.3**
  - [ ]* 5.3 Write property test cho diagram description
    - **Property 2: Diagram Description Completeness**
    - **Validates: Requirements 1.3, 3.3, 8.4**
  - [x]* 5.4 Write property test cho heading preservation

    - **Property 5: Heading Preservation**
    - **Validates: Requirements 3.1, 8.2**
  - [ ]* 5.5 Write property test cho no text skipped
    - **Property 16: No Text Content Skipped**
    - **Validates: Requirements 8.5**

- [ ] 6. Implement MultimodalIngestionService
  - [ ] 6.1 Tạo file app/services/multimodal_ingestion_service.py
    - Implement MultimodalIngestionService class
    - Method: convert_pdf_to_images(pdf_path, dpi=300) → List[Image]

    - Method: ingest_pdf(pdf_path, document_id) → IngestionResult
    - Implement progress logging



    - Implement resume capability

    - _Requirements: 2.1, 7.1, 7.4, 7.5_
  - [ ]* 6.2 Write property test cho PDF page count equals image count
    - **Property 6: PDF Page Count Equals Image Count**
    - **Validates: Requirements 2.1**
  - [ ]* 6.3 Write property test cho ingestion logs progress
    - **Property 13: Ingestion Logs Progress**
    - **Validates: Requirements 7.1**
  - [ ]* 6.4 Write property test cho ingestion summary
    - **Property 14: Ingestion Summary Contains Counts**
    - **Validates: Requirements 7.4**
  - [ ]* 6.5 Write property test cho resume capability
    - **Property 15: Resume From Last Successful Page**



    - **Validates: Requirements 7.5**

  - [ ] 6.6 Integrate với SupabaseStorageClient và VisionExtractor
    - Wire up dependencies
    - Implement full pipeline flow


    - Add error handling cho từng step
    - _Requirements: 2.1, 2.2, 3.1, 3.4_
  - [x]* 6.7 Write property test cho database stores image metadata



    - **Property 4: Database Stores Image Metadata**

    - **Validates: Requirements 2.4, 5.4**
  - [ ]* 6.8 Write property test cho extraction stores text with embedding
    - **Property 8: Extraction Stores Text with Embedding**


    - **Validates: Requirements 3.4**

- [x] 7. Checkpoint - Đảm bảo ingestion pipeline hoạt động

  - Ensure all tests pass, ask the user if questions arise.





- [ ] 8. Update RAG Tool với Evidence Images
  - [ ] 8.1 Cập nhật app/engine/tools/rag_tool.py
    - Method: search_with_evidence(query, top_k, max_evidence_images) → RAGResult
    - Method: collect_evidence_images(results) → List[EvidenceImage]

    - Include image_url trong search results
    - Limit evidence images to 3
    - _Requirements: 1.1, 1.4, 6.1, 6.2, 6.4_





  - [ ]* 8.2 Write property test cho search results include image URL
    - **Property 3: Search Results Include Image URL**

    - **Validates: Requirements 1.4, 4.4, 6.1**

  - [ ]* 8.3 Write property test cho response metadata contains evidence images
    - **Property 11: Response Metadata Contains Evidence Images**


    - **Validates: Requirements 6.2**
  - [ ]* 8.4 Write property test cho maximum evidence images
    - **Property 12: Maximum Evidence Images Per Response**
    - **Validates: Requirements 6.4**

- [ ] 9. Update Response Models
  - [ ] 9.1 Cập nhật app/models/schemas.py
    - Thêm EvidenceImage model
    - Thêm RAGResultWithEvidence model
    - Thêm IngestionResult model
    - Thêm ExtractionResult model
    - _Requirements: 6.2_
  - [ ] 9.2 Cập nhật ChatService để include evidence_images
    - Modify response format
    - Add evidence_images to metadata
    - Handle graceful fallback khi không có images
    - _Requirements: 1.5, 6.2_

- [ ] 10. Update Knowledge API
  - [ ] 10.1 Cập nhật app/api/v1/knowledge.py
    - Endpoint: POST /api/v1/knowledge/ingest-multimodal
    - Accept PDF file upload
    - Return IngestionResult
    - Add progress streaming (optional)
    - _Requirements: 2.1, 7.1, 7.4_
  - [ ] 10.2 Cập nhật health check cho hybrid infrastructure
    - Check Neon connection
    - Check Supabase connection
    - Report degraded status if either fails
    - _Requirements: 4.5_

- [ ] 11. Checkpoint - Đảm bảo API hoạt động
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Data Migration và Re-ingestion
  - [ ] 12.1 Tạo script truncate old data
    - Script: scripts/truncate_old_knowledge.py
    - Backup old data trước khi truncate
    - Execute TRUNCATE TABLE knowledge_embeddings
    - _Requirements: 5.3_
  - [ ] 12.2 Tạo script re-ingest với multimodal pipeline
    - Script: scripts/reingest_multimodal.py
    - Process COLREGs PDF với new pipeline
    - Log progress và summary
    - _Requirements: 2.1, 7.1, 7.4_

- [ ] 13. Update Documentation
  - [ ] 13.1 Cập nhật README.md
    - Add Multimodal RAG section
    - Document new environment variables
    - Update architecture diagram
    - _Requirements: Documentation_
  - [ ] 13.2 Tạo MULTIMODAL_RAG_GUIDE.md
    - Document ingestion process
    - Document evidence image feature
    - Troubleshooting guide
    - _Requirements: Documentation_

- [ ] 14. Final Checkpoint - Đảm bảo toàn bộ hệ thống hoạt động
  - Ensure all tests pass, ask the user if questions arise.
