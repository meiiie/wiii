"""
Tests for retry_on_transient decorator — Sprint 68.

Tests transient error classification, retry behavior, backoff timing, and config metadata.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.core.resilience import _is_transient, retry_on_transient


# =============================================================================
# _is_transient classification
# =============================================================================


class TestIsTransient:
    """Test _is_transient() error classification."""

    def test_connection_error_is_transient(self):
        assert _is_transient(ConnectionError("refused")) is True

    def test_timeout_error_is_transient(self):
        assert _is_transient(TimeoutError("timed out")) is True

    def test_asyncio_timeout_is_transient(self):
        assert _is_transient(asyncio.TimeoutError()) is True

    def test_value_error_not_transient(self):
        assert _is_transient(ValueError("bad value")) is False

    def test_runtime_error_not_transient(self):
        assert _is_transient(RuntimeError("unexpected")) is False

    def test_http_429_is_transient(self):
        exc = Exception("rate limited")
        exc.status_code = 429
        assert _is_transient(exc) is True

    def test_http_503_is_transient(self):
        exc = Exception("unavailable")
        exc.status_code = 503
        assert _is_transient(exc) is True

    def test_http_502_is_transient(self):
        exc = Exception("bad gateway")
        exc.status = 502
        assert _is_transient(exc) is True

    def test_http_504_is_transient(self):
        exc = Exception("timeout")
        exc.status_code = 504
        assert _is_transient(exc) is True

    def test_http_400_not_transient(self):
        exc = Exception("bad request")
        exc.status_code = 400
        assert _is_transient(exc) is False

    def test_resource_exhausted_by_name(self):
        """Google API ResourceExhausted detected by class name."""

        class ResourceExhausted(Exception):
            pass

        assert _is_transient(ResourceExhausted()) is True

    def test_rate_limit_error_by_name(self):
        """OpenAI RateLimitError detected by class name."""

        class RateLimitError(Exception):
            pass

        assert _is_transient(RateLimitError()) is True


# =============================================================================
# retry_on_transient decorator behavior
# =============================================================================


class TestRetryOnTransient:
    """Test retry_on_transient() decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        """No retry needed when function succeeds."""
        mock_fn = AsyncMock(return_value="ok")
        decorated = retry_on_transient()(mock_fn)
        result = await decorated()
        assert result == "ok"
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self):
        """Retries on TimeoutError, then succeeds."""
        mock_fn = AsyncMock(side_effect=[TimeoutError("t"), "ok"])
        decorated = retry_on_transient(max_attempts=3, base_delay=0.01)(mock_fn)

        with patch("app.core.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await decorated()

        assert result == "ok"
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_connection_error(self):
        """Retries on ConnectionError."""
        mock_fn = AsyncMock(side_effect=[ConnectionError("c"), "ok"])
        decorated = retry_on_transient(max_attempts=3, base_delay=0.01)(mock_fn)

        with patch("app.core.resilience.asyncio.sleep", new_callable=AsyncMock):
            result = await decorated()

        assert result == "ok"
        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_exhausted_raises(self):
        """Raises after max_attempts exhausted."""
        mock_fn = AsyncMock(side_effect=TimeoutError("always fails"))
        decorated = retry_on_transient(max_attempts=3, base_delay=0.01)(mock_fn)

        with patch("app.core.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TimeoutError):
                await decorated()

        assert mock_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_value_error(self):
        """ValueError is NOT transient — no retry, raises immediately."""
        mock_fn = AsyncMock(side_effect=ValueError("permanent"))
        decorated = retry_on_transient(max_attempts=3)(mock_fn)

        with pytest.raises(ValueError):
            await decorated()

        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_respects_max_attempts(self):
        """max_attempts=2 means only 2 tries."""
        mock_fn = AsyncMock(side_effect=TimeoutError("t"))
        decorated = retry_on_transient(max_attempts=2, base_delay=0.01)(mock_fn)

        with patch("app.core.resilience.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(TimeoutError):
                await decorated()

        assert mock_fn.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_config_metadata(self):
        """Decorator attaches retry_config metadata."""
        mock_fn = AsyncMock(return_value="ok")
        decorated = retry_on_transient(max_attempts=5, base_delay=2.0)(mock_fn)
        assert hasattr(decorated, "retry_config")
        assert decorated.retry_config["max_attempts"] == 5
        assert decorated.retry_config["base_delay"] == 2.0

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        """functools.wraps preserves __name__."""

        async def my_function():
            return "ok"

        decorated = retry_on_transient()(my_function)
        assert decorated.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_backoff_delay_increases(self):
        """Verify exponential backoff: delays increase with each attempt."""
        mock_fn = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), "ok"])
        decorated = retry_on_transient(max_attempts=3, base_delay=1.0, jitter=False)(mock_fn)

        sleep_calls = []
        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("app.core.resilience.asyncio.sleep", side_effect=mock_sleep):
            result = await decorated()

        assert result == "ok"
        assert len(sleep_calls) == 2
        # First retry: 1.0s, second retry: 2.0s (exponential)
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Delay is capped at max_delay."""
        mock_fn = AsyncMock(side_effect=[TimeoutError(), TimeoutError(), TimeoutError(), "ok"])
        decorated = retry_on_transient(max_attempts=4, base_delay=5.0, max_delay=8.0, jitter=False)(mock_fn)

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("app.core.resilience.asyncio.sleep", side_effect=mock_sleep):
            result = await decorated()

        assert result == "ok"
        # base=5, attempt2=10->capped to 8, attempt3=20->capped to 8
        assert sleep_calls[0] == pytest.approx(5.0)
        assert sleep_calls[1] == pytest.approx(8.0)
        assert sleep_calls[2] == pytest.approx(8.0)
