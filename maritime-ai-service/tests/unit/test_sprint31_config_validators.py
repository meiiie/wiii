"""
Tests for Sprint 31: New configuration validators.

Covers:
- async_pool_min_size: 1-100
- async_pool_max_size: 1-100
- chunk_size: 100-10000
- chunk_overlap: 0-5000
- code_execution_timeout: 1-300
- vision_image_quality: 1-100
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
# async_pool_min_size
# =============================================================================


class TestAsyncPoolMinSize:
    def test_default_valid(self):
        s = _make_settings()
        assert s.async_pool_min_size == 2

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="async_pool_min_size"):
            _make_settings(async_pool_min_size=0)

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="async_pool_min_size"):
            _make_settings(async_pool_min_size=-1)

    def test_over_100_rejected(self):
        with pytest.raises(ValidationError, match="async_pool_min_size"):
            _make_settings(async_pool_min_size=101)

    def test_boundary_1_accepted(self):
        s = _make_settings(async_pool_min_size=1)
        assert s.async_pool_min_size == 1

    def test_boundary_100_accepted(self):
        # Sprint 83: Also set max_size to satisfy cross-field validator (min <= max)
        s = _make_settings(async_pool_min_size=100, async_pool_max_size=100)
        assert s.async_pool_min_size == 100


# =============================================================================
# async_pool_max_size
# =============================================================================


class TestAsyncPoolMaxSize:
    def test_default_valid(self):
        s = _make_settings()
        assert s.async_pool_max_size == 10

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="async_pool_max_size"):
            _make_settings(async_pool_max_size=0)

    def test_over_100_rejected(self):
        with pytest.raises(ValidationError, match="async_pool_max_size"):
            _make_settings(async_pool_max_size=101)


# =============================================================================
# chunk_size
# =============================================================================


class TestChunkSize:
    def test_default_valid(self):
        s = _make_settings()
        assert s.chunk_size == 800

    def test_too_small_rejected(self):
        with pytest.raises(ValidationError, match="chunk_size"):
            _make_settings(chunk_size=50)

    def test_too_large_rejected(self):
        with pytest.raises(ValidationError, match="chunk_size"):
            _make_settings(chunk_size=20000)

    def test_boundary_100_accepted(self):
        # Sprint 83: Also set chunk_overlap=0 to satisfy cross-field validator (overlap < size)
        s = _make_settings(chunk_size=100, chunk_overlap=0)
        assert s.chunk_size == 100


# =============================================================================
# chunk_overlap
# =============================================================================


class TestChunkOverlap:
    def test_default_valid(self):
        s = _make_settings()
        assert s.chunk_overlap == 100

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="chunk_overlap"):
            _make_settings(chunk_overlap=-1)

    def test_zero_accepted(self):
        s = _make_settings(chunk_overlap=0)
        assert s.chunk_overlap == 0

    def test_over_5000_rejected(self):
        with pytest.raises(ValidationError, match="chunk_overlap"):
            _make_settings(chunk_overlap=5001)


# =============================================================================
# code_execution_timeout
# =============================================================================


class TestCodeExecutionTimeout:
    def test_default_valid(self):
        s = _make_settings()
        assert s.code_execution_timeout == 30

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="code_execution_timeout"):
            _make_settings(code_execution_timeout=0)

    def test_negative_rejected(self):
        with pytest.raises(ValidationError, match="code_execution_timeout"):
            _make_settings(code_execution_timeout=-5)

    def test_over_300_rejected(self):
        with pytest.raises(ValidationError, match="code_execution_timeout"):
            _make_settings(code_execution_timeout=301)

    def test_boundary_1_accepted(self):
        s = _make_settings(code_execution_timeout=1)
        assert s.code_execution_timeout == 1


# =============================================================================
# vision_image_quality
# =============================================================================


class TestVisionImageQuality:
    def test_default_valid(self):
        s = _make_settings()
        assert s.vision_image_quality == 85

    def test_zero_rejected(self):
        with pytest.raises(ValidationError, match="vision_image_quality"):
            _make_settings(vision_image_quality=0)

    def test_over_100_rejected(self):
        with pytest.raises(ValidationError, match="vision_image_quality"):
            _make_settings(vision_image_quality=101)

    def test_boundary_1_accepted(self):
        s = _make_settings(vision_image_quality=1)
        assert s.vision_image_quality == 1

    def test_boundary_100_accepted(self):
        s = _make_settings(vision_image_quality=100)
        assert s.vision_image_quality == 100
