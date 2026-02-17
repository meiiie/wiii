"""
Unit test conftest — shared fixtures for all unit tests.
"""
import pytest


@pytest.fixture(autouse=True)
def _disable_rate_limiting():
    """Disable slowapi rate limiting in unit tests.

    The in-memory rate limiter accumulates request counts across the full
    test suite.  Since all tests share the same client IP (127.0.0.1),
    rate limits can be hit when many endpoint tests run together.
    Disabling the limiter prevents cross-test interference.
    """
    from app.core.rate_limit import limiter

    original = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original
