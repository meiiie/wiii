"""
Tests for Sprint 37: Async safety and resource management.

Covers:
- vision_extractor._rate_limit() is async (no time.sleep)
- supabase_storage retry uses asyncio.sleep (no time.sleep)
- web_search_tools circuit breaker is thread-safe
- admin.py _ingestion_jobs has bounded cleanup
"""

import ast
import threading
import time

import pytest

from app.api.v1.admin import _ingestion_jobs, _cleanup_old_jobs, _MAX_TRACKED_JOBS


# ============================================================================
# Async sleep verification (no blocking time.sleep in async code)
# ============================================================================


class TestNoBlockingSleepInAsyncCode:
    """Verify async functions don't use time.sleep()."""

    def test_vision_extractor_no_time_sleep(self):
        """vision_extractor._rate_limit should use asyncio.sleep, not time.sleep."""
        with open("app/engine/vision_extractor.py", "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                # Check all async functions for time.sleep calls
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if (isinstance(child.func, ast.Attribute)
                                and child.func.attr == "sleep"
                                and isinstance(child.func.value, ast.Name)
                                and child.func.value.id == "time"):
                            pytest.fail(
                                f"async function '{node.name}' at line {node.lineno} "
                                f"uses blocking time.sleep() at line {child.lineno}"
                            )

    def test_supabase_storage_no_time_sleep_in_async(self):
        """supabase_storage async methods should not use time.sleep()."""
        with open("app/services/supabase_storage.py", "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if (isinstance(child.func, ast.Attribute)
                                and child.func.attr == "sleep"
                                and isinstance(child.func.value, ast.Name)
                                and child.func.value.id == "time"):
                            pytest.fail(
                                f"async function '{node.name}' at line {node.lineno} "
                                f"uses blocking time.sleep() at line {child.lineno}"
                            )

    def test_vision_rate_limit_is_async(self):
        """_rate_limit should be an async method."""
        with open("app/engine/vision_extractor.py", "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if (isinstance(item, ast.AsyncFunctionDef)
                            and item.name == "_rate_limit"):
                        return  # Found as async — pass
                    if (isinstance(item, ast.FunctionDef)
                            and item.name == "_rate_limit"):
                        pytest.fail(
                            "_rate_limit is a sync method — should be async "
                            "to avoid blocking the event loop"
                        )


# ============================================================================
# Circuit breaker thread safety
# ============================================================================


class TestWebSearchCircuitBreakerThreadSafety:
    """Verify circuit breaker uses thread-safe operations."""

    def test_circuit_breaker_functions_use_lock(self):
        """CB functions should use threading.Lock for global state mutation."""
        with open("app/engine/tools/web_search_tools.py", "r", encoding="utf-8") as f:
            content = f.read()
        assert "threading.Lock()" in content or "threading.Lock(" in content
        assert "_cb_lock" in content

    def test_cb_record_failure_is_atomic(self):
        """Concurrent failures should not corrupt state."""
        from app.engine.tools.web_search_tools import (
            _cb_record_failure,
            _cb_record_success,
            _cb_is_open,
        )
        import app.engine.tools.web_search_tools as ws_mod

        # Reset state
        _cb_record_success()

        # Concurrent failures
        threads = []
        for _ in range(10):
            t = threading.Thread(target=_cb_record_failure)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have recorded all failures without corruption
        with ws_mod._cb_lock:
            assert ws_mod._cb_states.get("default", {}).get("failures", 0) == 10

        # Reset
        _cb_record_success()

    def test_cb_is_open_after_threshold(self):
        """Circuit breaker opens after threshold failures."""
        from app.engine.tools.web_search_tools import (
            _cb_record_failure,
            _cb_record_success,
            _cb_is_open,
        )

        _cb_record_success()  # Reset
        assert not _cb_is_open()

        for _ in range(3):
            _cb_record_failure()

        assert _cb_is_open()
        _cb_record_success()  # Reset


# ============================================================================
# Admin job cleanup
# ============================================================================


class TestIngestionJobCleanup:
    """Verify _ingestion_jobs has bounded growth."""

    @pytest.fixture(autouse=True)
    def reset_jobs(self):
        """Clear jobs between tests."""
        _ingestion_jobs.clear()
        yield
        _ingestion_jobs.clear()

    def test_max_tracked_jobs_is_defined(self):
        assert _MAX_TRACKED_JOBS > 0

    def test_cleanup_noop_under_limit(self):
        """No cleanup when under the limit."""
        _ingestion_jobs["job1"] = {"status": "completed"}
        _cleanup_old_jobs()
        assert "job1" in _ingestion_jobs

    def test_cleanup_removes_completed_when_over_limit(self):
        """Completed jobs are removed when over the limit."""
        # Fill beyond limit
        for i in range(_MAX_TRACKED_JOBS + 5):
            _ingestion_jobs[f"job{i}"] = {"status": "completed"}

        _cleanup_old_jobs()
        assert len(_ingestion_jobs) <= _MAX_TRACKED_JOBS

    def test_cleanup_preserves_pending_jobs(self):
        """Pending/processing jobs are not removed."""
        # Fill with completed
        for i in range(_MAX_TRACKED_JOBS):
            _ingestion_jobs[f"completed{i}"] = {"status": "completed"}

        # Add pending jobs beyond limit
        for i in range(5):
            _ingestion_jobs[f"pending{i}"] = {"status": "pending"}

        _cleanup_old_jobs()

        # All pending jobs should survive
        for i in range(5):
            assert f"pending{i}" in _ingestion_jobs

    def test_cleanup_removes_failed_jobs(self):
        """Failed jobs are also eligible for cleanup."""
        for i in range(_MAX_TRACKED_JOBS + 5):
            _ingestion_jobs[f"failed{i}"] = {"status": "failed"}

        _cleanup_old_jobs()
        assert len(_ingestion_jobs) <= _MAX_TRACKED_JOBS
