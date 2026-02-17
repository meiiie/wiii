# Requirements Document

## Introduction

Chuyển đổi hệ thống Maritime AI Service từ **"Đọc văn bản" (Text-based)** sang **"Hiểu tài liệu" (Vision-based)** theo CHỈ THỊ KỸ THUẬT SỐ 26. Hệ thống mới cho phép AI "nhìn" thấy trang tài liệu gốc như con người, bao gồm bảng biểu, sơ đồ đèn hiệu, hình vẽ tàu bè trong luật COLREGs. Khi trả lời, AI không chỉ đưa ra text mà còn hiển thị hình ảnh dẫn chứng (Evidence Image) cho người học.

## Glossary

- **Multimodal_RAG_System**: Hệ thống RAG có khả năng xử lý cả text và hình ảnh
- **Vision_Model**: Google Gemini 2.5 Flash với khả năng đọc và hiểu hình ảnh
- **Rasterization**: Quá trình chuyển đổi PDF thành ảnh chất lượng cao
- **Evidence_Image**: Hình ảnh trang sách luật gốc được hiển thị cùng câu trả lời
- **Supabase_Storage**: Object Storage để lưu trữ file ảnh (JPG/PNG)
- **Neon_Database**: Serverless Postgres lưu trữ metadata, text description và vectors
- **Ingestion_Pipeline**: Quy trình nạp dữ liệu từ PDF vào hệ thống
- **Hybrid_Infrastructure**: Kiến trúc kết hợp Neon (metadata) + Supabase (files)

## Requirements

### Requirement 1

**User Story:** As a maritime student, I want the AI to understand visual content in maritime documents (tables, diagrams, ship illustrations), so that I receive accurate answers about COLREGs rules that include visual elements.

#### Acceptance Criteria

1. WHEN a user asks about a COLREGs rule containing diagrams THEN the Multimodal_RAG_System SHALL return both text explanation and reference to the original page image
2. WHEN the system processes a PDF page with tables THEN the Vision_Model SHALL convert the table structure into Markdown Table format
3. WHEN the system processes a PDF page with navigation light diagrams THEN the Vision_Model SHALL describe colors, positions, and meanings in text
4. WHEN displaying search results THEN the Multimodal_RAG_System SHALL include the image_url field pointing to the evidence image
5. IF the image_url is unavailable THEN the Multimodal_RAG_System SHALL gracefully fallback to text-only response

### Requirement 2

**User Story:** As a system administrator, I want to convert PDF documents into high-quality images and store them efficiently, so that the AI can process visual content.

#### Acceptance Criteria

1. WHEN a PDF document is uploaded THEN the Ingestion_Pipeline SHALL convert each page to a high-quality image using pdf2image library
2. WHEN an image is generated THEN the Ingestion_Pipeline SHALL upload it to Supabase_Storage bucket "maritime-docs" with public access
3. WHEN the upload completes THEN the Ingestion_Pipeline SHALL return the public_url of the image
4. WHEN storing image metadata THEN the Neon_Database SHALL save image_url and page_number in knowledge_embeddings table
5. IF the Supabase_Storage upload fails THEN the Ingestion_Pipeline SHALL retry up to 3 times before logging error

### Requirement 3

**User Story:** As a system administrator, I want the AI to extract text content from document images accurately, so that the knowledge base contains complete information including visual elements.

#### Acceptance Criteria

1. WHEN an image is sent to Vision_Model THEN the Vision_Model SHALL extract all text content preserving headings (Điều, Khoản)
2. WHEN the image contains tables THEN the Vision_Model SHALL convert them to Markdown Table format
3. WHEN the image contains diagrams THEN the Vision_Model SHALL describe visual elements (colors, positions, meanings) in Vietnamese
4. WHEN extraction completes THEN the Ingestion_Pipeline SHALL store the extracted text with embedding in Neon_Database
5. IF the Vision_Model extraction fails THEN the Ingestion_Pipeline SHALL log the error and skip the page with notification

### Requirement 4

**User Story:** As a developer, I want to set up hybrid infrastructure with Neon for metadata and Supabase for file storage, so that the system can efficiently handle both structured data and binary files.

#### Acceptance Criteria

1. WHEN the system initializes THEN the Hybrid_Infrastructure SHALL connect to both Neon_Database and Supabase_Storage
2. WHEN storing document data THEN the Neon_Database SHALL contain metadata, text_description, vectors, image_url, and page_number
3. WHEN storing images THEN the Supabase_Storage SHALL organize files in bucket "maritime-docs" with folder structure by document
4. WHEN querying knowledge THEN the Hybrid_Infrastructure SHALL return both text content and image_url from Neon_Database
5. IF either Neon_Database or Supabase_Storage is unavailable THEN the Hybrid_Infrastructure SHALL report health status as degraded

### Requirement 5

**User Story:** As a system administrator, I want to migrate the database schema to support multimodal content, so that the system can store image references alongside text content.

#### Acceptance Criteria

1. WHEN migration runs THEN the Neon_Database SHALL add column image_url (TEXT) to knowledge_embeddings table
2. WHEN migration runs THEN the Neon_Database SHALL add column page_number (INTEGER) to knowledge_embeddings table
3. WHEN migration completes THEN the Neon_Database SHALL truncate old pypdf-extracted data
4. WHEN the new schema is active THEN the Ingestion_Pipeline SHALL populate image_url for all new entries
5. IF migration fails THEN the Neon_Database SHALL rollback to previous schema state

### Requirement 6

**User Story:** As a maritime student, I want to see the original document page alongside the AI's answer, so that I can verify the information and study the visual content directly.

#### Acceptance Criteria

1. WHEN the RAG_Tool returns search results THEN the response SHALL include image_url for each relevant chunk
2. WHEN the AI generates an answer THEN the response metadata SHALL contain list of evidence_images with their page_numbers
3. WHEN the frontend displays the answer THEN the Evidence_Image SHALL be shown alongside the text response
4. WHEN multiple pages are relevant THEN the Multimodal_RAG_System SHALL return up to 3 most relevant evidence_images
5. IF no evidence_image is available THEN the response SHALL indicate text-only source

### Requirement 7

**User Story:** As a developer, I want to implement the multimodal ingestion pipeline with proper error handling and logging, so that the system can reliably process large PDF documents.

#### Acceptance Criteria

1. WHEN processing a PDF THEN the Ingestion_Pipeline SHALL log progress for each page (page X of Y)
2. WHEN an error occurs during rasterization THEN the Ingestion_Pipeline SHALL log the error and continue with next page
3. WHEN an error occurs during Vision_Model extraction THEN the Ingestion_Pipeline SHALL retry once before skipping
4. WHEN ingestion completes THEN the Ingestion_Pipeline SHALL report summary (total pages, successful, failed)
5. WHEN the system restarts THEN the Ingestion_Pipeline SHALL be able to resume from last successful page

### Requirement 8

**User Story:** As a system administrator, I want to configure the Vision Model prompt for maritime document extraction, so that the AI accurately captures domain-specific content.

#### Acceptance Criteria

1. WHEN sending image to Vision_Model THEN the Ingestion_Pipeline SHALL use specialized maritime extraction prompt
2. WHEN the prompt is applied THEN the Vision_Model SHALL preserve article numbers (Điều, Khoản) in output
3. WHEN the prompt is applied THEN the Vision_Model SHALL convert tables to Markdown format
4. WHEN the prompt is applied THEN the Vision_Model SHALL describe navigation lights with colors and positions
5. WHEN the prompt is applied THEN the Vision_Model SHALL not skip any visible text content
