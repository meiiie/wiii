# READY TO EXECUTE - ARCHITECT TASK-006

**Copy toàn bộ prompt này vào Claude Code session mới và thực thi**

---

## Context

Bạn là **ARCHITECT** agent. Nhiệm vụ của bạn là clean up deprecated code và consolidate overlapping APIs.

**Project:** Maritime AI Tutor Service
**Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`

---

## TASK-006: Clean Deprecated Code & Consolidate APIs

**Priority:** HIGH
**Goal:** Loại bỏ technical debt, simplify codebase

---

## PHASE 1: Investigation

**Chạy các lệnh sau để tìm usages:**

```bash
# Tìm unified_agent usages
grep -rn "unified_agent\|get_unified_agent" app/ --include="*.py"
```

```bash
# Tìm old LLM factory usages
grep -rn "create_tutor_llm\|create_rag_llm\|create_analyzer_llm\|create_extraction_llm" app/ --include="*.py"
```

```bash
# Tìm semantic_memory wrapper usages
grep -rn "from app.engine.semantic_memory import" app/ --include="*.py"
```

**Ghi lại kết quả trước khi làm gì.**

---

## PHASE 2: Analyze unified_agent.py

**File:** `app/engine/unified_agent.py`

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/engine/unified_agent.py
```

**Check:**
1. Có deprecation notice không? (đầu file)
2. Function `get_unified_agent()` ở đâu?
3. Có ai import không? (từ Phase 1)

**Decision:**
- Nếu KHÔNG có production usage → **DELETE FILE**
- Nếu CÓ usage → **ADD DEPRECATION WARNING**

**Nếu cần add warning:**
```python
import warnings

def get_unified_agent():
    """DEPRECATED: Use multi-agent system instead."""
    warnings.warn(
        "get_unified_agent() is deprecated since 2025-12-20. "
        "Use build_multi_agent_graph() from app.engine.multi_agent.graph instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # ... rest of existing code
```

---

## PHASE 3: Consolidate LLM APIs

**Files:**
- `app/engine/llm_factory.py` - Old factory (creates new instances)
- `app/engine/llm_pool.py` - New singleton pool (PREFERRED)

**Step 1:** Read cả 2 files

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_factory.py
```

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_pool.py
```

**Step 2:** Nếu factory functions còn được dùng, add deprecation warnings:

```python
# In llm_factory.py

import warnings
from app.engine.llm_pool import get_llm_moderate, get_llm_deep, get_llm_light

def create_rag_llm(...):
    """DEPRECATED: Use get_llm_moderate() from llm_pool instead."""
    warnings.warn(
        "create_rag_llm() is deprecated. Use get_llm_moderate() from "
        "app.engine.llm_pool for better memory efficiency.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_llm_moderate()  # Redirect to pool

def create_tutor_llm(...):
    """DEPRECATED: Use get_llm_deep() from llm_pool instead."""
    warnings.warn(
        "create_tutor_llm() is deprecated. Use get_llm_deep() from "
        "app.engine.llm_pool for better memory efficiency.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_llm_deep()

def create_analyzer_llm(...):
    """DEPRECATED: Use get_llm_light() from llm_pool instead."""
    warnings.warn(
        "create_analyzer_llm() is deprecated. Use get_llm_light() from "
        "app.engine.llm_pool for better memory efficiency.",
        DeprecationWarning,
        stacklevel=2
    )
    return get_llm_light()
```

---

## PHASE 4: Clean Semantic Memory Wrapper

**Files:**
- `app/engine/semantic_memory.py` (wrapper - 24 lines, just re-exports)
- `app/engine/semantic_memory/` (actual implementation)

**Step 1:** Read wrapper

```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/engine/semantic_memory.py
```

**Step 2:** Nếu chỉ là re-exports, có 2 options:

**Option A (Safe):** Add deprecation notice
```python
"""
DEPRECATED: Import directly from app.engine.semantic_memory.core instead.

Example:
    # Old (deprecated):
    from app.engine.semantic_memory import SemanticMemoryEngine

    # New (preferred):
    from app.engine.semantic_memory.core import SemanticMemoryEngine
"""
import warnings
warnings.warn(
    "Importing from app.engine.semantic_memory is deprecated. "
    "Import from app.engine.semantic_memory.core instead.",
    DeprecationWarning,
    stacklevel=2
)

# Keep existing re-exports for backward compatibility
from app.engine.semantic_memory.core import ...
```

**Option B (If no usages):** Delete the wrapper file

---

## PHASE 5: Create ADR Documentation

**File:** `.claude/knowledge/decisions.md`

```markdown
# Architecture Decision Records

## ADR-001: Deprecate unified_agent.py

**Date:** 2025-02-05
**Status:** [ACCEPTED/REJECTED]
**Author:** ARCHITECT

### Context
unified_agent.py (649 lines) was deprecated on 2025-12-20.
Multi-agent system has replaced it.

### Decision
[DELETE / KEEP WITH WARNING]

### Consequences
- [List impacts]

---

## ADR-002: Consolidate LLM APIs

**Date:** 2025-02-05
**Status:** ACCEPTED

### Context
Two overlapping APIs exist:
- llm_factory.py: Creates new instances each call
- llm_pool.py: Singleton pool (5x memory savings)

### Decision
Deprecate llm_factory functions, redirect to llm_pool.

### Migration Path
| Old | New |
|-----|-----|
| create_tutor_llm() | get_llm_deep() |
| create_rag_llm() | get_llm_moderate() |
| create_analyzer_llm() | get_llm_light() |
```

---

## Constraints

- KHÔNG delete nếu còn production usage
- Add deprecation warnings TRƯỚC khi delete
- Document decisions trong ADR
- Test sau mỗi change

---

## Completion Report

```
ARCHITECT TASK-006 Completion Report

Investigation Results:
- unified_agent.py usages: [list files]
- llm_factory.py usages: [list files]
- semantic_memory.py usages: [list files]

Actions Taken:
- [ ] unified_agent.py: [DELETED / DEPRECATED / KEPT]
- [ ] llm_factory.py: [DEPRECATED functions]
- [ ] semantic_memory.py: [DELETED / DEPRECATED / KEPT]

Files Modified:
- [list]

Files Deleted:
- [list]

ADR Created:
- .claude/knowledge/decisions.md
```

---

## START NOW

Bắt đầu với investigation:
```bash
grep -rn "unified_agent\|get_unified_agent" app/ --include="*.py"
```
