# Semantic Chunking Design

## Overview

Thiết kế chi tiết cho việc nâng cấp hệ thống Multimodal RAG từ "1 page = 1 chunk" sang "Semantic Chunking". Feature này giải quyết vấn đề critical được xác định trong báo cáo kỹ thuật: mỗi trang PDF đang được xử lý như một đơn vị duy nhất với 1 embedding, dẫn đến semantic search kém chính xác.

### Current State
```
┌─────────────────────────────────────────────────────────────┐
│                    CURRENT ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────┤
│  PDF Page → Vision Extract → 1 Embedding → 1 DB Row         │
│                                                              │
│  PROBLEMS:                                                   │
│  • 1 page = 1 chunk (quá lớn cho semantic search)           │
│  • Không phân loại content type                             │
│  • Không có confidence scoring                              │
│  • Search accuracy thấp                                      │
└─────────────────────────────────────────────────────────────┘
```

### Target State
```
┌─────────────────────────────────────────────────────────────┐
│                    TARGET ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────┤
│  PDF Page → Vision Extract → Semantic Chunker               │
│                                    ↓                         │
│              Multiple Chunks (500-800 chars each)           │
│                                    ↓                         │
│              N Embeddings → N DB Rows per page              │
│                                                              │
│  BENEFITS:                                                   │
│  • Focused chunks cho semantic search                       │
│  • Content type classification                              │
│  • Confidence scoring                                        │
│  • Maritime document hierarchy extraction                   │
└─────────────────────────────────────────────────────────────┘
```

## Architecture

### Semantic Chunking Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SEMANTIC CHUNKING PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Vision Extraction Output (Full Page Text)                                 │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 1: TEXT SPLITTING (RecursiveCharacterTextSplitter)              │   │
│   │   • chunk_size: 800 chars                                            │   │
│   │   • chunk_overlap: 100 chars                                         │   │
│   │   • Preserve sentence boundaries                                     │   │
│   │   • Output: List[str] raw chunks                                     │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 2: CONTENT TYPE DETECTION                                       │   │
│   │   • Detect: text, table, heading, diagram_reference, formula         │   │
│   │   • Maritime-specific patterns (Điều, Khoản, Rule)                   │   │
│   │   • Output: content_type per chunk                                   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 3: CONFIDENCE SCORING                                           │   │
│   │   • Base score from chunk length                                     │   │
│   │   • Boost for structured content                                     │   │
│   │   • Penalty for too short/long chunks                                │   │
│   │   • Output: confidence_score (0.0-1.0)                               │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 4: HIERARCHY EXTRACTION                                         │   │
│   │   • Extract: article, clause, point, rule numbers                    │   │
│   │   • Build metadata JSONB                                             │   │
│   │   • Output: section_hierarchy dict                                   │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ STEP 5: EMBEDDING & STORAGE                                          │   │
│   │   • Generate embedding per chunk                                     │   │
│   │   • Store with: chunk_index, content_type, confidence_score          │   │
│   │   • Maintain image_url reference from page                           │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. SemanticChunker Service

```python
class SemanticChunker:
    """Semantic chunking service optimized for maritime documents"""
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]
        )
        self.maritime_patterns = {...}  # Regex patterns for Điều, Khoản, Rule
    
    async def chunk_page_content(
        self, 
        text: str, 
        page_metadata: Dict[str, Any]
    ) -> List[ChunkResult]:
        """Split page content into semantic chunks with metadata"""
        pass
    
    def _detect_content_type(self, text: str) -> str:
        """Detect content type: text, table, heading, diagram_reference, formula"""
        pass
    
    def _calculate_confidence(self, chunk: str, content_type: str) -> float:
        """Calculate confidence score (0.0-1.0)"""
        pass
    
    def _extract_document_hierarchy(self, chunk: str) -> Dict[str, Any]:
        """Extract article/clause/point/rule numbers"""
        pass
```

### 2. ChunkResult Data Model

```python
@dataclass
class ChunkResult:
    """Result of semantic chunking for a single chunk"""
    chunk_index: int
    content: str
    content_type: str  # text, table, heading, diagram_reference, formula
    confidence_score: float  # 0.0-1.0
    metadata: Dict[str, Any]  # section_hierarchy, word_count, etc.
```

### 3. Enhanced MultimodalIngestionService

```python
class MultimodalIngestionService:
    def __init__(self, ..., chunker: SemanticChunker):
        self.chunker = chunker
    
    async def _process_page_with_chunking(
        self,
        image: Image.Image,
        document_id: str,
        page_number: int
    ) -> PageResult:
        """Process page with semantic chunking"""
        # 1. Upload image to Supabase
        # 2. Extract text using Vision
        # 3. Apply semantic chunking
        # 4. Generate embedding per chunk
        # 5. Store each chunk in database
        pass
```

## Data Models

### Database Schema Changes

```sql
-- Migration: 003_add_chunking_columns.py
-- Add columns for semantic chunking support

ALTER TABLE knowledge_embeddings
ADD COLUMN content_type VARCHAR(50) DEFAULT 'text',
ADD COLUMN confidence_score FLOAT DEFAULT 1.0;

-- Create composite index for chunk ordering
CREATE INDEX idx_knowledge_chunks_ordering 
ON knowledge_embeddings(document_id, page_number, chunk_index);

-- Create index for content type filtering
CREATE INDEX idx_knowledge_chunks_content_type 
ON knowledge_embeddings(content_type);

-- Create index for confidence filtering
CREATE INDEX idx_knowledge_chunks_confidence 
ON knowledge_embeddings(confidence_score);
```

### Pydantic Models

```python
class ChunkResult(BaseModel):
    """Result of semantic chunking"""
    chunk_index: int
    content: str
    content_type: str = "text"
    confidence_score: float = 1.0
    metadata: Dict[str, Any] = {}

class PageChunkingResult(BaseModel):
    """Result of chunking a single page"""
    page_number: int
    total_chunks: int
    chunks: List[ChunkResult]
    image_url: Optional[str] = None
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Chunk Size Bounds
*For any* text input, all generated chunks SHALL have length between MIN_CHUNK_SIZE (50) and CHUNK_SIZE + CHUNK_OVERLAP (900) characters.
**Validates: Requirements 1.1, 1.5**

### Property 2: Chunk Count Increases with Text Length
*For any* text input, the number of chunks generated SHALL be proportional to text length (approximately text_length / chunk_size).
**Validates: Requirements 1.4**

### Property 3: Content Type Valid Enum
*For any* chunk processed, the content_type SHALL be one of: "text", "table", "heading", "diagram_reference", "formula".
**Validates: Requirements 2.1**

### Property 4: Table Detection Accuracy
*For any* text containing Markdown table syntax (| characters and --- separators), the content_type SHALL be "table".
**Validates: Requirements 2.2**

### Property 5: Heading Detection for Maritime Patterns
*For any* text containing maritime legal patterns (Điều X, Khoản X, Rule X), the content_type SHALL be "heading".
**Validates: Requirements 2.3, 2.4**

### Property 6: Confidence Score Bounds
*For any* chunk, the confidence_score SHALL be between 0.0 and 1.0 inclusive.
**Validates: Requirements 3.1**

### Property 7: Short Chunk Confidence Penalty
*For any* chunk with fewer than 50 characters, the confidence_score SHALL be 0.6 or lower.
**Validates: Requirements 3.2**

### Property 8: Long Chunk Confidence Penalty
*For any* chunk with more than 1000 characters, the confidence_score SHALL be 0.7 or lower.
**Validates: Requirements 3.3**

### Property 9: Structured Content Confidence Boost
*For any* chunk with content_type "heading" or "table", the confidence_score SHALL be at least 20% higher than base score.
**Validates: Requirements 3.4**

### Property 10: Chunk Index Sequential
*For any* page with N chunks, the chunk_index values SHALL be sequential integers from 0 to N-1.
**Validates: Requirements 4.4**

### Property 11: Article Number Extraction
*For any* text containing "Điều X" or "Article X" pattern, the metadata.section_hierarchy SHALL contain the article number.
**Validates: Requirements 5.1**

### Property 12: Clause Number Extraction
*For any* text containing "Khoản X" or "Clause X" pattern, the metadata.section_hierarchy SHALL contain the clause number.
**Validates: Requirements 5.2**

### Property 13: Database Round-Trip Consistency
*For any* chunk stored in database, reading it back SHALL return identical content, content_type, and confidence_score.
**Validates: Requirements 2.5, 3.5, 5.5**

## Error Handling

### Chunking Errors
- **Empty text**: Return empty list, log warning
- **Text too short**: Return single chunk with full text
- **Regex timeout**: Use fallback simple splitting

### Content Detection Errors
- **Unknown pattern**: Default to "text" type
- **Multiple types detected**: Use highest priority type

### Storage Errors
- **Database connection failure**: Retry with exponential backoff
- **Constraint violation**: Log and skip chunk

## Testing Strategy

### Property-Based Testing (Hypothesis)

The testing strategy uses **Hypothesis** library for property-based testing to verify correctness properties.

Each property-based test MUST:
1. Be tagged with comment referencing the correctness property
2. Run minimum 100 iterations
3. Use format: `**Feature: semantic-chunking, Property {number}: {property_text}**`

```python
from hypothesis import given, strategies as st, settings

@settings(max_examples=100)
@given(st.text(min_size=100, max_size=5000))
def test_chunk_size_bounds(text):
    """
    **Feature: semantic-chunking, Property 1: Chunk Size Bounds**
    **Validates: Requirements 1.1, 1.5**
    """
    chunker = SemanticChunker()
    chunks = chunker.chunk_text(text)
    for chunk in chunks:
        assert 50 <= len(chunk.content) <= 900
```

### Unit Tests

Unit tests cover specific examples and edge cases:
- Empty text handling
- Single sentence text
- Text with only tables
- Text with only headings
- Mixed content types

### Integration Tests

Integration tests verify end-to-end flows:
- Full ingestion pipeline with chunking
- Search with chunked results
- Evidence image association

