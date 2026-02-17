# Design Document: Insight Memory Engine

## Overview

Nâng cấp Semantic Memory Engine từ lưu trữ "Atomic Facts" sang "Behavioral Insights". Hệ thống mới sẽ:
1. Trích xuất insights sâu về phong cách học tập, lỗ hổng kiến thức, sự thay đổi mục tiêu
2. Tự động consolidate memories khi gần đầy (40/50)
3. Enforce hard limit 50 với cơ chế last_accessed
4. Categorize insights để retrieval hiệu quả

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INSIGHT MEMORY ENGINE v0.5                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User Message                                                               │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    INSIGHT EXTRACTOR                                 │   │
│   │  • New extraction prompt (behavioral focus)                          │   │
│   │  • Categories: learning_style, knowledge_gap, goal_evolution, etc.   │   │
│   │  • Quality validation (min 20 chars, complete sentence)              │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    INSIGHT VALIDATOR                                 │   │
│   │  • Check for behavioral content                                      │   │
│   │  • Reject atomic facts (too short)                                   │   │
│   │  • Detect duplicates → Merge                                         │   │
│   │  • Detect contradictions → Evolution note                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    MEMORY MANAGER                                    │   │
│   │  • Check count (40/50 → Consolidation)                               │   │
│   │  • Hard limit 50 enforcement                                         │   │
│   │  • Update last_accessed on retrieval                                 │   │
│   │  • FIFO fallback when consolidation fails                            │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    MEMORY CONSOLIDATOR                               │   │
│   │  • Trigger at 40/50 memories                                         │   │
│   │  • LLM rewrite to merge duplicates                                   │   │
│   │  • Target: 30 core items                                             │   │
│   │  • Preserve recent + relevant                                        │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. InsightExtractor

```python
class InsightExtractor:
    """Extract behavioral insights from user messages."""
    
    INSIGHT_CATEGORIES = [
        "learning_style",    # Phong cách học tập
        "knowledge_gap",     # Lỗ hổng kiến thức
        "goal_evolution",    # Sự thay đổi mục tiêu
        "habit",             # Thói quen học tập
        "preference"         # Sở thích cá nhân
    ]
    
    async def extract_insights(
        self,
        user_id: str,
        message: str,
        conversation_history: List[str] = None
    ) -> List[Insight]:
        """Extract behavioral insights from message."""
        pass
    
    def _build_insight_prompt(self, message: str, history: List[str]) -> str:
        """Build prompt for insight extraction."""
        pass
```

### 2. InsightValidator

```python
class InsightValidator:
    """Validate and process insights before storage."""
    
    MIN_INSIGHT_LENGTH = 20
    
    def validate(self, insight: Insight) -> ValidationResult:
        """Validate insight quality."""
        pass
    
    def is_behavioral(self, content: str) -> bool:
        """Check if content describes behavior, not just fact."""
        pass
    
    def find_duplicate(
        self,
        insight: Insight,
        existing: List[Insight]
    ) -> Optional[Insight]:
        """Find duplicate or similar insight."""
        pass
    
    def detect_contradiction(
        self,
        insight: Insight,
        existing: List[Insight]
    ) -> Optional[Insight]:
        """Detect if insight contradicts existing one."""
        pass
```

### 3. MemoryConsolidator

```python
class MemoryConsolidator:
    """Consolidate memories when approaching capacity."""
    
    CONSOLIDATION_THRESHOLD = 40
    TARGET_COUNT = 30
    
    async def should_consolidate(self, user_id: str) -> bool:
        """Check if consolidation is needed."""
        pass
    
    async def consolidate(self, user_id: str) -> ConsolidationResult:
        """Run consolidation process."""
        pass
    
    def _build_consolidation_prompt(
        self,
        memories: List[Insight]
    ) -> str:
        """Build prompt for LLM consolidation."""
        pass
```

### 4. Enhanced SemanticMemoryEngine

```python
class SemanticMemoryEngine:
    """Enhanced with Insight Engine capabilities."""
    
    MAX_MEMORIES = 50
    CONSOLIDATION_THRESHOLD = 40
    PRESERVE_DAYS = 7  # Preserve memories accessed within 7 days
    
    def __init__(self):
        self._extractor = InsightExtractor()
        self._validator = InsightValidator()
        self._consolidator = MemoryConsolidator()
    
    async def store_insight(
        self,
        user_id: str,
        insight: Insight
    ) -> bool:
        """Store insight with validation and consolidation check."""
        pass
    
    async def retrieve_insights(
        self,
        user_id: str,
        query: str,
        prioritize_categories: List[str] = None
    ) -> List[Insight]:
        """Retrieve insights with category prioritization."""
        pass
    
    def _update_last_accessed(self, insight_id: UUID) -> None:
        """Update last_accessed timestamp."""
        pass
```

## Data Models

### Insight Model

```python
class InsightCategory(str, Enum):
    LEARNING_STYLE = "learning_style"
    KNOWLEDGE_GAP = "knowledge_gap"
    GOAL_EVOLUTION = "goal_evolution"
    HABIT = "habit"
    PREFERENCE = "preference"

class Insight(BaseModel):
    id: UUID
    user_id: str
    content: str  # Complete sentence describing insight
    category: InsightCategory
    sub_topic: Optional[str] = None  # e.g., "Rule 15", "COLREGs"
    confidence: float = 0.8
    source_messages: List[str] = []  # Messages that led to this insight
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_accessed: datetime
    evolution_notes: List[str] = []  # Track changes over time
    
    class Config:
        from_attributes = True
```

### Database Schema Update

```sql
-- Add new columns to semantic_memories table
ALTER TABLE semantic_memories 
ADD COLUMN IF NOT EXISTS insight_category VARCHAR(50),
ADD COLUMN IF NOT EXISTS sub_topic VARCHAR(100),
ADD COLUMN IF NOT EXISTS last_accessed TIMESTAMP DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS evolution_notes JSONB DEFAULT '[]';

-- Create index for last_accessed queries
CREATE INDEX IF NOT EXISTS idx_semantic_memories_last_accessed 
ON semantic_memories(user_id, last_accessed DESC);

-- Create index for category queries
CREATE INDEX IF NOT EXISTS idx_semantic_memories_category 
ON semantic_memories(user_id, insight_category);
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Insight Format Validation
*For any* extracted insight, the content SHALL be a complete sentence with at least 20 characters describing behavioral or contextual information.
**Validates: Requirements 1.4, 5.1, 5.2**

### Property 2: Consolidation Trigger
*For any* user with memory count >= 40, the system SHALL trigger consolidation before allowing new insertions.
**Validates: Requirements 2.1, 2.3**

### Property 3: Hard Limit Enforcement
*For any* user, the memory count SHALL never exceed 50 items.
**Validates: Requirements 3.1**

### Property 4: Last Accessed Update
*For any* memory retrieval operation, the accessed memory's last_accessed timestamp SHALL be updated to current time.
**Validates: Requirements 3.3**

### Property 5: Recent Memory Preservation
*For any* deletion operation, memories with last_accessed within 7 days SHALL be preserved unless no other option exists.
**Validates: Requirements 3.4**

### Property 6: Category Assignment
*For any* stored insight, the metadata SHALL contain a valid category from the defined set.
**Validates: Requirements 4.1, 4.2**

### Property 7: Duplicate Merge
*For any* insight that duplicates existing content, the system SHALL merge instead of append, resulting in no increase in memory count.
**Validates: Requirements 5.3**

### Property 8: Contradiction Evolution
*For any* insight that contradicts existing insight, the system SHALL update the existing one with an evolution note.
**Validates: Requirements 5.4**

## Error Handling

| Error | Handling |
|-------|----------|
| LLM extraction fails | Return empty list, log error |
| LLM consolidation fails | Fallback to FIFO eviction |
| Database connection fails | Retry 3 times, then fail gracefully |
| Invalid insight format | Reject and log, continue processing |
| Memory limit exceeded | Block insertion, trigger consolidation |

## Testing Strategy

### Unit Tests
- InsightExtractor: Test prompt building, response parsing
- InsightValidator: Test length validation, behavioral detection
- MemoryConsolidator: Test threshold detection, consolidation logic

### Property-Based Tests (Hypothesis)
- Property 1: Generate random insights, verify format validation
- Property 2: Generate user with 40+ memories, verify consolidation triggers
- Property 3: Attempt to exceed 50 memories, verify hard limit
- Property 4: Access memories, verify timestamp updates
- Property 5: Create memories with various dates, verify preservation logic
- Property 6: Store insights, verify category metadata
- Property 7: Create duplicate insights, verify merge behavior
- Property 8: Create contradicting insights, verify evolution notes

### Integration Tests
- End-to-end: Chat → Extract → Validate → Store → Retrieve
- Consolidation flow: Fill to 40 → Trigger → Verify reduction to 30
- Hard limit flow: Fill to 50 → Block → Consolidate → Allow new

### Test Framework
- **Property-based testing**: Hypothesis (Python)
- **Unit testing**: pytest
- **Minimum iterations**: 100 per property test
