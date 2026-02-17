# Implementation Plan

## Overview

Implementation plan cho tính năng **Source Highlighting with Citation Jumping** - Backend only.

**Estimated Effort:** 1-2 tuần
**Dependencies:** PyMuPDF (fitz), hypothesis (testing)

---

- [x] 1. Database Schema Enhancement




  - [x] 1.1 Create Alembic migration for bounding_boxes column

    - Add JSONB column `bounding_boxes` to `knowledge_embeddings` table
    - Set DEFAULT NULL for existing records
    - Create GIN index for future query optimization
    - _Requirements: 3.1, 3.2, 3.3_
  - [ ]* 1.2 Write property test for schema migration
    - **Property 6: Re-ingestion Data Preservation**




    - **Validates: Requirements 4.1, 4.2**
    - Verify existing embeddings unchanged after migration


- [x] 2. BoundingBoxExtractor Component

  - [x] 2.1 Create BoundingBoxExtractor class
    - Implement `extract_text_with_boxes()` using PyMuPDF `page.get_text("dict")`
    - Implement `normalize_bbox()` to convert points to percentage (0-100)
    - Implement `merge_boxes()` for overlapping/adjacent boxes
    - _Requirements: 1.1, 1.2, 1.4_
  - [ ]* 2.2 Write property test for coordinate normalization
    - **Property 1: Bounding Box Coordinate Normalization**
    - **Validates: Requirements 1.4**
    - Generate random coordinates, verify output is 0-100
  - [ ]* 2.3 Write property test for extraction completeness
    - **Property 2: Bounding Box Extraction Completeness**


    - **Validates: Requirements 1.1, 1.3**




    - Test with known text, verify boxes found or graceful fallback
  - [ ]* 2.4 Write property test for multi-block coverage
    - **Property 3: Multi-Block Chunk Coverage**

    - **Validates: Requirements 1.2**
    - Test chunks spanning multiple blocks




- [x] 3. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.



- [x] 4. Integrate BoundingBox into Ingestion Pipeline
  - [x] 4.1 Modify MultimodalIngestionService
    - Add `extract_with_bounding_boxes()` method
    - Call BoundingBoxExtractor during chunk processing
    - Store bounding_boxes in database with each chunk
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 4.2 Update chunk storage to include bounding_boxes
    - Modify `_store_chunk()` to accept bounding_boxes parameter
    - Handle null bounding_boxes gracefully
    - _Requirements: 1.3_


- [x] 5. Enhanced API Response
  - [x] 5.1 Update Source schema with bounding_boxes field
    - Add `bounding_boxes: Optional[List[dict]]` to Source model
    - Update SourceWithHighlight schema
    - _Requirements: 2.1, 2.2_
  - [x] 5.2 Modify chat_service to include bounding_boxes in sources



    - Fetch bounding_boxes from database with sources
    - Merge same-page sources into single entry
    - _Requirements: 2.3, 2.4_
  - [ ]* 5.3 Write property test for API response consistency
    - **Property 4: API Response Schema Consistency**
    - **Validates: Requirements 2.1, 2.3**
    - Verify all sources have consistent format

  - [ ]* 5.4 Write property test for same-page merging
    - **Property 5: Same-Page Source Merging**
    - **Validates: Requirements 2.4**
    - Test multiple chunks from same page merge correctly

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Source Details API Endpoint

  - [x] 7.1 Create new API router for sources


    - Create `app/api/v1/sources.py`
    - Implement `GET /api/v1/sources/{node_id}` endpoint
    - Return full metadata including bounding_boxes
    - _Requirements: 5.1, 5.2, 5.3_


  - [x] 7.2 Register router in main app
    - Add sources router to FastAPI app
    - Update OpenAPI documentation
    - _Requirements: 5.1_
  - [ ]* 7.3 Write property test for source details completeness
    - **Property 7: Source Details API Completeness**




    - **Validates: Requirements 5.1, 5.3**
    - Verify all required fields returned

- [x] 8. Re-ingestion Script
  - [x] 8.1 Create re-ingestion script for bounding boxes




    - Create `scripts/reingest_bounding_boxes.py`
    - Update existing chunks with bounding_boxes
    - Preserve embeddings, only update bounding_boxes


    - Report extraction success rate statistics

    - _Requirements: 4.1, 4.2, 4.3_
  - [ ]* 8.2 Write integration test for re-ingestion
    - Verify embeddings unchanged after re-ingestion
    - Verify bounding_boxes populated
    - _Requirements: 4.2_

- [x] 9. Final Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Documentation and Cleanup

  - [x] 10.1 Update README.md with new feature documentation
    - Document bounding_boxes in API response
    - Document Source Details API endpoint
    - Add usage examples for frontend integration
    - _Requirements: All_
  - [x] 10.2 Update KIRO_CONTEXT_MEMORY.md
    - Add v0.9.8 changelog entry
    - Document new components and APIs
    - _Requirements: All_
