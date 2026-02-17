# Design Document: Project Restructure

## Overview

Tài liệu này mô tả thiết kế chi tiết cho việc tái cấu trúc dự án maritime-ai-service. Kế hoạch được chia thành 4 giai đoạn (P0-P3) với mức độ ưu tiên giảm dần.

## Architecture

### Current State
```
maritime-ai-service/
├── scripts/                    # Mixed: tests + utilities + migrations
│   ├── test_*.py              # ~60 test files mixed together
│   ├── *.sql                  # Migration scripts
│   ├── check_*.py             # Utility scripts
│   └── import_*.py            # Data scripts
├── tests/
│   ├── e2e/                   # Empty
│   ├── integration/           # Empty
│   ├── unit/                  # Empty
│   └── property/              # Has property tests
├── app/engine/
│   ├── agents/chat_agent.py   # Legacy - unused
│   ├── graph.py               # Legacy - unused
│   └── semantic_memory.py     # 1,298 lines - needs split
└── docs/
    ├── SEMANTIC_MEMORY_V03_GUIDE.md
    ├── SEMANTIC_MEMORY_V04_GUIDE.md
    └── SEMANTIC_MEMORY_V05_GUIDE.md
```

### Target State
```
maritime-ai-service/
├── scripts/
│   ├── migrations/            # SQL files only
│   ├── data/                  # Data import scripts
│   └── utils/                 # Utility scripts
├── tests/
│   ├── e2e/                   # End-to-end tests
│   ├── integration/           # Integration tests
│   ├── unit/                  # Unit tests
│   └── property/              # Property-based tests
├── archive/                   # Archived legacy code
│   ├── chat_agent.py
│   └── graph.py
├── app/engine/
│   └── semantic_memory/       # Refactored module
│       ├── __init__.py
│       ├── core.py
│       ├── context.py
│       └── extraction.py
└── docs/
    └── SEMANTIC_MEMORY_ARCHITECTURE.md
```

## Components and Interfaces

### P0: Test File Categorization

| Pattern | Destination | Examples |
|---------|-------------|----------|
| `*_e2e.py` | tests/e2e/ | test_chat_e2e.py, test_humanization_e2e.py |
| `*_production*.py` | tests/e2e/ | test_deep_reasoning_production.py |
| `*_integration.py` | tests/integration/ | test_guardian_integration.py |
| `test_guardian_*.py` | tests/integration/ | test_guardian_agent.py |
| `test_hybrid_search.py` | tests/integration/ | - |
| `test_*.py` (remaining) | tests/unit/ | test_intent_classifier.py |

### P0: Scripts Categorization

| Pattern | Destination | Examples |
|---------|-------------|----------|
| `*.sql` | scripts/migrations/ | create_*.sql, upgrade_*.sql |
| `import_*.py`, `reingest_*.py` | scripts/data/ | import_colregs.py |
| `check_*.py`, `verify_*.py` | scripts/utils/ | check_neo4j_data.py |

### P1: Legacy Code Verification

Before archiving, verify these conditions:
1. `chat_service.py` only imports `UnifiedAgent`
2. No active references to `ChatAgent` or `AgentOrchestrator`
3. No fallback logic using legacy agents

### P2: Semantic Memory Module Structure

```python
# app/engine/semantic_memory/__init__.py
from .core import SemanticMemoryEngine

__all__ = ["SemanticMemoryEngine"]

# app/engine/semantic_memory/core.py
class SemanticMemoryEngine:
    """Main facade class - maintains backward compatibility"""
    
# app/engine/semantic_memory/context.py
class ContextBuilder:
    """Handles retrieve_context and context building logic"""
    
# app/engine/semantic_memory/extraction.py
class FactExtractor:
    """Handles fact extraction from conversations"""
```

## Data Models

No new data models required. This is a structural refactoring.

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Import Backward Compatibility
*For any* code that imports SemanticMemoryEngine, both import paths (`from app.engine.semantic_memory import SemanticMemoryEngine` and `from app.engine.semantic_memory.core import SemanticMemoryEngine`) SHALL return the same class object.
**Validates: Requirements 3.2, 3.3**

### Property 2: Test Discovery Completeness
*For any* test file moved from scripts/ to tests/, pytest SHALL discover and be able to execute that test file.
**Validates: Requirements 1.1, 5.1**

## Error Handling

### File Move Errors
- If destination directory doesn't exist, create it
- If file already exists at destination, skip with warning
- Log all file operations for audit trail

### Import Errors After Refactoring
- Maintain backward-compatible imports in `__init__.py`
- Add deprecation warnings for old import paths if needed

### Archive Errors
- Create archive/ directory if not exists
- Preserve original file timestamps
- Keep git history by using `git mv` when possible

## Testing Strategy

### Unit Testing
- Verify file categorization logic
- Test import compatibility after refactoring
- Validate documentation merge logic

### Property-Based Testing
Using `hypothesis` library (already in project):

1. **Import Compatibility Property**: Test that SemanticMemoryEngine can be imported from multiple paths and returns identical class
2. **Test Discovery Property**: Verify all test files are discoverable by pytest

### Integration Testing
- Run full test suite after each phase
- Verify server starts correctly
- Test /chat endpoint functionality
- Verify Guardian Agent works
- Verify RAG search works

### Verification Commands
```bash
# After P0: Verify test discovery
pytest tests/ --collect-only

# After P1: Verify app works
pytest tests/ -v
uvicorn app.main:app --reload

# After P2: Verify imports
python -c "from app.engine.semantic_memory import SemanticMemoryEngine; print('OK')"
python -c "from app.engine.semantic_memory.core import SemanticMemoryEngine; print('OK')"

# Full verification
python scripts/utils/verify_all_systems.py
```
