# Architecture Decision Records (ADR)

This document tracks major architectural decisions for the Wiii platform project.

---

## ADR-001: Deprecate unified_agent.py

**Date:** 2025-02-05
**Status:** ACCEPTED (Partially - Keep with warning)
**Author:** ARCHITECT
**Task:** TASK-006

### Context

`unified_agent.py` (649 lines) was originally deprecated on 2025-12-20 with a module-level deprecation warning. The Multi-Agent system was intended to replace it.

**Investigation findings:**
- **Still heavily used in production:**
  - `chat_service.py`: Initializes UnifiedAgent instances
  - `chat_orchestrator.py`: Uses `_process_with_unified_agent()`
  - `chat_stream.py`: Imports helper functions (get_last_retrieved_sources, clear_retrieved_sources)
  - `config.py`: Feature flag `use_unified_agent=True`

### Decision

**KEEP with existing deprecation warning** (do not delete)

Rationale:
- Core production functionality still depends on it
- Removing it would break active user sessions
- Feature flag `use_unified_agent` shows it's part of a phased migration strategy

### Consequences

**Positive:**
- No production breakage
- Allows gradual migration to Multi-Agent system
- Existing deprecation warning guides new development

**Negative:**
- Technical debt remains in codebase
- Two orchestration systems maintained in parallel

### Migration Path

Users should:
1. Set `use_multi_agent=True` in `.env`
2. Test with Multi-Agent system
3. Once stable, set `use_unified_agent=False`

**Removal timeline:** After Multi-Agent reaches 100% adoption (TBD)

---

## ADR-002: Consolidate LLM APIs (Factory → Singleton Pool)

**Date:** 2025-02-05
**Status:** ACCEPTED
**Author:** ARCHITECT
**Task:** TASK-006

### Context

Two overlapping APIs existed for LLM instance creation:

1. **llm_factory.py** (Old pattern):
   - `create_tutor_llm()`, `create_rag_llm()`, `create_analyzer_llm()`, `create_extraction_llm()`
   - Creates new instances on every call
   - Memory usage: ~600MB (15+ LLM instances)

2. **llm_pool.py** (New pattern - SOTA):
   - `get_llm_deep()`, `get_llm_moderate()`, `get_llm_light()`
   - Singleton pool with 3 shared instances
   - Memory usage: ~120MB (5× reduction)

**Investigation findings:**
- **llm_factory still used in 5 files:**
  - `rag_agent.py`: create_rag_llm()
  - `grader_agent.py`: create_rag_llm()
  - `tutor_node.py`: create_tutor_llm()
  - `extraction.py`: create_extraction_llm()

### Decision

**Deprecate llm_factory convenience functions**, redirect to llm_pool.

Implementation:
- Added deprecation warnings to all 4 functions
- Functions now redirect to singleton pool equivalents
- Keep `create_llm()` base function (still useful for custom configurations)

### Migration Path

| Old (Deprecated) | New (Preferred) | Memory Tier |
|-----------------|-----------------|-------------|
| `create_tutor_llm()` | `get_llm_deep()` | DEEP (8192 tokens) |
| `create_rag_llm()` | `get_llm_moderate()` | MODERATE (4096 tokens) |
| `create_analyzer_llm()` | `get_llm_light()` | LIGHT (1024 tokens) |
| `create_extraction_llm()` | `get_llm_light()` | LIGHT (MINIMAL mapped) |

**Example migration:**

```python
# Old (deprecated):
from app.engine.llm_factory import create_rag_llm
llm = create_rag_llm()

# New (preferred):
from app.engine.llm_pool import get_llm_moderate
llm = get_llm_moderate()
```

### Consequences

**Positive:**
- **5× memory reduction** (~600MB → ~120MB)
- Faster startup (3 instances vs 15+ instances)
- Consistent LLM configuration across components
- SOTA pattern alignment (OpenAI, Anthropic, Google best practices)

**Negative:**
- Cannot customize temperature per component (all use defaults)
- Deprecation warnings will appear in logs until migration complete

**Mitigation:**
- Warnings provide clear migration instructions
- Functions still work (redirect to pool)
- No breaking changes for existing code

### Implementation Details

**Files modified:**
- `app/engine/llm_factory.py`: Added deprecation warnings to 4 functions

**Redirect mapping:**
```python
def create_tutor_llm(...) -> ChatGoogleGenerativeAI:
    warnings.warn("deprecated...", DeprecationWarning)
    from app.engine.llm_pool import get_llm_deep
    return get_llm_deep()
```

### Next Steps (DEVELOPER tasks)

1. Migrate remaining usages:
   - [ ] `app/engine/agentic_rag/rag_agent.py:205`
   - [ ] `app/engine/multi_agent/agents/grader_agent.py:77`
   - [ ] `app/engine/multi_agent/agents/tutor_node.py:87`
   - [ ] `app/engine/semantic_memory/extraction.py:74`

2. After migration complete:
   - Remove deprecated functions from llm_factory.py
   - Keep only `create_llm()` base function

---

## ADR-003: Deprecate semantic_memory.py Wrapper

**Date:** 2025-02-05
**Status:** ACCEPTED (Keep with warning)
**Author:** ARCHITECT
**Task:** TASK-006

### Context

`semantic_memory.py` (24 lines) is a backward compatibility wrapper that re-exports from `semantic_memory/` module structure.

Created during CHỈ THỊ KỸ THUẬT SỐ 25 - Project Restructure.

**Investigation findings:**
- **Still used in 3 files:**
  - `chat_stream.py:366`: `get_semantic_memory_engine`
  - `multi_agent/graph.py:119`: `get_semantic_memory_engine`
  - `chat_service.py:76`: `SemanticMemoryEngine`, `get_semantic_memory_engine`

### Decision

**KEEP wrapper with deprecation warning**

Rationale:
- Provides smooth transition for existing code
- Only 24 lines (low maintenance cost)
- Already properly structured with re-exports

Implementation:
- Added runtime deprecation warning
- Updated docstring with migration guide
- Keep re-exports intact

### Migration Path

```python
# Old (deprecated):
from app.engine.semantic_memory import SemanticMemoryEngine
from app.engine.semantic_memory import get_semantic_memory_engine

# New (preferred):
from app.engine.semantic_memory.core import SemanticMemoryEngine
from app.engine.semantic_memory.core import get_semantic_memory_engine
```

### Consequences

**Positive:**
- Clear migration path documented
- No breaking changes
- Encourages direct imports from core module

**Negative:**
- Extra indirection layer remains
- Deprecation warning on every import

**Mitigation:**
- Warning clearly explains migration
- Low impact (only 24 lines to maintain)

### Next Steps (DEVELOPER tasks)

1. Migrate remaining usages:
   - [ ] `app/api/v1/chat_stream.py:366`
   - [ ] `app/engine/multi_agent/graph.py:119`
   - [ ] `app/services/chat_service.py:76`

2. After migration complete:
   - Can optionally remove wrapper
   - Or keep as convenience (decision TBD)

---

## ADR-004: Multi-Organization (Multi-Tenant) Architecture

**Date:** 2026-02-09
**Status:** ACCEPTED & IMPLEMENTED
**Author:** LEADER
**Sprint:** 24

### Context

Wiii platform serves multiple organizations from a single deployment:
- **LMS Hang Hai**: Maritime education (COLREGs, SOLAS)
- **Phuong Luu Kiem**: Public administration AI
- **Minh Hong**: Price comparison for Chinese buyers in Vietnam

Each org needs different domain plugins, data isolation, and user membership management.

### Decision

**Shared Database + Shared Schema + `organization_id` column**, feature-gated via `enable_multi_tenant=False`.

This follows the industry-standard pattern used by OpenAI, Anthropic, Azure for MVP multi-tenant:
- Application-level org filtering (no PostgreSQL RLS in MVP)
- `organizations` + `user_organizations` tables
- ContextVar per-request isolation (`org_context.py`)
- Org-prefixed thread IDs for data isolation
- Domain filtering via `allowed_domains` per org

### Alternatives Considered

1. **Separate databases per org** — Too complex for MVP, operational overhead
2. **PostgreSQL RLS** — Can be added later for defense-in-depth (Phase 2)
3. **Separate deployments** — Defeats purpose of shared infrastructure

### Consequences

**Positive:**
- Zero behavioral change for existing single-tenant deployments (`enable_multi_tenant=False`)
- Nullable `organization_id` columns — no data migration needed
- "default" org absorbs all pre-existing users/data
- Domain filtering, not domain creation — orgs select from global plugins
- Backward-compatible thread IDs (old format still valid)

**Negative:**
- No RLS in MVP — application-level filtering only
- No billing/quotas — organization is purely for data isolation
- No org-scoped API keys yet — relies on header-based org context

### Implementation

| Component | File |
|-----------|------|
| DB Migration | `alembic/versions/008_add_organizations.py` |
| Models | `app/models/organization.py` |
| Repository | `app/repositories/organization_repository.py` |
| ContextVar | `app/core/org_context.py` |
| Middleware | `app/core/middleware.py` (OrgContextMiddleware) |
| Config | `app/core/config.py` (+2 fields) |
| Domain Router | `app/domains/router.py` (+allowed_domains) |
| Thread Utils | `app/core/thread_utils.py` (+org_id) |
| Pipeline | `app/services/chat_orchestrator.py` (+org threading) |
| Admin API | `app/api/v1/organizations.py` |
| Tests | 7 new test files, 112 new tests |

**Result: 1325 passed, 0 failed**

---

## Summary

| ADR | Component | Status | Action Taken |
|-----|-----------|--------|--------------|
| ADR-001 | unified_agent.py | Keep with warning | Already has deprecation notice |
| ADR-002 | llm_factory.py | Deprecate functions | Added warnings + redirects |
| ADR-003 | semantic_memory.py | Keep wrapper | Added runtime warning |
| ADR-004 | Multi-Tenant | **Implemented** | Shared DB + ContextVar + feature gate |

**Total files modified:** 2 (llm_factory.py, semantic_memory.py) + 10 (Sprint 24)
**Total files deleted:** 0
**New files created:** 5 source + 7 test (Sprint 24)

---

## References

- TASK-006: Clean Deprecated Code & Consolidate APIs
- MEMORY_OVERFLOW_SOTA_ANALYSIS.md: LLM Pool pattern justification
- RAG_LATENCY_PHASE4_SOTA_ANALYSIS.md: Performance benchmarks
- CHỈ THỊ KỸ THUẬT SỐ 25: Project Restructure
- CHỈ THỊ KỸ THUẬT SỐ 28: SOTA 2025 Gemini Thinking Configuration
- Sprint 24 Plan: Multi-Organization Architecture (`.claude/plans/`)
