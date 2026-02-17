"""
Tests for Sprint 32: asyncpg_url property and similarity threshold validators.

Covers:
- settings.asyncpg_url: Centralized URL conversion for asyncpg
- Similarity threshold validators: 8 float fields must be 0.0-1.0
"""

import pytest
from pydantic import ValidationError


def _make_settings(**overrides):
    """Create Settings with overrides, bypassing .env."""
    from app.core.config import Settings
    defaults = {
        "environment": "development",
        "api_key": "test-key",
        "google_api_key": "test-google-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)


# =============================================================================
# asyncpg_url property
# =============================================================================


class TestAsyncpgUrl:
    """Test centralized asyncpg URL conversion."""

    def test_converts_asyncpg_format(self):
        """postgresql+asyncpg:// should become postgresql://."""
        s = _make_settings(database_url="postgresql+asyncpg://user:pass@host:5432/db")
        assert s.asyncpg_url == "postgresql://user:pass@host:5432/db"

    def test_converts_postgres_shorthand(self):
        """postgres:// should become postgresql://."""
        s = _make_settings(database_url="postgres://user:pass@host:5432/db")
        assert s.asyncpg_url == "postgresql://user:pass@host:5432/db"

    def test_plain_postgresql_unchanged(self):
        """postgresql:// should remain unchanged."""
        s = _make_settings(database_url="postgresql://user:pass@host:5432/db")
        assert s.asyncpg_url == "postgresql://user:pass@host:5432/db"

    def test_fallback_to_components(self):
        """When no DATABASE_URL, should build from host/port/user/pass/db."""
        s = _make_settings(
            database_url=None,
            postgres_user="wiii",
            postgres_password="secret",
            postgres_host="localhost",
            postgres_port=5433,
            postgres_db="wiii_ai",
        )
        assert s.asyncpg_url == "postgresql://wiii:secret@localhost:5433/wiii_ai"

    def test_default_fallback(self):
        """Default settings should produce valid asyncpg URL."""
        s = _make_settings(database_url=None)
        url = s.asyncpg_url
        assert url.startswith("postgresql://")
        assert "postgresql+asyncpg" not in url


# =============================================================================
# Similarity threshold validators
# =============================================================================


SIMILARITY_FIELDS = [
    "similarity_threshold",
    "fact_similarity_threshold",
    "memory_duplicate_threshold",
    "memory_related_threshold",
    "cache_similarity_threshold",
    "quality_skip_threshold",
    "insight_duplicate_threshold",
    "insight_contradiction_threshold",
]


class TestSimilarityThresholdValidators:
    """All 8 similarity thresholds must be between 0.0 and 1.0."""

    def test_defaults_valid(self):
        """Default values for all similarity fields should be valid."""
        s = _make_settings()
        for field in SIMILARITY_FIELDS:
            val = getattr(s, field)
            assert 0.0 <= val <= 1.0, f"{field}={val} out of range"

    @pytest.mark.parametrize("field", SIMILARITY_FIELDS)
    def test_negative_rejected(self, field):
        with pytest.raises(ValidationError, match="Similarity threshold"):
            _make_settings(**{field: -0.1})

    @pytest.mark.parametrize("field", SIMILARITY_FIELDS)
    def test_over_1_rejected(self, field):
        with pytest.raises(ValidationError, match="Similarity threshold"):
            _make_settings(**{field: 1.1})

    @pytest.mark.parametrize("field", SIMILARITY_FIELDS)
    def test_boundary_0_accepted(self, field):
        s = _make_settings(**{field: 0.0})
        assert getattr(s, field) == 0.0

    @pytest.mark.parametrize("field", SIMILARITY_FIELDS)
    def test_boundary_1_accepted(self, field):
        s = _make_settings(**{field: 1.0})
        assert getattr(s, field) == 1.0

    @pytest.mark.parametrize("field", SIMILARITY_FIELDS)
    def test_mid_value_accepted(self, field):
        s = _make_settings(**{field: 0.5})
        assert getattr(s, field) == 0.5


# =============================================================================
# Sources pool cleanup
# =============================================================================


class TestSourcesPoolCleanup:
    """Test the close_pool() function for resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_pool_when_none(self):
        """close_pool() should be no-op when pool is None."""
        from app.api.v1 import sources
        original = sources._pool
        sources._pool = None
        try:
            await sources.close_pool()  # Should not raise
            assert sources._pool is None
        finally:
            sources._pool = original

    @pytest.mark.asyncio
    async def test_close_pool_calls_close(self):
        """close_pool() should call pool.close() and reset to None."""
        from unittest.mock import AsyncMock, MagicMock
        from app.api.v1 import sources

        mock_pool = MagicMock()
        mock_pool.close = AsyncMock()
        original = sources._pool
        sources._pool = mock_pool
        try:
            await sources.close_pool()
            mock_pool.close.assert_called_once()
            assert sources._pool is None
        finally:
            sources._pool = original
