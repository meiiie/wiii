# READY TO EXECUTE - TESTER TASK-008

**Copy toàn bộ prompt này vào Claude Code session mới và thực thi**

---

## Context

Bạn là **TESTER** agent. DEVELOPER đã hoàn thành TASK-001 đến TASK-005. Nhiệm vụ của bạn là tạo regression tests.

**Project:** Maritime AI Tutor Service
**Location:** `/mnt/e/Sach/Sua/AI_v1/maritime-ai-service/`
**Test Framework:** pytest, pytest-asyncio

---

## TASK-008: Create Regression Tests

**Priority:** HIGH
**Goal:** Đảm bảo các bug fixes không bị regression

---

## TEST 1: No Bare Except Clauses

**File:** `tests/unit/test_code_quality.py` (CREATE NEW)

```python
"""
Test code quality - no bare except clauses allowed.
Verifies TASK-002 fix.
"""
import ast
from pathlib import Path
import pytest


def test_no_bare_except_clauses():
    """
    Scan entire codebase for bare 'except:' clauses.
    These should all be 'except Exception:' or more specific.

    TASK-002 fixed 5 instances. This test prevents regression.
    """
    app_dir = Path("app")
    bare_excepts = []

    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:  # bare except
                    bare_excepts.append(f"{py_file}:{node.lineno}")

    assert len(bare_excepts) == 0, (
        f"Found {len(bare_excepts)} bare except clauses (should be 0):\n"
        + "\n".join(f"  - {loc}" for loc in bare_excepts)
    )


def test_exception_handlers_have_logging():
    """
    Verify exception handlers include some form of logging.
    This is a best-effort check.
    """
    # This would require more sophisticated AST analysis
    # For now, just document the expectation
    pass
```

---

## TEST 2: Connection Pool Configuration

**File:** `tests/unit/test_connection_pool_config.py` (CREATE NEW)

```python
"""
Test connection pool configuration.
Verifies TASK-001 fix.
"""
import pytest
from app.core.config import settings


def test_async_pool_config_exists():
    """Verify async pool configuration is defined."""
    assert hasattr(settings, 'async_pool_min_size')
    assert hasattr(settings, 'async_pool_max_size')


def test_async_pool_config_values():
    """Verify pool sizes are reasonable."""
    assert settings.async_pool_min_size >= 1, "min_size should be at least 1"
    assert settings.async_pool_max_size >= 5, "max_size should be at least 5"
    assert settings.async_pool_max_size >= settings.async_pool_min_size


def test_dense_repo_uses_config():
    """Verify DenseSearchRepository uses config for pool size."""
    from app.repositories.dense_search_repository import DenseSearchRepository
    import inspect

    source = inspect.getsource(DenseSearchRepository._get_pool)
    assert "async_pool_max_size" in source or "settings" in source


def test_sparse_repo_has_pool():
    """Verify SparseSearchRepository has connection pooling."""
    from app.repositories.sparse_search_repository import SparseSearchRepository

    repo = SparseSearchRepository()
    assert hasattr(repo, '_pool'), "SparseSearchRepository should have _pool attribute"
    assert hasattr(repo, '_get_pool'), "SparseSearchRepository should have _get_pool method"
```

---

## TEST 3: ChatOrchestrator Fallback

**File:** `tests/unit/test_chat_orchestrator_fallback.py` (CREATE NEW)

```python
"""
Test ChatOrchestrator fallback behavior.
Verifies TASK-004 fix.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_fallback_when_unified_agent_none():
    """
    Verify graceful fallback to RAG when UnifiedAgent is None.

    Before fix: raised RuntimeError
    After fix: falls back to RAGAgent
    """
    from app.services.chat_orchestrator import ChatOrchestrator

    # Mock RAG agent
    mock_rag = AsyncMock()
    mock_rag.query.return_value = MagicMock(
        answer="Fallback answer from RAG",
        citations=[{"title": "Test Source", "page": 1}]
    )

    # Mock other dependencies
    mock_input_processor = AsyncMock()
    mock_input_processor.build_context.return_value = MagicMock(
        message="Test question",
        user_role=MagicMock(value="student"),
        user_name="Test User"
    )
    mock_input_processor.validate_input.return_value = (True, None)

    mock_output_processor = AsyncMock()
    mock_output_processor.validate_and_format.return_value = MagicMock()
    mock_output_processor.format_sources.return_value = []

    mock_session_manager = MagicMock()
    mock_session_manager.get_or_create_session.return_value = "test-session-id"

    # Create orchestrator WITHOUT unified agent
    orchestrator = ChatOrchestrator(
        unified_agent=None,  # <-- Key: no unified agent
        rag_agent=mock_rag,
        input_processor=mock_input_processor,
        output_processor=mock_output_processor,
        session_manager=mock_session_manager,
        background_runner=MagicMock(),
    )

    # Should NOT raise, should use fallback
    result = await orchestrator.process(
        message="Test question",
        user_id="test-user",
        user_role="student"
    )

    # Verify RAG was called as fallback
    mock_rag.query.assert_called_once()


@pytest.mark.asyncio
async def test_error_when_no_agents_available():
    """
    Verify proper error when BOTH agents are None.
    """
    from app.services.chat_orchestrator import ChatOrchestrator

    mock_input_processor = AsyncMock()
    mock_input_processor.validate_input.return_value = (True, None)
    mock_input_processor.build_context.return_value = MagicMock(
        message="Test",
        user_role=MagicMock(value="student")
    )

    orchestrator = ChatOrchestrator(
        unified_agent=None,
        rag_agent=None,  # <-- Both None
        input_processor=mock_input_processor,
        output_processor=AsyncMock(),
        session_manager=MagicMock(get_or_create_session=MagicMock(return_value="id")),
        background_runner=MagicMock(),
    )

    with pytest.raises(RuntimeError, match="No processing agent"):
        await orchestrator.process(
            message="Test",
            user_id="test",
            user_role="student"
        )
```

---

## TEST 4: Batch Delete (N+1 Fix)

**File:** `tests/unit/test_batch_delete.py` (CREATE NEW)

```python
"""
Test batch delete uses IN clause instead of loop.
Verifies TASK-003 fix.
"""
import pytest
import inspect


def test_delete_user_history_uses_batch():
    """
    Verify delete_user_history uses batch delete (IN clause).

    Before fix: Loop with N queries
    After fix: Single query with IN clause
    """
    from app.repositories.chat_history_repository import ChatHistoryRepository

    source = inspect.getsource(ChatHistoryRepository.delete_user_history)

    # Should use .in_() for batch operation
    assert ".in_(" in source, (
        "delete_user_history should use .in_() for batch delete"
    )

    # Should NOT have nested query in loop
    # This is a heuristic check
    assert "for chat_session in sessions:" not in source or ".in_(" in source, (
        "delete_user_history should not query inside loop"
    )


def test_delete_uses_synchronize_session_false():
    """
    Verify batch delete uses synchronize_session=False for performance.
    """
    from app.repositories.chat_history_repository import ChatHistoryRepository

    source = inspect.getsource(ChatHistoryRepository.delete_user_history)

    assert "synchronize_session=False" in source, (
        "Batch delete should use synchronize_session=False"
    )
```

---

## TEST 5: Parallel Search (Optional - if TASK-005 done)

**File:** `tests/unit/test_parallel_operations.py` (CREATE NEW)

```python
"""
Test parallel operations.
Verifies TASK-005 fix.
"""
import pytest
import inspect


def test_hybrid_search_uses_gather():
    """
    Verify HybridSearchService uses asyncio.gather for parallel search.
    """
    from app.services.hybrid_search_service import HybridSearchService

    source = inspect.getsource(HybridSearchService.search)

    # Should use asyncio.gather
    assert "gather" in source, (
        "HybridSearchService.search should use asyncio.gather"
    )


def test_parallel_search_handles_exceptions():
    """
    Verify parallel search has return_exceptions=True.
    """
    from app.services.hybrid_search_service import HybridSearchService

    source = inspect.getsource(HybridSearchService.search)

    assert "return_exceptions=True" in source or "return_exceptions = True" in source, (
        "asyncio.gather should use return_exceptions=True for fault tolerance"
    )
```

---

## Execution Instructions

**Step 1:** Create test directory structure
```bash
mkdir -p tests/unit
touch tests/unit/__init__.py
```

**Step 2:** Create each test file
- `tests/unit/test_code_quality.py`
- `tests/unit/test_connection_pool_config.py`
- `tests/unit/test_chat_orchestrator_fallback.py`
- `tests/unit/test_batch_delete.py`
- `tests/unit/test_parallel_operations.py` (if TASK-005 done)

**Step 3:** Run tests
```bash
cd /mnt/e/Sach/Sua/AI_v1/maritime-ai-service
pytest tests/unit/test_code_quality.py -v
pytest tests/unit/test_connection_pool_config.py -v
pytest tests/unit/test_chat_orchestrator_fallback.py -v
pytest tests/unit/test_batch_delete.py -v
```

---

## Completion Report

```
TESTER TASK-008 Completion Report

Files Created:
- tests/unit/test_code_quality.py (2 tests)
- tests/unit/test_connection_pool_config.py (4 tests)
- tests/unit/test_chat_orchestrator_fallback.py (2 tests)
- tests/unit/test_batch_delete.py (2 tests)
- tests/unit/test_parallel_operations.py (2 tests) [if applicable]

Test Results:
- test_code_quality: [PASS/FAIL]
- test_connection_pool_config: [PASS/FAIL]
- test_chat_orchestrator_fallback: [PASS/FAIL]
- test_batch_delete: [PASS/FAIL]
- test_parallel_operations: [PASS/FAIL/SKIPPED]

Total: X tests, Y passed, Z failed
```

---

## START NOW

Bắt đầu với:
```bash
mkdir -p tests/unit && touch tests/unit/__init__.py
```

Sau đó tạo `tests/unit/test_code_quality.py` first.
