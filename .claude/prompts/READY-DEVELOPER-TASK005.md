# READY TO EXECUTE - DEVELOPER TASK-005

**Copy toàn bộ prompt này vào Claude Code session mới và thực thi**

---

## Context

Bạn là **DEVELOPER** agent. LEADER đã verify xong TASK-001 đến TASK-004. Bây giờ bạn thực hiện TASK-005.

**Project:** Maritime AI Tutor Service
**Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`

---

## TASK-005: Parallelize Sequential Operations

**Priority:** HIGH
**Goal:** Tăng performance bằng cách chạy parallel các async operations

---

## FIX 1: HybridSearchService

**File:** `app/services/hybrid_search_service.py`

**Step 1:** Đọc file trước
```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/services/hybrid_search_service.py
```

**Step 2:** Tìm method `search()` (khoảng line 150-200)

**Step 3:** Tìm đoạn code sequential như này:
```python
dense_results = await self._dense_repo.search(...)
sparse_results = await self._sparse_repo.search(...)
```

**Step 4:** Thay bằng parallel execution:
```python
import asyncio

# Create tasks for parallel execution
dense_task = self._dense_repo.search(query_embedding, limit=limit*2)
sparse_task = self._sparse_repo.search(query_text, limit=limit*2)

# Run in parallel
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

**Step 5:** Đảm bảo `import asyncio` ở đầu file (nếu chưa có)

---

## FIX 2: InputProcessor

**File:** `app/services/input_processor.py`

**Step 1:** Đọc file
```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/services/input_processor.py
```

**Step 2:** Tìm method `build_context()` hoặc tương tự (khoảng line 230-260)

**Step 3:** Tìm đoạn code sequential retrieval:
```python
insights = await self._semantic_memory.retrieve_insights_prioritized(...)
# ... some code ...
mem_context = await self._semantic_memory.retrieve_context(...)
```

**Step 4:** Thay bằng parallel execution:
```python
import asyncio

# Create parallel tasks
insights_task = self._semantic_memory.retrieve_insights_prioritized(
    user_id=user_id,
    limit=5
)
context_task = self._semantic_memory.retrieve_context(
    user_id=user_id,
    query=message
)

# Execute in parallel
results = await asyncio.gather(
    insights_task,
    context_task,
    return_exceptions=True
)

insights, mem_context = results

# Handle exceptions gracefully
if isinstance(insights, Exception):
    logger.warning(f"Insights retrieval failed: {insights}")
    insights = []
if isinstance(mem_context, Exception):
    logger.warning(f"Context retrieval failed: {mem_context}")
    mem_context = None
```

---

## Constraints

- CHỈ thay đổi execution pattern (sequential → parallel)
- KHÔNG thay đổi logic search/retrieval
- PHẢI dùng `return_exceptions=True` để handle partial failures
- PHẢI add logging cho failures
- Đảm bảo `import asyncio` có ở đầu file

---

## Execution Checklist

1. [ ] Read `hybrid_search_service.py`
2. [ ] Find sequential dense/sparse search
3. [ ] Replace with asyncio.gather()
4. [ ] Add exception handling
5. [ ] Read `input_processor.py`
6. [ ] Find sequential insights/context retrieval
7. [ ] Replace with asyncio.gather()
8. [ ] Add exception handling
9. [ ] Verify imports

---

## Completion Report

Khi hoàn thành, báo cáo theo format:

```
DEVELOPER TASK-005 Completion Report

Files Modified:
- hybrid_search_service.py: Parallelized dense+sparse search
- input_processor.py: Parallelized insights+context retrieval

Changes:
- Added asyncio.gather() for parallel execution
- Added return_exceptions=True for fault tolerance
- Added logging for partial failures

Expected Performance Improvement:
- HybridSearch: ~100-150ms faster (was sequential)
- InputProcessor: ~100-200ms faster (was sequential)
```

---

## START NOW

Bắt đầu bằng:
```
Read file: /mnt/e/Sach/Sua/AI_v1/maritime-ai-service/app/services/hybrid_search_service.py
```
