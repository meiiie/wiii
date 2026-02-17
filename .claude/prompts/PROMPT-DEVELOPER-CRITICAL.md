# DEVELOPER Agent Prompt - Critical Fixes

**Copy toàn bộ nội dung này vào Claude Code session mới**

---

## Your Role

You are **DEVELOPER** working on the Maritime AI Service project. Your LEADER has assigned you critical bug fixes that must be completed immediately.

**Read your full persona:** `.claude/agents/developer.md`

---

## Project Context

- **Project:** Maritime AI Tutor Service (FastAPI + LangGraph + Gemini)
- **Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`
- **Documentation:** Read `CLAUDE.md` in parent directory for architecture overview

---

## Your Assigned Tasks (Priority Order)

### TASK-001: Fix AsyncPG Connection Pool [CRITICAL]
**File:** `app/repositories/dense_search_repository.py`

**Problem:** Line 114 has `max_size=1` - only ONE async connection allowed, causing production bottlenecks.

**Your Fix:**
1. Read the file first: `app/repositories/dense_search_repository.py`
2. Find line ~114 in `_get_pool()` method
3. Change `max_size=1` to `max_size=10`
4. Add config from settings (create if needed in `app/core/config.py`):
   ```python
   async_pool_min_size: int = Field(default=2)
   async_pool_max_size: int = Field(default=10)
   ```
5. Update pool creation to use settings

**Also fix:** `app/repositories/sparse_search_repository.py:272`
- Currently creates NEW connection per request: `await asyncpg.connect()`
- Add `_get_pool()` method similar to dense repo
- Use `pool.acquire()` instead of `connect()`

---

### TASK-002: Fix Bare Except Clauses [CRITICAL]
**Problem:** 5 instances of `except:` that swallow ALL exceptions including SystemExit

**Files to fix:**
1. `app/engine/multi_agent/graph.py:724`
2. `app/repositories/dense_search_repository.py:219`
3. `app/repositories/dense_search_repository.py:229`
4. `app/repositories/sparse_search_repository.py:306`
5. `app/services/multimodal_ingestion_service.py:473`

**Your Fix for each:**
```python
# Change FROM:
except:
    pass  # or whatever is there

# Change TO:
except Exception as e:
    logger.warning(f"Operation failed: {e}")
    # keep the original behavior (pass/continue/return)
```

---

### TASK-003: Fix N+1 Query in Delete [CRITICAL]
**File:** `app/repositories/chat_history_repository.py:456-470`

**Problem:** Loop with nested queries - user with 50 sessions triggers 100+ queries

**Current bad code:**
```python
for chat_session in sessions:
    msg_result = session.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == chat_session.session_id
    ).delete()
    session.delete(chat_session)
```

**Your Fix:**
```python
# Get all session IDs first
session_ids = [s.session_id for s in sessions]

if session_ids:
    # Batch delete messages (ONE query)
    session.query(ChatMessageModel).filter(
        ChatMessageModel.session_id.in_(session_ids)
    ).delete(synchronize_session=False)

    # Batch delete sessions (ONE query)
    session.query(ChatSessionModel).filter(
        ChatSessionModel.session_id.in_(session_ids)
    ).delete(synchronize_session=False)

    session.commit()
```

---

### TASK-004: Add ChatOrchestrator Fallback [CRITICAL]
**File:** `app/services/chat_orchestrator.py:200-206`

**Problem:** Hard crash when UnifiedAgent unavailable

**Current bad code:**
```python
else:
    logger.error("[ERROR] UnifiedAgent not available")
    raise RuntimeError("UnifiedAgent not available")
```

**Your Fix:**
```python
else:
    # Fallback to direct RAG mode
    logger.warning("[FALLBACK] UnifiedAgent unavailable, using direct RAG")

    if self._rag_agent:
        rag_result = await self._rag_agent.query(
            question=message,
            user_role=user_role,
            limit=5
        )
        return InternalChatResponse(
            answer=rag_result.answer,
            sources=rag_result.citations,
            reasoning_trace=None,
            metadata={"mode": "fallback_rag"}
        )
    else:
        logger.error("[ERROR] No processing agent available")
        raise RuntimeError("No processing agent available")
```

---

## Execution Instructions

1. **Start by reading** the main CLAUDE.md:
   ```
   Read file: /mnt/e/Sach/Sua/AI_v1/CLAUDE.md
   ```

2. **For each task:**
   - Read the file first (ALWAYS read before edit)
   - Make the specific changes described
   - Verify the change is correct
   - Move to next task

3. **After all fixes:**
   - Run tests if possible: `pytest tests/ -v --tb=short`
   - Report completion

---

## Constraints

- DO NOT refactor or improve unrelated code
- DO NOT add new features
- DO NOT change function signatures
- ONLY fix the specific issues described
- ALWAYS read files before editing

---

## Completion Report Format

When done, report:
```markdown
## DEVELOPER Task Completion Report

**Date:** YYYY-MM-DD
**Tasks Completed:** TASK-001, TASK-002, TASK-003, TASK-004

### Changes Made
- `dense_search_repository.py`: Changed pool max_size to 10
- `sparse_search_repository.py`: Added connection pooling
- [list all changes]

### Tests
- [ ] Ran pytest (pass/fail)
- [ ] Manual verification done

### Notes
[Any concerns or observations]
```

---

## Start Now

Begin with:
```
Read file: /mnt/e/Sach/Sua/AI_v1/CLAUDE.md
```

Then read and fix TASK-001 first.
