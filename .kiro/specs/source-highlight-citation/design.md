# Design Document: Source Highlighting with Citation Jumping

## Overview

Tính năng này mở rộng hệ thống MM-RAG hiện tại để hỗ trợ **Source Highlighting with Citation Jumping** - cho phép frontend hiển thị chính xác vị trí text được trích dẫn trong PDF.

**Scope:** Backend only (Maritime AI Service). Frontend implementation sẽ do team LMS Angular thực hiện.

**Current State:**
- ✅ Evidence Images (Supabase URLs)
- ✅ Page number tracking
- ✅ Chunk indexing
- ❌ Bounding box coordinates

**Target State:**
- ✅ Bounding box extraction từ PyMuPDF
- ✅ Enhanced API response với coordinates
- ✅ Source details endpoint
- ✅ Re-ingestion support

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SOURCE HIGHLIGHTING ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PDF Document                                                               │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────┐                                                        │
│   │ PyMuPDF Extract │  Extract text + bounding boxes                         │
│   │ (fitz)          │  page.get_text("dict") → blocks with bbox              │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ BoundingBox     │  Normalize coords to percentage (0-100)                │
│   │ Normalizer      │  Handle multi-block chunks                             │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ Neon PostgreSQL │  Store in knowledge_embeddings.bounding_boxes          │
│   │ (JSONB column)  │  Format: [{"x0":0,"y0":0,"x1":100,"y1":10}, ...]       │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ Chat API        │  Return sources with bounding_boxes                    │
│   │ /api/v1/chat    │  + Source Details API /api/v1/sources/{node_id}        │
│   └─────────────────┘                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. BoundingBoxExtractor

**Location:** `app/engine/bounding_box_extractor.py`

```python
from dataclasses import dataclass
from typing import List, Optional
import fitz  # PyMuPDF

@dataclass
class BoundingBox:
    """Normalized bounding box (0-100 percentage)."""
    x0: float  # Left edge (0-100)
    y0: float  # Top edge (0-100)
    x1: float  # Right edge (0-100)
    y1: float  # Bottom edge (0-100)
    
    def to_dict(self) -> dict:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1}

class BoundingBoxExtractor:
    """Extract and normalize bounding boxes from PDF pages."""
    
    def extract_text_with_boxes(
        self, 
        page: fitz.Page, 
        text_content: str
    ) -> List[BoundingBox]:
        """
        Extract bounding boxes for text content on a page.
        
        Args:
            page: PyMuPDF page object
            text_content: The text to find bounding boxes for
            
        Returns:
            List of normalized BoundingBox objects
        """
        pass
    
    def normalize_bbox(
        self, 
        bbox: tuple, 
        page_width: float, 
        page_height: float
    ) -> BoundingBox:
        """
        Normalize raw coordinates to percentage (0-100).
        
        Args:
            bbox: Raw coordinates (x0, y0, x1, y1) in points
            page_width: Page width in points
            page_height: Page height in points
            
        Returns:
            Normalized BoundingBox
        """
        pass
    
    def merge_boxes(self, boxes: List[BoundingBox]) -> List[BoundingBox]:
        """
        Merge overlapping or adjacent bounding boxes.
        
        Args:
            boxes: List of bounding boxes
            
        Returns:
            Merged list of bounding boxes
        """
        pass
```

### 2. Enhanced MultimodalIngestionService

**Location:** `app/services/multimodal_ingestion_service.py` (modify existing)

```python
# Add to existing service
async def extract_with_bounding_boxes(
    self,
    pdf_path: str,
    page_num: int,
    chunk_text: str
) -> Optional[List[dict]]:
    """
    Extract bounding boxes for a chunk from PDF page.
    
    Returns:
        List of bounding box dicts or None if extraction fails
    """
    pass
```

### 3. Enhanced Source Schema

**Location:** `app/models/schemas.py` (modify existing)

```python
class SourceWithHighlight(BaseModel):
    """Source with highlighting coordinates."""
    node_id: str
    title: str
    source_type: str
    content_snippet: str
    page_number: Optional[int] = None
    image_url: Optional[str] = None
    document_id: Optional[str] = None
    bounding_boxes: Optional[List[dict]] = None  # NEW
```

### 4. Source Details API

**Location:** `app/api/v1/sources.py` (new file)

```python
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("/{node_id}")
async def get_source_details(node_id: str) -> SourceDetailResponse:
    """
    Get detailed source information including bounding boxes.
    
    Returns:
        Full source metadata for PDF highlighting
    """
    pass
```

## Data Models

### Database Schema Enhancement

```sql
-- Migration: Add bounding_boxes column
ALTER TABLE knowledge_embeddings 
ADD COLUMN bounding_boxes JSONB DEFAULT NULL;

-- Index for queries (optional, for future filtering)
CREATE INDEX idx_knowledge_bounding_boxes 
ON knowledge_embeddings USING GIN(bounding_boxes);

-- Example data format
-- bounding_boxes: [
--   {"x0": 10.5, "y0": 5.2, "x1": 90.3, "y1": 8.7},
--   {"x0": 10.5, "y0": 9.0, "x1": 85.1, "y1": 12.5}
-- ]
```

### API Response Format

```json
{
  "data": {
    "answer": "Theo Điều 15 COLREGs...",
    "sources": [
      {
        "node_id": "chunk_123",
        "title": "Rule 15 - Crossing Situation",
        "source_type": "knowledge_graph",
        "content_snippet": "When two power-driven vessels...",
        "page_number": 15,
        "image_url": "https://supabase.co/.../page_15.jpg",
        "document_id": "colregs_2024",
        "bounding_boxes": [
          {"x0": 10.5, "y0": 45.2, "x1": 90.3, "y1": 52.7}
        ]
      }
    ]
  }
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Bounding Box Coordinate Normalization

*For any* bounding box extracted from a PDF page, all coordinate values (x0, y0, x1, y1) SHALL be normalized to percentage values between 0 and 100 inclusive.

**Validates: Requirements 1.4**

### Property 2: Bounding Box Extraction Completeness

*For any* chunk text that exists on a PDF page, the extraction process SHALL return at least one bounding box, OR return null if extraction fails (graceful fallback).

**Validates: Requirements 1.1, 1.3**

### Property 3: Multi-Block Chunk Coverage

*For any* chunk that spans multiple text blocks on a page, the bounding_boxes array SHALL contain coordinates covering all relevant text blocks.

**Validates: Requirements 1.2**

### Property 4: API Response Schema Consistency

*For any* source returned by the chat API, the response SHALL include page_number, image_url, and bounding_boxes fields in a consistent format (values may be null but fields must exist).

**Validates: Requirements 2.1, 2.3**

### Property 5: Same-Page Source Merging

*For any* response containing multiple chunks from the same page, the system SHALL merge them into a single source entry with combined bounding_boxes array.

**Validates: Requirements 2.4**

### Property 6: Re-ingestion Data Preservation

*For any* document re-ingested with bounding box extraction, the existing embeddings (vector data) SHALL remain unchanged while bounding_boxes are updated.

**Validates: Requirements 4.1, 4.2**

### Property 7: Source Details API Completeness

*For any* valid node_id, the source details API SHALL return all required fields: bounding_boxes, page_number, image_url, text_snippet, and document_id.

**Validates: Requirements 5.1, 5.3**

## Error Handling

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| PDF page extraction fails | Return null for bounding_boxes, log warning |
| Text not found on page | Return empty array [], log debug |
| Invalid coordinates | Skip invalid box, continue with valid ones |
| Database write fails | Retry once, then fail chunk processing |
| API node_id not found | Return 404 with error message |

## Testing Strategy

### Unit Tests

- Test BoundingBoxExtractor with mock PDF pages
- Test coordinate normalization with edge cases (0, 100, negative)
- Test box merging logic with overlapping boxes
- Test API response schema validation

### Property-Based Tests

Using `hypothesis` library for property-based testing:

1. **Normalization Property Test**: Generate random coordinates, verify output is 0-100
2. **Extraction Completeness Test**: Generate PDFs with known text, verify boxes found
3. **Schema Consistency Test**: Generate random sources, verify response format
4. **Merging Property Test**: Generate same-page chunks, verify merge behavior

### Integration Tests

- End-to-end ingestion with bounding box extraction
- Chat API response with bounding_boxes
- Source details API endpoint
- Re-ingestion script verification

### Test Framework

- **Property-Based Testing Library:** `hypothesis` (Python)
- **Unit Testing:** `pytest`
- **Minimum iterations:** 100 per property test
- **Test annotation format:** `**Feature: source-highlight-citation, Property {number}: {property_text}**`
