# Multimodal RAG Vision Design

## Overview

Thiết kế chi tiết cho việc nâng cấp Maritime AI Service từ Text-based RAG sang Vision-based Multimodal RAG theo CHỈ THỊ KỸ THUẬT SỐ 26. Hệ thống mới cho phép AI "nhìn" thấy trang tài liệu gốc, xử lý bảng biểu, sơ đồ đèn hiệu, và hiển thị Evidence Image cho người học.

### Current State
```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────┤
│  PDF → pypdf (text extraction) → Embeddings → Neon          │
│                                                              │
│  PROBLEMS:                                                   │
│  • Mất cấu trúc bảng biểu                                   │
│  • Không đọc được sơ đồ đèn hiệu                            │
│  • Không hiểu hình vẽ tàu bè                                │
│  • AI trả lời thiếu chính xác về visual content             │
└─────────────────────────────────────────────────────────────┘
```

### Target State
```
┌─────────────────────────────────────────────────────────────┐
│                    TARGET ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│  PDF → pdf2image → Supabase Storage → Gemini Vision         │
│                         ↓                                    │
│              Text + image_url → Neon (pgvector)             │
│                         ↓                                    │
│              RAG Response + Evidence Images                  │
│                                                              │
│  BENEFITS:                                                   │
│  • AI "nhìn" thấy trang tài liệu như con người              │
│  • Bảng biểu được convert sang Markdown Table               │
│  • Sơ đồ đèn hiệu được mô tả chi tiết                       │
│  • Evidence Image hiển thị cùng câu trả lời                 │
└─────────────────────────────────────────────────────────────┘
```

## Architecture

### Hybrid Infrastructure Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HYBRID INFRASTRUCTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        RENDER (Compute)                              │   │
│   │   ┌─────────────────────────────────────────────────────────────┐   │   │
│   │   │  Maritime AI Service (FastAPI)                               │   │   │
│   │   │  • Ingestion Pipeline (pdf2image + Vision extraction)        │   │   │
│   │   │  • RAG Tool (Hybrid Search + Evidence Images)                │   │   │
│   │   │  • Chat Service (Response with image_url)                    │   │   │
│   │   └─────────────────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                    │                    │                    │               │
│                    ▼                    ▼                    ▼               │
│   ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│   │   NEON DATABASE     │  │  SUPABASE STORAGE   │  │   GOOGLE GEMINI     │ │
│   │   (Serverless PG)   │  │  (Object Storage)   │  │   (Vision Model)    │ │
│   │                     │  │                     │  │                     │ │
│   │  • Metadata         │  │  • Page Images      │  │  • Image → Text     │ │
│   │  • Text Description │  │  • JPG/PNG files    │  │  • Table → Markdown │ │
│   │  • Vectors (768d)   │  │  • Public URLs      │  │  • Diagram → Desc   │ │
│   │  • image_url        │  │  • Bucket:          │  │  • Embeddings       │ │
│   │  • page_number      │  │    maritime-docs    │  │                     │ │
│   └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Multimodal Ingestion Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTIMODAL INGESTION PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PDF Document                                                               │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 1: RASTERIZATION (pdf2image)                                    │   │
│   │   • Convert each page to high-quality image (300 DPI)                │   │
│   │   • Output: List[PIL.Image]                                          │   │
│   │   • Requires: poppler-utils in Dockerfile                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 2: STORAGE (Supabase)                                           │   │
│   │   • Upload image to bucket "maritime-docs"                           │   │
│   │   • Path: {document_id}/page_{number}.jpg                            │   │
│   │   • Return: public_url                                               │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 3: VISION EXTRACTION (Gemini 2.5 Flash)                         │   │
│   │   • Send image URL to Vision Model                                   │   │
│   │   • Maritime-specific extraction prompt                              │   │
│   │   • Output: Markdown text with tables, diagram descriptions          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 4: INDEXING (Neon + pgvector)                                   │   │
│   │   • Generate embedding for extracted text                            │   │
│   │   • Store: text, embedding, image_url, page_number                   │   │
│   │   • Update knowledge_embeddings table                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Retrieval Flow with Evidence Images

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RETRIEVAL FLOW WITH EVIDENCE IMAGES                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User Query: "Giải thích Rule 15 về tình huống cắt hướng"                  │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ HYBRID SEARCH (Dense + Sparse + RRF)                                 │   │
│   │   • Dense: pgvector similarity search                                │   │
│   │   • Sparse: Neo4j full-text search                                   │   │
│   │   • RRF Reranker: Merge and rank results                             │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ RESULT ENRICHMENT                                                    │   │
│   │   • Attach image_url to each result chunk                            │   │
│   │   • Collect unique evidence_images (max 3)                           │   │
│   │   • Include page_number for reference                                │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ LLM RESPONSE GENERATION                                              │   │
│   │   • Context: text content + image references                         │   │
│   │   • Output: Answer with evidence_images in metadata                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   Response:                                                                  │
│   {                                                                          │
│     "answer": "Theo Điều 15 COLREGs...",                                    │
│     "sources": [...],                                                        │
│     "evidence_images": [                                                     │
│       {"url": "https://xyz.supabase.co/.../page_15.jpg", "page": 15}        │
│     ]                                                                        │
│   }                                                                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. MultimodalIngestionService

```python
class MultimodalIngestionService:
    """Service for multimodal document ingestion"""
    
    def __init__(
        self,
        supabase_client: SupabaseClient,
        vision_extractor: VisionExtractor,
        embedding_service: GeminiEmbeddings,
        db_session: AsyncSession
    ):
        self.supabase = supabase_client
        self.vision = vision_extractor
        self.embeddings = embedding_service
        self.db = db_session
    
    async def ingest_pdf(
        self,
        pdf_path: str,
        document_id: str
    ) -> IngestionResult:
        """
        Full pipeline: PDF → Images → Vision → Embeddings → Database
        Returns summary with total, successful, failed counts
        """
        pass
    
    async def convert_pdf_to_images(
        self,
        pdf_path: str,
        dpi: int = 300
    ) -> List[Image]:
        """Convert PDF pages to high-quality images"""
        pass
    
    async def upload_to_supabase(
        self,
        image: Image,
        document_id: str,
        page_number: int
    ) -> str:
        """Upload image and return public URL"""
        pass
    
    async def extract_text_from_image(
        self,
        image_url: str
    ) -> str:
        """Use Vision Model to extract text from image"""
        pass
```

### 2. VisionExtractor

```python
class VisionExtractor:
    """Gemini Vision-based text extraction"""
    
    MARITIME_EXTRACTION_PROMPT = """
    Đóng vai chuyên gia số hóa dữ liệu Hàng hải. 
    Hãy nhìn bức ảnh này và mô tả lại toàn bộ nội dung thành văn bản định dạng Markdown.
    
    1. Giữ nguyên các tiêu đề (Điều, Khoản).
    2. Nếu có Bảng biểu: Chuyển thành Markdown Table.
    3. Nếu có Hình vẽ (Đèn hiệu/Tàu bè): Mô tả chi tiết màu sắc, vị trí, ý nghĩa.
    4. Không bỏ sót bất kỳ chữ nào.
    """
    
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
    
    async def extract(self, image_url: str) -> ExtractionResult:
        """Extract text from image using Vision Model"""
        pass
    
    def validate_extraction(self, result: str) -> bool:
        """Validate extraction contains expected elements"""
        pass
```

### 3. SupabaseStorageClient

```python
class SupabaseStorageClient:
    """Client for Supabase Storage operations"""
    
    BUCKET_NAME = "maritime-docs"
    
    def __init__(self, url: str, key: str):
        self.client = create_client(url, key)
    
    async def upload_image(
        self,
        image_data: bytes,
        path: str
    ) -> str:
        """Upload image and return public URL"""
        pass
    
    async def get_public_url(self, path: str) -> str:
        """Get public URL for stored file"""
        pass
    
    async def delete_image(self, path: str) -> bool:
        """Delete image from storage"""
        pass
```

### 4. Enhanced RAGTool

```python
class EnhancedRAGTool:
    """RAG Tool with Evidence Image support"""
    
    async def search_with_evidence(
        self,
        query: str,
        top_k: int = 5,
        max_evidence_images: int = 3
    ) -> RAGResult:
        """
        Search knowledge base and return results with evidence images
        """
        pass
    
    def collect_evidence_images(
        self,
        results: List[SearchResult]
    ) -> List[EvidenceImage]:
        """Collect unique evidence images from search results"""
        pass
```

## Data Models

### Database Schema Changes

```sql
-- Migration: Add multimodal columns to knowledge_embeddings
ALTER TABLE knowledge_embeddings
ADD COLUMN image_url TEXT,
ADD COLUMN page_number INTEGER;

-- Index for page lookup
CREATE INDEX idx_knowledge_embeddings_page 
ON knowledge_embeddings(page_number);

-- Index for document grouping
CREATE INDEX idx_knowledge_embeddings_document 
ON knowledge_embeddings(document_id, page_number);
```

### Pydantic Models

```python
class IngestionResult(BaseModel):
    """Result of PDF ingestion"""
    document_id: str
    total_pages: int
    successful_pages: int
    failed_pages: int
    errors: List[str] = []

class EvidenceImage(BaseModel):
    """Evidence image reference"""
    url: str
    page_number: int
    document_id: str

class RAGResultWithEvidence(BaseModel):
    """RAG result with evidence images"""
    answer: str
    sources: List[Source]
    evidence_images: List[EvidenceImage]
    suggested_questions: List[str]

class ExtractionResult(BaseModel):
    """Vision extraction result"""
    text: str
    has_tables: bool
    has_diagrams: bool
    headings_found: List[str]
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Based on the prework analysis, the following correctness properties have been identified after eliminating redundancies:

### Property 1: Table to Markdown Conversion
*For any* PDF page containing a table structure, when processed by the Vision_Model, the extracted text SHALL contain valid Markdown table syntax (pipe characters `|` and header separators `---`).
**Validates: Requirements 1.2, 3.2, 8.3**

### Property 2: Diagram Description Completeness
*For any* PDF page containing navigation light diagrams, when processed by the Vision_Model, the extracted text SHALL contain color keywords (đỏ, xanh, trắng, vàng) and position descriptions.
**Validates: Requirements 1.3, 3.3, 8.4**

### Property 3: Search Results Include Image URL
*For any* search query against the knowledge base, all returned result chunks SHALL include an image_url field (may be null for legacy data).
**Validates: Requirements 1.4, 4.4, 6.1**

### Property 4: Database Stores Image Metadata
*For any* newly ingested document page, the database record SHALL contain both image_url (non-empty string) and page_number (positive integer).
**Validates: Requirements 2.4, 5.4**

### Property 5: Heading Preservation
*For any* PDF page containing article headings (Điều, Khoản), when processed by the Vision_Model, the extracted text SHALL preserve these heading markers.
**Validates: Requirements 3.1, 8.2**

### Property 6: PDF Page Count Equals Image Count
*For any* PDF document with N pages, the rasterization process SHALL produce exactly N images.
**Validates: Requirements 2.1**

### Property 7: Upload Returns Valid Public URL
*For any* image uploaded to Supabase Storage, the returned URL SHALL be a valid HTTP/HTTPS URL pointing to the maritime-docs bucket.
**Validates: Requirements 2.2, 2.3**

### Property 8: Extraction Stores Text with Embedding
*For any* successful Vision extraction, the database SHALL store both the extracted text (non-empty) and its embedding vector (768 dimensions).
**Validates: Requirements 3.4**

### Property 9: Storage Folder Structure
*For any* uploaded image, the storage path SHALL follow the pattern `{document_id}/page_{number}.jpg`.
**Validates: Requirements 4.3**

### Property 10: Schema Contains Required Fields
*For any* record in knowledge_embeddings table after migration, the schema SHALL include columns: text, embedding, image_url, page_number, document_id.
**Validates: Requirements 4.2**

### Property 11: Response Metadata Contains Evidence Images
*For any* RAG response with visual content sources, the response metadata SHALL contain an evidence_images array with url and page_number for each image.
**Validates: Requirements 6.2**

### Property 12: Maximum Evidence Images Per Response
*For any* RAG response, the evidence_images array SHALL contain at most 3 items.
**Validates: Requirements 6.4**

### Property 13: Ingestion Logs Progress
*For any* PDF ingestion process, the system SHALL log progress messages in format "Processing page X of Y" for each page.
**Validates: Requirements 7.1**

### Property 14: Ingestion Summary Contains Counts
*For any* completed ingestion, the IngestionResult SHALL contain total_pages, successful_pages, and failed_pages with sum(successful + failed) = total.
**Validates: Requirements 7.4**

### Property 15: Resume From Last Successful Page
*For any* interrupted ingestion, when resumed, the system SHALL start from the last successfully processed page (not from beginning).
**Validates: Requirements 7.5**

### Property 16: No Text Content Skipped
*For any* PDF page with visible text, the Vision extraction SHALL produce non-empty text output with length proportional to visible content.
**Validates: Requirements 8.5**

## Error Handling

### Rasterization Errors
- **Corrupted PDF**: Log error, skip document, notify admin
- **Memory overflow**: Process pages in batches of 10
- **Missing poppler**: Fail fast with clear error message

### Storage Errors
- **Upload failure**: Retry up to 3 times with exponential backoff
- **Bucket not found**: Create bucket if not exists
- **Quota exceeded**: Alert admin, pause ingestion

### Vision Extraction Errors
- **API timeout**: Retry once with longer timeout
- **Rate limit**: Implement request throttling (10 req/min)
- **Invalid response**: Log and skip page with notification

### Database Errors
- **Connection failure**: Use connection pool with retry
- **Migration failure**: Rollback to previous state
- **Constraint violation**: Log and skip record

## Testing Strategy

### Property-Based Testing (Hypothesis)

The testing strategy uses **Hypothesis** library for property-based testing to verify correctness properties.

Each property-based test MUST:
1. Be tagged with comment referencing the correctness property
2. Run minimum 100 iterations
3. Use format: `**Feature: multimodal-rag-vision, Property {number}: {property_text}**`

```python
# Example property test structure
from hypothesis import given, strategies as st, settings

@settings(max_examples=100)
@given(st.binary(min_size=100))  # Random PDF-like data
def test_pdf_page_count_equals_image_count(pdf_data):
    """
    **Feature: multimodal-rag-vision, Property 6: PDF Page Count Equals Image Count**
    **Validates: Requirements 2.1**
    """
    # Test implementation
    pass
```

### Unit Tests

Unit tests cover specific examples and edge cases:
- Empty PDF handling
- Single page PDF
- PDF with only images (no text)
- Malformed table structures
- Missing headings

### Integration Tests

Integration tests verify end-to-end flows:
- Full ingestion pipeline (PDF → Database)
- Search with evidence images
- Health check for hybrid infrastructure
