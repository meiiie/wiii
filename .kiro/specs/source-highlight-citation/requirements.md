# Requirements Document

## Introduction

Tính năng **Source Highlighting with Citation Jumping** cho phép người dùng click vào source trong câu trả lời AI để jump đến vị trí cụ thể trong PDF và highlight (tô vàng) phần dữ liệu được tham khảo. Đây là enhancement phổ biến trong MM-RAG 2025 để tăng tính explainability và trustworthiness.

**Phạm vi Backend:** Spec này chỉ cover phần Backend (Maritime AI Service). Frontend (LMS Angular) sẽ được team Frontend implement dựa trên API mới.

**Tình trạng hiện tại:**
- ✅ Evidence Images đã có (Supabase URLs)
- ✅ Page number tracking đã có
- ❌ Bounding box coordinates chưa có
- ❌ Text position tracking chưa có

## Glossary

- **Bounding Box**: Tọa độ hình chữ nhật (x0, y0, x1, y1) xác định vị trí của text/element trên trang PDF
- **Citation Jumping**: Tính năng cho phép user click vào source để nhảy đến vị trí chính xác trong document
- **Source Highlighting**: Tô màu (highlight) phần text/image được trích dẫn trong PDF
- **Evidence Image**: Ảnh chụp trang PDF gốc được hiển thị cùng câu trả lời
- **Chunk**: Đoạn text được chia nhỏ từ document để indexing và retrieval
- **PyMuPDF (fitz)**: Thư viện Python để xử lý PDF, extract text với coordinates

## Requirements

### Requirement 1: Bounding Box Extraction

**User Story:** As a system administrator, I want the ingestion pipeline to extract bounding box coordinates for each chunk, so that the frontend can highlight the exact text position in PDF viewer.

#### Acceptance Criteria

1. WHEN the system extracts text from a PDF page THEN the system SHALL store bounding box coordinates (x0, y0, x1, y1) for each chunk in the database
2. WHEN a chunk spans multiple text blocks THEN the system SHALL store an array of bounding boxes covering all relevant text
3. WHEN the bounding box extraction fails THEN the system SHALL fallback to page-level reference without coordinates
4. WHEN storing bounding boxes THEN the system SHALL normalize coordinates to percentage values (0-100) for responsive display

### Requirement 2: Enhanced Source Metadata in API Response

**User Story:** As a frontend developer, I want the chat API to return bounding box coordinates with each source, so that I can implement highlight overlay in PDF viewer.

#### Acceptance Criteria

1. WHEN the chat API returns sources THEN the system SHALL include bounding_boxes array for each source
2. WHEN a source has no bounding box data THEN the system SHALL return null for bounding_boxes field
3. WHEN returning source metadata THEN the system SHALL include page_number, image_url, and bounding_boxes in a consistent format
4. WHEN the response includes multiple chunks from same page THEN the system SHALL merge bounding boxes into single source entry

### Requirement 3: Database Schema Enhancement

**User Story:** As a database administrator, I want the knowledge_embeddings table to store bounding box data, so that citation coordinates are persisted and queryable.

#### Acceptance Criteria

1. WHEN adding bounding box support THEN the system SHALL add a JSONB column named bounding_boxes to knowledge_embeddings table
2. WHEN migrating existing data THEN the system SHALL set bounding_boxes to NULL for existing records
3. WHEN indexing bounding box data THEN the system SHALL create appropriate indexes for query performance

### Requirement 4: Re-ingestion with Bounding Box

**User Story:** As a content manager, I want to re-ingest existing documents to extract bounding boxes, so that all documents support the highlight feature.

#### Acceptance Criteria

1. WHEN re-ingesting a document THEN the system SHALL extract and store bounding boxes for all chunks
2. WHEN the re-ingestion script runs THEN the system SHALL preserve existing embeddings and only update bounding_boxes
3. WHEN re-ingestion completes THEN the system SHALL report statistics on bounding box extraction success rate

### Requirement 5: Chunk-to-Source Mapping API

**User Story:** As a frontend developer, I want an API endpoint to get detailed source information including highlight coordinates, so that I can render PDF with precise highlights.

#### Acceptance Criteria

1. WHEN a client requests source details by node_id THEN the system SHALL return full metadata including bounding_boxes, page_number, image_url, and text_snippet
2. WHEN the requested node_id does not exist THEN the system SHALL return 404 with appropriate error message
3. WHEN returning source details THEN the system SHALL include document_id for PDF file reference
