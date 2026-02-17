# Implementation Plan

## Feature: Hybrid Text/Vision Detection

Tối ưu hóa pipeline ingestion bằng cách phân loại thông minh các trang PDF để giảm 50-70% API calls cho Gemini Vision.

---

- [x] 1. Create PageAnalyzer Component




  - [x] 1.1 Create `app/engine/page_analyzer.py` with PageAnalysisResult dataclass

    - Define fields: page_number, has_images, has_tables, has_diagrams, has_maritime_signals, text_length, recommended_method, confidence
    - _Requirements: 1.1_
  - [ ] 1.2 Implement `analyze_page()` method to detect visual content
    - Check for embedded images via `page.get_images()`
    - Check for table patterns in text (pipe characters, grid patterns)

    - Check for diagram keywords (hình, figure, sơ đồ)
    - Check for maritime keywords (đèn, tín hiệu, cờ)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [ ] 1.3 Implement `should_use_vision()` method
    - Return True if any visual indicator is present
    - Return False for plain text only
    - _Requirements: 1.2, 1.3_
  - [ ]* 1.4 Write property test for page classification completeness
    - **Property 1: Page Classification Completeness**
    - **Validates: Requirements 1.1**
  - [ ]* 1.5 Write property test for visual content detection
    - **Property 2: Visual Content Detection Implies Vision**


    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4**



  - [ ]* 1.6 Write property test for plain text detection
    - **Property 3: Plain Text Implies Direct**
    - **Validates: Requirements 2.5**


- [ ] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add Configuration Settings



  - [ ] 3.1 Add hybrid detection settings to `app/core/config.py`
    - `hybrid_detection_enabled: bool = True`
    - `min_text_length_for_direct: int = 100`
    - `force_vision_mode: bool = False`
    - _Requirements: 3.1, 3.2, 3.3_
  - [ ] 3.2 Add configurable patterns for visual detection
    - `table_patterns: List[str]`

    - `diagram_keywords: List[str]`

    - `maritime_keywords: List[str]`
    - _Requirements: 3.2_


- [ ] 4. Implement Direct Extraction Method
  - [ ] 4.1 Add `_extract_direct()` method to MultimodalIngestionService
    - Use PyMuPDF `page.get_text()` for text extraction

    - Preserve document structure (blocks, paragraphs)
    - Handle Vietnamese encoding correctly
    - _Requirements: 5.1, 5.2_
  - [ ]* 4.2 Write property test for direct extraction text quality
    - **Property 9: Direct Extraction Text Quality**
    - **Validates: Requirements 5.1, 5.2**

- [ ] 5. Integrate PageAnalyzer into Ingestion Pipeline
  - [ ] 5.1 Update `MultimodalIngestionService.__init__()` to accept PageAnalyzer
    - Add `page_analyzer` parameter with default instance
    - _Requirements: 1.1_

  - [ ] 5.2 Update `_process_page()` to use hybrid detection
    - Call `page_analyzer.analyze_page()` first

    - Route to direct or vision extraction based on result

    - Implement fallback logic for short text
    - _Requirements: 1.2, 1.3, 5.3_
  - [ ] 5.3 Add force_vision_mode support
    - Skip analysis and use vision when force_vision_mode is True

    - _Requirements: 3.3_
  - [ ]* 5.4 Write property test for routing follows classification
    - **Property 4: Routing Follows Classification**

    - **Validates: Requirements 1.2, 1.3**
  - [ ]* 5.5 Write property test for force vision override
    - **Property 5: Force Vision Override**
    - **Validates: Requirements 3.3**
  - [ ]* 5.6 Write property test for fallback on short text
    - **Property 6: Fallback on Short Text**
    - **Validates: Requirements 5.3**


- [x] 6. Checkpoint - Ensure all tests pass

  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Enhance IngestionResult with Method Tracking
  - [ ] 7.1 Add tracking fields to IngestionResult dataclass
    - `vision_pages: int = 0`
    - `direct_pages: int = 0`

    - `fallback_pages: int = 0`



    - _Requirements: 4.1_
  - [ ] 7.2 Add `api_savings_percent` property
    - Calculate: `(direct_pages / total_pages) * 100`
    - Handle division by zero

    - _Requirements: 4.2_
  - [ ] 7.3 Update `_process_page()` to track extraction method
    - Increment appropriate counter based on method used

    - _Requirements: 4.1_
  - [ ]* 7.4 Write property test for method count consistency
    - **Property 7: Method Count Consistency**



    - **Validates: Requirements 4.1**
  - [ ]* 7.5 Write property test for savings calculation
    - **Property 8: Savings Calculation**
    - **Validates: Requirements 4.2**

- [ ] 8. Add Extraction Method to Chunk Metadata
  - [ ] 8.1 Update chunk metadata to include extraction_method
    - Add `extraction_method: str` field ("direct" or "vision")
    - _Requirements: 4.3_
  - [ ]* 8.2 Write property test for chunking consistency
    - **Property 10: Chunking Consistency**
    - **Validates: Requirements 5.4**

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Update Logging and Documentation
  - [ ] 10.1 Add detailed logging for extraction method decisions
    - Log page analysis results
    - Log extraction method used per page
    - Log fallback events
    - _Requirements: 1.4_
  - [ ] 10.2 Update ingestion completion log with savings summary
    - Log vision_pages, direct_pages, fallback_pages
    - Log api_savings_percent
    - _Requirements: 4.1, 4.2_
  - [ ] 10.3 Update README.md with hybrid detection documentation
    - Document configuration options
    - Document expected cost savings
    - _Requirements: All_

- [ ] 11. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
