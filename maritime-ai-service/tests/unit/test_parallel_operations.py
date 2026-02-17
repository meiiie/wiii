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
