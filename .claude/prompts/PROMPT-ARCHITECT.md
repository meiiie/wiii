# ARCHITECT Agent Prompt - Code Cleanup & Consolidation

**Copy toàn bộ nội dung này vào Claude Code session mới**

---

## Your Role

You are **ARCHITECT** working on the Maritime AI Service project. Your LEADER has assigned you to clean up technical debt and consolidate overlapping code.

**Read your full persona:** `.claude/agents/architect.md`

---

## Project Context

- **Project:** Maritime AI Tutor Service
- **Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`
- **Architecture:** Clean Architecture with LangGraph multi-agent system

---

## Your Assigned Task

### TASK-006: Clean Deprecated Code & Consolidate APIs [HIGH]

---

## Phase 1: Investigate Usage

First, search for usages of deprecated code:

```bash
# Search for unified_agent usage
grep -rn "unified_agent\|get_unified_agent" app/ --include="*.py"

# Search for old LLM factory usage
grep -rn "create_tutor_llm\|create_rag_llm\|create_analyzer_llm" app/ --include="*.py"

# Search for semantic_memory wrapper usage
grep -rn "from app.engine.semantic_memory import" app/ --include="*.py"
```

Record all usages found.

---

## Phase 2: Analyze unified_agent.py

**File:** `app/engine/unified_agent.py` (649 lines)

**Status:** Marked DEPRECATED 2025-12-20

**Decision Tree:**
```
IF usages found in production code:
    → Add deprecation warning
    → Create migration guide
    → Keep for now
ELSE IF only used in tests:
    → Update tests to use multi-agent
    → Delete file
ELSE (no usages):
    → Delete file immediately
```

**If keeping, add deprecation warning:**
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
    # ... existing code
```

---

## Phase 3: Consolidate LLM APIs

**Current State:**
- `app/engine/llm_factory.py` - Creates NEW LLM instances
- `app/engine/llm_pool.py` - Singleton pool (PREFERRED)

**Problem:** Both are used, causing confusion and memory waste.

**Action:**
1. Read both files
2. Identify which factory functions are still called
3. For each used factory function, add deprecation warning:

```python
# In llm_factory.py
import warnings

def create_rag_llm(...):
    """DEPRECATED: Use get_llm_moderate() from llm_pool instead."""
    warnings.warn(
        "create_rag_llm() is deprecated. Use get_llm_moderate() from "
        "app.engine.llm_pool instead for better memory efficiency.",
        DeprecationWarning,
        stacklevel=2
    )
    # ... existing code OR redirect to pool
    from app.engine.llm_pool import get_llm_moderate
    return get_llm_moderate()
```

4. Update callers to use pool directly (if time permits)

---

## Phase 4: Clean Semantic Memory Wrapper

**Current State:**
- `app/engine/semantic_memory.py` (24 lines) - Just re-exports
- `app/engine/semantic_memory/` (submodule with actual code)

**Problem:** Two import paths cause confusion.

**Action:**
1. Find all imports from `app.engine.semantic_memory`
2. Update to import from `app.engine.semantic_memory.core` directly
3. Delete wrapper file

**Example migration:**
```python
# OLD
from app.engine.semantic_memory import SemanticMemoryEngine

# NEW
from app.engine.semantic_memory.core import SemanticMemoryEngine
```

---

## Execution Instructions

1. **Start with investigation** - Run grep commands, document findings
2. **Create backup plan** - List files that will be modified
3. **Make changes incrementally** - One file at a time
4. **Test after each change** - Run pytest if possible
5. **Document decisions** - Create ADR if significant

---

## Output: Architecture Decision Record

Create file: `.claude/knowledge/decisions.md`

```markdown
# ADR-001: Deprecate unified_agent.py

**Date:** 2025-02-05
**Status:** ACCEPTED
**Deciders:** LEADER, ARCHITECT

## Context
The unified_agent.py was the original ReAct implementation.
Multi-agent system (LangGraph) has replaced it since 2025-12-20.

## Decision
[Based on your investigation - keep with warning OR delete]

## Consequences
- Positive: Reduced code complexity, single code path
- Negative: [Any migration effort needed]

---

# ADR-002: Consolidate LLM APIs to Singleton Pool

**Date:** 2025-02-05
**Status:** ACCEPTED

## Context
Two overlapping APIs exist for LLM instantiation.

## Decision
Deprecate llm_factory.py functions in favor of llm_pool.py singletons.

## Migration Path
| Old API | New API |
|---------|---------|
| create_tutor_llm() | get_llm_deep() |
| create_rag_llm() | get_llm_moderate() |
| create_analyzer_llm() | get_llm_light() |
```

---

## Constraints

- DO NOT delete without verifying zero production usage
- DO NOT break existing functionality
- Add deprecation warnings before removal
- Document all decisions

---

## Completion Report

```markdown
## ARCHITECT Task Completion - TASK-006

### Investigation Results
- unified_agent.py usages: [list]
- llm_factory.py usages: [list]
- semantic_memory.py usages: [list]

### Actions Taken
- [ ] Added deprecation warnings
- [ ] Updated imports
- [ ] Deleted unused files
- [ ] Created ADR documentation

### Files Modified
[list all files]

### Files Deleted
[list deleted files]
```
