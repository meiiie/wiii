# Design Document: Hybrid Text/Vision Detection

## Overview

Tính năng Hybrid Text/Vision Detection tối ưu hóa pipeline ingestion bằng cách phân loại thông minh các trang PDF. Thay vì gửi tất cả trang qua Gemini Vision API (tốn chi phí), hệ thống sẽ:
- **Text-only pages**: Extract trực tiếp bằng PyMuPDF (miễn phí, nhanh)
- **Visual pages**: Gửi qua Gemini Vision (chính xác cho bảng/hình)

Mục tiêu: Giảm 50-70% API calls, tiết kiệm chi phí đáng kể.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID TEXT/VISION INGESTION PIPELINE                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   PDF Document                                                               │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────┐                                                        │
│   │ PyMuPDF Open    │                                                        │
│   │ (fitz.open)     │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ PAGE ANALYZER   │  ← NEW COMPONENT                                       │
│   │                 │                                                        │
│   │ Checks:         │                                                        │
│   │ • Has images?   │                                                        │
│   │ • Has tables?   │                                                        │
│   │ • Has diagrams? │                                                        │
│   │ • Maritime kw?  │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│     ┌──────┴──────┐                                                          │
│     │             │                                                          │
│     ▼             ▼                                                          │
│ ┌────────┐   ┌────────┐                                                      │
│ │ TEXT   │   │ VISUAL │                                                      │
│ │ ONLY   │   │CONTENT │                                                      │
│ └───┬────┘   └───┬────┘                                                      │
│     │            │                                                           │
│     ▼            ▼                                                           │
│ ┌────────────┐ ┌────────────┐                                                │
│ │ DIRECT     │ │ VISION     │                                                │
│ │ EXTRACTION │ │ EXTRACTION │                                                │
│ │ (PyMuPDF)  │ │ (Gemini)   │                                                │
│ │ FREE ✓     │ │ PAID $     │                                                │
│ └─────┬──────┘ └─────┬──────┘                                                │
│       │              │                                                       │
│       └──────┬───────┘                                                       │
│              ▼                                                               │
│   ┌─────────────────┐                                                        │
│   │ QUALITY CHECK   │  ← Fallback if direct extraction fails                 │
│   │ min_length=100  │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ SEMANTIC        │                                                        │
│   │ CHUNKING        │  (Same pipeline for both methods)                      │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ EMBEDDING +     │                                                        │
│   │ STORE IN NEON   │                                                        │
│   └─────────────────┘                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. PageAnalyzer (NEW)

```python
@dataclass
class PageAnalysisResult:
    """Result of page content analysis"""
    page_number: int
    has_images: bool
    has_tables: bool
    has_diagrams: bool
    has_maritime_signals: bool
    text_length: int
    recommended_method: str  # "direct" or "vision"
    confidence: float  # 0.0-1.0

class PageAnalyzer:
    """Analyzes PDF pages to determine optimal extraction method"""
    
    # Visual content indicators
    TABLE_PATTERNS = [r'\|.*\|.*\|', r'┌|┐|└|┘|├|┤|─|│']
    DIAGRAM_KEYWORDS = ['hình', 'figure', 'sơ đồ', 'biểu đồ', 'diagram']
    MARITIME_KEYWORDS = ['đèn', 'tín hiệu', 'cờ', 'còi', 'light', 'signal']
    
    def analyze_page(self, page: fitz.Page) -> PageAnalysisResult:
        """Analyze a single page and recommend extraction method"""
        
    def should_use_vision(self, result: PageAnalysisResult) -> bool:
        """Determine if Vision API should be used"""
```

### 2. Updated MultimodalIngestionService

```python
class MultimodalIngestionService:
    def __init__(self, ..., page_analyzer: PageAnalyzer = None):
        self.page_analyzer = page_analyzer or PageAnalyzer()
    
    async def _process_page(self, page, image, ...) -> PageResult:
        # Analyze page first
        analysis = self.page_analyzer.analyze_page(page)
        
        if self.page_analyzer.should_use_vision(analysis):
            # Use Vision extraction (existing flow)
            text = await self._extract_with_vision(image)
        else:
            # Use direct extraction (new flow)
            text = self._extract_direct(page)
            
            # Quality check - fallback if needed
            if len(text.strip()) < self.min_text_length:
                text = await self._extract_with_vision(image)
        
        # Continue with chunking (same for both)
        chunks = await self.chunker.chunk_page_content(text, metadata)
```

### 3. IngestionResult Enhancement

```python
@dataclass
class IngestionResult:
    document_id: str
    total_pages: int
    successful_pages: int
    failed_pages: int
    errors: List[str]
    
    # NEW: Extraction method tracking
    vision_pages: int = 0      # Pages processed via Vision
    direct_pages: int = 0      # Pages processed via Direct
    fallback_pages: int = 0    # Pages that fell back to Vision
    
    @property
    def api_savings_percent(self) -> float:
        """Calculate estimated API cost savings"""
        if self.total_pages == 0:
            return 0.0
        return (self.direct_pages / self.total_pages) * 100
```

## Data Models

### PageAnalysisResult

| Field | Type | Description |
|-------|------|-------------|
| page_number | int | 1-indexed page number |
| has_images | bool | Page contains embedded images |
| has_tables | bool | Page contains table structures |
| has_diagrams | bool | Page contains diagram references |
| has_maritime_signals | bool | Page contains maritime signal keywords |
| text_length | int | Length of extractable text |
| recommended_method | str | "direct" or "vision" |
| confidence | float | Confidence in recommendation (0.0-1.0) |

### Configuration Settings

```python
# In app/core/config.py
class Settings:
    # Hybrid detection settings
    hybrid_detection_enabled: bool = True
    min_text_length_for_direct: int = 100
    force_vision_mode: bool = False
    
    # Visual content patterns (configurable)
    table_patterns: List[str] = [r'\|.*\|.*\|']
    diagram_keywords: List[str] = ['hình', 'figure', 'sơ đồ']
    maritime_keywords: List[str] = ['đèn', 'tín hiệu', 'cờ']
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Page Classification Completeness
*For any* PDF page processed by Page_Analyzer, the result SHALL contain a recommended_method that is either "direct" or "vision" - no page should be left unclassified.
**Validates: Requirements 1.1**

### Property 2: Visual Content Detection Implies Vision
*For any* PDF page that contains embedded images, table patterns, diagram keywords, or maritime signal keywords, the Page_Analyzer SHALL recommend "vision" extraction method.
**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

### Property 3: Plain Text Implies Direct
*For any* PDF page that contains only plain text without any visual indicators (no images, no tables, no diagram keywords, no maritime keywords), the Page_Analyzer SHALL recommend "direct" extraction method.
**Validates: Requirements 2.5**

### Property 4: Routing Follows Classification
*For any* page classification result, the Multimodal_Ingestion_Service SHALL use the extraction method matching the classification (direct → PyMuPDF, vision → Gemini Vision).
**Validates: Requirements 1.2, 1.3**

### Property 5: Force Vision Override
*For any* ingestion with force_vision_mode enabled, all pages SHALL use Vision extraction regardless of Page_Analyzer classification.
**Validates: Requirements 3.3**

### Property 6: Fallback on Short Text
*For any* page where direct extraction produces text shorter than min_text_length threshold, the system SHALL automatically fallback to Vision extraction.
**Validates: Requirements 5.3**

### Property 7: Method Count Consistency
*For any* completed ingestion, the equation vision_pages + direct_pages + fallback_pages SHALL equal successful_pages.
**Validates: Requirements 4.1**

### Property 8: Savings Calculation
*For any* completed ingestion with total_pages > 0, api_savings_percent SHALL equal (direct_pages / total_pages) * 100.
**Validates: Requirements 4.2**

### Property 9: Direct Extraction Text Quality
*For any* text-only PDF page, direct extraction via PyMuPDF SHALL preserve Vietnamese characters correctly and maintain document structure (headings detected, paragraphs separated).
**Validates: Requirements 5.1, 5.2**

### Property 10: Chunking Consistency
*For any* extracted text, the semantic chunking pipeline SHALL produce identical chunk structure regardless of whether the text came from direct or vision extraction.
**Validates: Requirements 5.4**

## Error Handling

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| PyMuPDF fails to open page | Log error, skip page, increment failed_pages |
| Direct extraction returns empty | Fallback to Vision extraction |
| Direct extraction returns garbled text | Detect via encoding check, fallback to Vision |
| Vision extraction fails after fallback | Log error, skip page |
| Page analysis throws exception | Default to Vision (safe fallback) |

## Testing Strategy

### Unit Tests
- Test PageAnalyzer with various page types (text-only, images, tables)
- Test configuration loading and validation
- Test fallback logic triggers correctly

### Property-Based Tests (Hypothesis)
- Property 1: Classification completeness
- Property 2: Image detection → vision
- Property 3: Table detection → vision
- Property 5: Fallback triggers
- Property 6: Method tracking accuracy
- Property 7: Savings calculation

### Integration Tests
- End-to-end ingestion with mixed PDF (text + visual pages)
- Verify chunks are identical quality regardless of extraction method
- Verify cost savings reporting accuracy
