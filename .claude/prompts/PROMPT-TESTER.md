# TESTER Agent Prompt - Regression Tests

**Copy toàn bộ nội dung này vào Claude Code session mới**

---

## Your Role

You are **TESTER** working on the Maritime AI Service project. Your LEADER has assigned you to create regression tests for the critical bug fixes.

**Read your full persona:** `.claude/agents/tester.md`

**Prerequisite:** Wait until DEVELOPER completes TASK-001 through TASK-005.

---

## Project Context

- **Project:** Maritime AI Tutor Service
- **Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`
- **Test Framework:** pytest, pytest-asyncio
- **Test Location:** `tests/`

---

## Your Assigned Task

### TASK-008: Create Regression Tests [HIGH]

---

## Test 1: Connection Pool Concurrency

**File to create:** `tests/integration/test_connection_pool.py`

```python
"""
Test connection pool handles concurrent requests.
Verifies fix for TASK-001 (AsyncPG pool size).
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
import numpy as np


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dense_search_concurrent_requests():
    """
    Verify dense search pool handles 10+ concurrent requests.

    Before fix: max_size=1 caused sequential execution
    After fix: max_size=10 allows parallel execution
    """
    from app.repositories.dense_search_repository import get_dense_search_repository

    repo = get_dense_search_repository()

    # Create 10 concurrent search tasks
    embedding = np.random.rand(768).tolist()
    tasks = [
        repo.search(embedding, limit=5)
        for _ in range(10)
    ]

    # All should complete without timeout
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Verify no exceptions
    exceptions = [r for r in results if isinstance(r, Exception)]
    assert len(exceptions) == 0, f"Got exceptions: {exceptions}"

    # Verify all returned results
    assert all(isinstance(r, list) for r in results)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sparse_search_uses_pool():
    """
    Verify sparse search uses connection pool, not per-request connection.
    """
    from app.repositories.sparse_search_repository import SparseSearchRepository

    repo = SparseSearchRepository()

    # Multiple searches should reuse connections
    for _ in range(5):
        results = await repo.search("test query", limit=5)
        assert isinstance(results, list)

    # Pool should exist after searches
    assert repo._pool is not None


@pytest.mark.asyncio
async def test_pool_recovers_after_error():
    """
    Verify connection pool recovers after a connection error.
    """
    from app.repositories.dense_search_repository import DenseSearchRepository

    repo = DenseSearchRepository()

    # First search should work
    embedding = np.random.rand(768).tolist()
    result1 = await repo.search(embedding, limit=5)

    # Simulate error by closing pool
    if repo._pool:
        await repo._pool.close()
        repo._pool = None

    # Next search should recreate pool and succeed
    result2 = await repo.search(embedding, limit=5)
    assert isinstance(result2, list)
```

---

## Test 2: Exception Handling

**File to create:** `tests/unit/test_exception_handling.py`

```python
"""
Test that no bare except clauses exist.
Verifies fix for TASK-002.
"""
import ast
import os
from pathlib import Path


def test_no_bare_except_clauses():
    """
    Scan codebase for bare 'except:' clauses.
    These should all be 'except Exception:' or more specific.
    """
    app_dir = Path("app")
    bare_excepts = []

    for py_file in app_dir.rglob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare_excepts.append(f"{py_file}:{node.lineno}")

    assert len(bare_excepts) == 0, (
        f"Found {len(bare_excepts)} bare except clauses:\n"
        + "\n".join(bare_excepts)
    )


def test_exceptions_are_logged():
    """
    Verify exception handlers include logging.
    """
    # This is a code review check - manual verification needed
    pass
```

---

## Test 3: Batch Delete Performance

**File to create:** `tests/integration/test_chat_history_performance.py`

```python
"""
Test batch delete performance.
Verifies fix for TASK-003 (N+1 query).
"""
import pytest
import time
import uuid
from datetime import datetime


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_user_with_many_sessions_performance(test_db_session):
    """
    Verify batch delete handles 50 sessions efficiently.

    Before fix: 100+ queries, 30+ seconds
    After fix: 2-3 queries, <5 seconds
    """
    from app.repositories.chat_history_repository import ChatHistoryRepository
    from app.models.database import ChatSessionModel, ChatMessageModel

    repo = ChatHistoryRepository()
    user_id = f"test-user-{uuid.uuid4()}"

    # Create 50 sessions with 10 messages each
    with test_db_session() as session:
        for i in range(50):
            chat_session = ChatSessionModel(
                session_id=uuid.uuid4(),
                user_id=user_id,
                created_at=datetime.utcnow()
            )
            session.add(chat_session)

            for j in range(10):
                message = ChatMessageModel(
                    session_id=chat_session.session_id,
                    role="user" if j % 2 == 0 else "assistant",
                    content=f"Message {j}",
                    created_at=datetime.utcnow()
                )
                session.add(message)

        session.commit()

    # Time the delete operation
    start = time.time()
    deleted_count = repo.delete_user_history(user_id)
    duration = time.time() - start

    # Should complete in <5 seconds (was 30+ with N+1)
    assert duration < 5.0, f"Delete took {duration:.2f}s, expected <5s"
    assert deleted_count > 0


@pytest.mark.integration
def test_delete_empty_user_history():
    """
    Verify delete handles user with no sessions gracefully.
    """
    from app.repositories.chat_history_repository import ChatHistoryRepository

    repo = ChatHistoryRepository()
    user_id = f"nonexistent-{uuid.uuid4()}"

    # Should not raise, return 0
    deleted_count = repo.delete_user_history(user_id)
    assert deleted_count == 0
```

---

## Test 4: ChatOrchestrator Fallback

**File to create:** `tests/unit/test_chat_orchestrator_fallback.py`

```python
"""
Test ChatOrchestrator fallback behavior.
Verifies fix for TASK-004.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.mark.asyncio
async def test_orchestrator_fallback_when_unified_agent_unavailable():
    """
    Verify graceful fallback to RAG mode when UnifiedAgent is None.
    """
    from app.services.chat_orchestrator import ChatOrchestrator
    from app.models.schemas import InternalChatResponse

    # Mock RAG agent
    mock_rag = AsyncMock()
    mock_rag.query.return_value = MagicMock(
        answer="Fallback answer",
        citations=[{"title": "Test", "page": 1}]
    )

    # Create orchestrator with no unified agent
    orchestrator = ChatOrchestrator(
        unified_agent=None,
        rag_agent=mock_rag,
        # ... other dependencies
    )

    # Process should use fallback
    result = await orchestrator.process(
        message="Test question",
        user_id="test-user",
        user_role="student"
    )

    # Verify fallback mode
    assert result is not None
    assert result.answer == "Fallback answer"
    assert result.metadata.get("mode") == "fallback_rag"
    mock_rag.query.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_raises_when_no_agents():
    """
    Verify proper error when both agents unavailable.
    """
    from app.services.chat_orchestrator import ChatOrchestrator

    orchestrator = ChatOrchestrator(
        unified_agent=None,
        rag_agent=None,
    )

    with pytest.raises(RuntimeError, match="No processing agent"):
        await orchestrator.process(
            message="Test",
            user_id="test",
            user_role="student"
        )
```

---

## Test 5: Parallel Search

**File to create:** `tests/unit/test_parallel_search.py`

```python
"""
Test parallel search execution.
Verifies fix for TASK-005.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_hybrid_search_runs_in_parallel():
    """
    Verify dense and sparse search run in parallel, not sequentially.
    """
    from app.services.hybrid_search_service import HybridSearchService

    # Create mocks with artificial delay
    async def slow_dense_search(*args, **kwargs):
        await asyncio.sleep(0.2)
        return [{"id": "1", "score": 0.9}]

    async def slow_sparse_search(*args, **kwargs):
        await asyncio.sleep(0.2)
        return [{"id": "2", "score": 0.8}]

    mock_dense = AsyncMock(side_effect=slow_dense_search)
    mock_sparse = AsyncMock(side_effect=slow_sparse_search)

    service = HybridSearchService(
        dense_repo=MagicMock(search=mock_dense),
        sparse_repo=MagicMock(search=mock_sparse),
    )

    # Time the search
    start = time.time()
    results = await service.search("test query", limit=5)
    duration = time.time() - start

    # Sequential would take 0.4s, parallel should be ~0.2s
    assert duration < 0.35, f"Search took {duration:.2f}s, expected <0.35s (parallel)"

    # Both should have been called
    mock_dense.assert_called_once()
    mock_sparse.assert_called_once()


@pytest.mark.asyncio
async def test_hybrid_search_handles_partial_failure():
    """
    Verify search continues if one method fails.
    """
    from app.services.hybrid_search_service import HybridSearchService

    mock_dense = AsyncMock(return_value=[{"id": "1", "score": 0.9}])
    mock_sparse = AsyncMock(side_effect=Exception("Sparse search failed"))

    service = HybridSearchService(
        dense_repo=MagicMock(search=mock_dense),
        sparse_repo=MagicMock(search=mock_sparse),
    )

    # Should not raise, return partial results
    results = await service.search("test query", limit=5)

    assert len(results) >= 1  # At least dense results
```

---

## Execution Instructions

1. **Read existing test structure:**
   ```
   ls tests/
   cat tests/conftest.py
   ```

2. **Create test files** in appropriate directories

3. **Run tests:**
   ```bash
   # Run new tests
   pytest tests/unit/test_exception_handling.py -v
   pytest tests/unit/test_chat_orchestrator_fallback.py -v
   pytest tests/unit/test_parallel_search.py -v

   # Run integration tests (requires services)
   pytest tests/integration/test_connection_pool.py -v -m integration
   pytest tests/integration/test_chat_history_performance.py -v -m integration
   ```

4. **Verify all pass**

---

## Constraints

- Tests should be deterministic (no flaky tests)
- Use mocks for unit tests
- Mark integration tests with `@pytest.mark.integration`
- Include docstrings explaining what each test verifies

---

## Completion Report

```markdown
## TESTER Task Completion - TASK-008

### Tests Created
- `tests/unit/test_exception_handling.py` (2 tests)
- `tests/unit/test_chat_orchestrator_fallback.py` (2 tests)
- `tests/unit/test_parallel_search.py` (2 tests)
- `tests/integration/test_connection_pool.py` (3 tests)
- `tests/integration/test_chat_history_performance.py` (2 tests)

### Test Results
- Unit tests: [PASS/FAIL]
- Integration tests: [PASS/FAIL/SKIPPED]

### Coverage Impact
[If coverage data available]
```
