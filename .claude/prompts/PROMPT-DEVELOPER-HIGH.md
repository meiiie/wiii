# DEVELOPER Agent Prompt - High Priority Optimizations

**Copy toàn bộ nội dung này vào Claude Code session mới**

---

## Your Role

You are **DEVELOPER** working on the Maritime AI Service project. Your LEADER has assigned you performance optimizations.

**Prerequisite:** TASK-001 through TASK-004 must be completed first.

---

## Project Context

- **Project:** Maritime AI Tutor Service
- **Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`
- **Read:** `CLAUDE.md` for architecture overview

---

## Your Assigned Task

### TASK-005: Parallelize Sequential Operations [HIGH]

**Problem:** Several async operations run sequentially when they could run in parallel, adding 100-300ms latency per request.

---

### Fix 1: HybridSearchService
**File:** `app/services/hybrid_search_service.py`
**Location:** Around lines 160-182

**Current (sequential):**
```python
dense_results = await self._dense_repo.search(query_embedding, limit=limit*2)
sparse_results = await self._sparse_repo.search(query_text, limit=limit*2)
```

**Your Fix (parallel):**
```python
import asyncio

# Create tasks
dense_task = self._dense_repo.search(query_embedding, limit=limit*2)
sparse_task = self._sparse_repo.search(query_text, limit=limit*2)

# Run in parallel with error handling
results = await asyncio.gather(
    dense_task,
    sparse_task,
    return_exceptions=True
)

dense_results, sparse_results = results

# Handle failures gracefully
if isinstance(dense_results, Exception):
    logger.warning(f"Dense search failed: {dense_results}")
    dense_results = []
if isinstance(sparse_results, Exception):
    logger.warning(f"Sparse search failed: {sparse_results}")
    sparse_results = []
```

---

### Fix 2: InputProcessor
**File:** `app/services/input_processor.py`
**Location:** Around lines 234-255

**Current (sequential):**
```python
insights = await self._semantic_memory.retrieve_insights_prioritized(user_id, limit=5)
# ... some processing ...
mem_context = await self._semantic_memory.retrieve_context(user_id, query=message)
```

**Your Fix (parallel):**
```python
import asyncio

# Create tasks for parallel execution
insights_task = self._semantic_memory.retrieve_insights_prioritized(user_id, limit=5)
context_task = self._semantic_memory.retrieve_context(user_id, query=message)

# Run both in parallel
results = await asyncio.gather(
    insights_task,
    context_task,
    return_exceptions=True
)

insights, mem_context = results

# Handle failures gracefully
if isinstance(insights, Exception):
    logger.warning(f"Insights retrieval failed: {insights}")
    insights = []
if isinstance(mem_context, Exception):
    logger.warning(f"Context retrieval failed: {mem_context}")
    mem_context = None
```

---

### Fix 3: Add Timing Logs (Optional but Recommended)
Add timing to verify improvement:

```python
import time

start = time.time()
# ... parallel operations ...
duration = time.time() - start
logger.info(f"Parallel search completed in {duration:.2f}s")
```

---

## Execution Instructions

1. Read `CLAUDE.md` first
2. Read each file before editing
3. Make changes carefully
4. Ensure `asyncio` is imported at top of file
5. Test if possible

---

## Constraints

- DO NOT change the search/retrieval logic
- ONLY change the execution pattern (sequential → parallel)
- Preserve all error handling
- Add `return_exceptions=True` to handle individual failures

---

## Completion Report

```markdown
## DEVELOPER Task Completion - TASK-005

### Changes Made
- `hybrid_search_service.py`: Parallelized dense+sparse search
- `input_processor.py`: Parallelized insights+context retrieval

### Expected Improvement
- HybridSearch: ~50-150ms faster
- InputProcessor: ~100-200ms faster

### Tests
- [ ] Tests pass
```
