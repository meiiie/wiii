# Design Document: Managed Memory List

## Overview

Nâng cấp module Semantic Memory từ v0.3 lên v0.4 với Managed Memory List theo chuẩn Industry (Qwen/OpenAI). Hệ thống sẽ implement Memory Capping (50 facts/user), True Deduplication (Upsert), và Memory Management API.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MANAGED MEMORY LIST v0.4                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   User Message                                                               │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    FACT EXTRACTION (LLM)                             │   │
│   │  • Extract atomic facts from message                                 │   │
│   │  • Validate fact_type (6 allowed types only)                        │   │
│   │  • Filter unsupported types                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    UPSERT LOGIC                                      │   │
│   │  • Check if fact_type exists for user                               │   │
│   │  • If exists: UPDATE content, embedding, updated_at                 │   │
│   │  • If not: INSERT new fact                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    MEMORY CAPPING                                    │   │
│   │  • Count USER_FACT entries for user                                 │   │
│   │  • If count > 50: Delete oldest (FIFO)                              │   │
│   │  • Log deletions for audit                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│        │                                                                     │
│        ▼                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                    STORAGE (pgvector)                                │   │
│   │  • semantic_memories table                                           │   │
│   │  • Vector embeddings (768 dims)                                      │   │
│   │  • Metadata with fact_type                                          │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. SemanticMemoryEngine (Updated)

```python
class SemanticMemoryEngine:
    # Configuration
    MAX_USER_FACTS = 50  # Memory cap
    ALLOWED_FACT_TYPES = {"name", "role", "level", "goal", "preference", "weakness"}
    
    async def store_user_fact_upsert(
        self,
        user_id: str,
        fact_content: str,
        fact_type: str,
        confidence: float = 0.9,
        session_id: Optional[str] = None
    ) -> bool:
        """
        Store or update a user fact using upsert logic.
        
        1. Validate fact_type is in ALLOWED_FACT_TYPES
        2. Check if fact of same type exists
        3. If exists: Update content, embedding, updated_at
        4. If not: Insert new fact
        5. Enforce memory cap (delete oldest if > 50)
        """
        pass
    
    async def _enforce_memory_cap(self, user_id: str) -> int:
        """
        Enforce memory cap by deleting oldest facts.
        
        Returns number of facts deleted.
        """
        pass
    
    def _validate_fact_type(self, fact_type: str) -> Optional[str]:
        """
        Validate and normalize fact_type.
        
        Returns normalized type or None if invalid.
        """
        pass
```

### 2. SemanticMemoryRepository (Updated)

```python
class SemanticMemoryRepository:
    def find_fact_by_type(
        self,
        user_id: str,
        fact_type: str
    ) -> Optional[SemanticMemory]:
        """Find existing fact by user_id and fact_type."""
        pass
    
    def update_fact(
        self,
        fact_id: UUID,
        content: str,
        embedding: List[float],
        metadata: dict
    ) -> bool:
        """Update existing fact content and embedding."""
        pass
    
    def delete_oldest_facts(
        self,
        user_id: str,
        count: int
    ) -> int:
        """Delete N oldest USER_FACT entries for user."""
        pass
    
    def get_all_user_facts(
        self,
        user_id: str
    ) -> List[SemanticMemorySearchResult]:
        """Get all facts for user (for API endpoint)."""
        pass
```

### 3. Memory API Endpoint

```python
# app/api/v1/memories.py

@router.get("/memories/{user_id}")
async def get_user_memories(
    user_id: str,
    api_key: str = Depends(verify_api_key)
) -> MemoryListResponse:
    """
    Get all stored facts for a user.
    
    Returns:
        [
            {"id": "...", "type": "name", "value": "Minh", "created_at": "..."},
            {"id": "...", "type": "goal", "value": "Học COLREGs", "created_at": "..."}
        ]
    """
    pass
```

## Data Models

### MemoryListResponse

```python
class MemoryItem(BaseModel):
    id: str
    type: str  # fact_type
    value: str  # content
    created_at: datetime

class MemoryListResponse(BaseModel):
    data: List[MemoryItem]
    total: int
```

### Updated FactType Enum

```python
class FactType(str, Enum):
    NAME = "name"
    ROLE = "role"           # Sinh viên/Giáo viên
    LEVEL = "level"         # Năm 3, Đại phó...
    GOAL = "goal"           # Mục tiêu học tập
    PREFERENCE = "preference"  # Phong cách học
    WEAKNESS = "weakness"   # Điểm yếu
    
    # Deprecated types (kept for backward compatibility)
    BACKGROUND = "background"  # -> mapped to ROLE
    INTEREST = "interest"      # -> mapped to PREFERENCE
    WEAK_AREA = "weak_area"    # -> mapped to WEAKNESS
    STRONG_AREA = "strong_area"  # -> ignored
    LEARNING_STYLE = "learning_style"  # -> mapped to PREFERENCE
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Memory Capping Invariant
*For any* user, after any sequence of fact storage operations, the total number of USER_FACT entries for that user SHALL never exceed 50.
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Upsert Uniqueness
*For any* user and fact_type, there SHALL exist at most one fact entry with that type. Storing a new fact with an existing type SHALL update the existing entry rather than create a duplicate.
**Validates: Requirements 2.1, 2.2, 2.3**

### Property 3: Timestamp Update on Upsert
*For any* fact that is updated via upsert, the updated_at timestamp SHALL be greater than or equal to the original created_at timestamp.
**Validates: Requirements 2.4**

### Property 4: API Response Completeness
*For any* user with N facts, the GET /api/v1/memories/{user_id} endpoint SHALL return exactly N items, each containing id, type, value, and created_at fields.
**Validates: Requirements 3.1, 3.2**

### Property 5: Fact Type Validation
*For any* fact extraction attempt, only facts with type in {name, role, level, goal, preference, weakness} SHALL be stored. Facts with unsupported types SHALL be ignored.
**Validates: Requirements 4.1, 4.2, 4.3**

### Property 6: FIFO Eviction Order
*For any* user at memory cap (50 facts), when a new fact is added, the fact with the oldest created_at timestamp SHALL be deleted.
**Validates: Requirements 1.2**

## Error Handling

| Error | HTTP Status | Response |
|-------|-------------|----------|
| User not found | 200 | Empty array `[]` |
| Unauthorized | 401 | `{"error": "unauthorized"}` |
| Invalid fact_type | Ignored | Fact not stored, no error |
| Database error | 500 | `{"error": "internal_error"}` |

## Testing Strategy

### Property-Based Testing (Hypothesis)

Sử dụng Hypothesis library để test các correctness properties:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.sampled_from(["name", "role", "level", "goal", "preference", "weakness"]), min_size=60, max_size=100))
def test_memory_cap_invariant(fact_types):
    """
    **Feature: managed-memory-list, Property 1: Memory Capping Invariant**
    
    For any sequence of fact storage operations, 
    user fact count never exceeds 50.
    """
    # Store all facts
    for fact_type in fact_types:
        engine.store_user_fact_upsert(user_id, f"value_{fact_type}", fact_type)
    
    # Verify cap
    count = repository.count_user_memories(user_id, MemoryType.USER_FACT)
    assert count <= 50
```

### Unit Tests

- Test upsert creates new fact when none exists
- Test upsert updates existing fact of same type
- Test memory cap deletes oldest when at limit
- Test API returns correct structure
- Test fact_type validation rejects invalid types
