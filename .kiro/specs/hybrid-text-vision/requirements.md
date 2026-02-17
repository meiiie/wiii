# Requirements Document

## Introduction

Tính năng Hybrid Text/Vision Detection tối ưu hóa pipeline ingestion bằng cách phân loại thông minh các trang PDF: trang chỉ có text thuần túy sẽ được extract trực tiếp bằng PyMuPDF, trong khi trang có hình ảnh/bảng biểu/sơ đồ sẽ được xử lý qua Gemini Vision. Mục tiêu giảm 50-70% API calls cho Gemini Vision, tiết kiệm chi phí và tăng tốc độ ingestion.

## Glossary

- **Multimodal_Ingestion_Service**: Service xử lý PDF thành chunks với embeddings
- **Page_Analyzer**: Module phân tích trang PDF để quyết định phương thức extraction
- **Vision_Extraction**: Sử dụng Gemini Vision API để extract text từ ảnh
- **Direct_Extraction**: Sử dụng PyMuPDF để extract text trực tiếp từ PDF
- **Visual_Content**: Nội dung có hình ảnh, bảng biểu, sơ đồ, đèn hiệu
- **Text_Only_Content**: Nội dung chỉ có văn bản thuần túy
- **Extraction_Method**: Phương thức được chọn (vision hoặc direct)

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want the ingestion pipeline to automatically detect page content type, so that I can reduce API costs by 50-70%.

#### Acceptance Criteria

1. WHEN the Multimodal_Ingestion_Service processes a PDF page THEN the Page_Analyzer SHALL classify the page as either visual_content or text_only_content
2. WHEN a page is classified as text_only_content THEN the Multimodal_Ingestion_Service SHALL use Direct_Extraction via PyMuPDF
3. WHEN a page is classified as visual_content THEN the Multimodal_Ingestion_Service SHALL use Vision_Extraction via Gemini Vision
4. WHEN processing a PDF document THEN the Multimodal_Ingestion_Service SHALL log the extraction method used for each page

### Requirement 2

**User Story:** As a system administrator, I want accurate page classification, so that visual content is not missed and text quality is maintained.

#### Acceptance Criteria

1. WHEN a page contains embedded images THEN the Page_Analyzer SHALL classify it as visual_content
2. WHEN a page contains table structures (detected via pipe characters or grid patterns) THEN the Page_Analyzer SHALL classify it as visual_content
3. WHEN a page contains diagram references (Hình, Figure, Sơ đồ keywords) THEN the Page_Analyzer SHALL classify it as visual_content
4. WHEN a page contains maritime signal descriptions (đèn, tín hiệu, cờ) THEN the Page_Analyzer SHALL classify it as visual_content
5. WHEN a page contains only plain text without visual indicators THEN the Page_Analyzer SHALL classify it as text_only_content

### Requirement 3

**User Story:** As a system administrator, I want configurable detection thresholds, so that I can tune the classification behavior.

#### Acceptance Criteria

1. WHEN the Page_Analyzer is initialized THEN the system SHALL allow configuration of minimum text length threshold for direct extraction
2. WHEN the Page_Analyzer is initialized THEN the system SHALL allow configuration of visual keyword patterns
3. WHERE force_vision mode is enabled THEN the Multimodal_Ingestion_Service SHALL use Vision_Extraction for all pages regardless of classification

### Requirement 4

**User Story:** As a system administrator, I want to track cost savings from hybrid detection, so that I can measure the optimization effectiveness.

#### Acceptance Criteria

1. WHEN ingestion completes THEN the Multimodal_Ingestion_Service SHALL report the count of pages processed via each extraction method
2. WHEN ingestion completes THEN the Multimodal_Ingestion_Service SHALL calculate and report the estimated API cost savings percentage
3. WHEN a page is processed THEN the Multimodal_Ingestion_Service SHALL record the extraction method in the chunk metadata

### Requirement 5

**User Story:** As a developer, I want the hybrid detection to maintain text quality, so that RAG search accuracy is not degraded.

#### Acceptance Criteria

1. WHEN Direct_Extraction is used THEN the extracted text SHALL preserve document structure (headings, paragraphs)
2. WHEN Direct_Extraction is used THEN the extracted text SHALL maintain Vietnamese character encoding correctly
3. WHEN Direct_Extraction produces text shorter than minimum threshold THEN the system SHALL fallback to Vision_Extraction
4. WHEN extraction method changes THEN the semantic chunking pipeline SHALL process the text identically regardless of extraction source
