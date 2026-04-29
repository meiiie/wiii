"""
Tests for Sprint 26: SSE keepalive heartbeat and client disconnect detection.

Covers:
- _keepalive_generator sends keepalive comments during idle periods
- _keepalive_generator aborts on client disconnect
- _keepalive_generator passes through data from inner generator
- _keepalive_generator handles inner generator errors
- format_sse creates valid SSE format
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.api.v1.chat_stream import (
    format_sse,
    _keepalive_generator,
    SSE_KEEPALIVE,
    KEEPALIVE_INTERVAL_SEC,
)


class TestFormatSSE:
    """Test SSE formatting helper."""

    def test_basic_format(self):
        """Should produce valid SSE: event + data + double newline."""
        result = format_sse("answer", {"content": "hello"})
        assert result.startswith("event: answer\n")
        assert "data: " in result
        assert result.endswith("\n\n")

    def test_unicode_content(self):
        """Vietnamese content should be preserved (ensure_ascii=False)."""
        result = format_sse("answer", {"content": "Xin chao!"})
        assert "Xin chao!" in result

    def test_keepalive_constant(self):
        """SSE keepalive should be a comment line."""
        assert SSE_KEEPALIVE == ": keepalive\n\n"

    def test_keepalive_interval(self):
        """Keepalive interval should be 15 seconds."""
        assert KEEPALIVE_INTERVAL_SEC == 15


class TestKeepaliveGenerator:
    """Test _keepalive_generator async wrapper."""

    @pytest.mark.asyncio
    async def test_passes_through_data(self):
        """Data from inner generator should pass through unchanged."""
        async def inner():
            yield "chunk1"
            yield "chunk2"

        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(return_value=False)

        chunks = []
        async for chunk in _keepalive_generator(inner(), mock_request):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]

    @pytest.mark.asyncio
    async def test_sends_keepalive_on_timeout(self, monkeypatch):
        """Should send keepalive when inner generator is idle."""
        async def slow_inner():
            await asyncio.sleep(0.5)  # Simulate delay
            yield "data"

        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(return_value=False)

        import app.api.v1.chat_stream as module
        monkeypatch.setattr(
            module.settings,
            "llm_stream_keepalive_interval_seconds",
            0.1,
        )

        chunks = []
        async for chunk in _keepalive_generator(slow_inner(), mock_request):
            chunks.append(chunk)
            if len(chunks) > 10:
                break  # Safety limit

        # Should have at least one keepalive before the data
        assert SSE_KEEPALIVE in chunks
        assert "data" in chunks

    @pytest.mark.asyncio
    async def test_aborts_on_client_disconnect(self):
        """Should stop when client disconnects."""
        async def infinite_inner():
            while True:
                yield "data"
                await asyncio.sleep(0.01)

        disconnect_after = 3
        call_count = 0

        async def is_disconnected():
            nonlocal call_count
            call_count += 1
            return call_count > disconnect_after

        mock_request = MagicMock()
        mock_request.is_disconnected = is_disconnected

        chunks = []
        async for chunk in _keepalive_generator(infinite_inner(), mock_request):
            chunks.append(chunk)
            if len(chunks) > 100:
                break  # Safety

        # Should have stopped before exhausting generator
        assert len(chunks) <= disconnect_after + 5  # Some tolerance

    @pytest.mark.asyncio
    async def test_handles_inner_generator_error(self):
        """Should emit error event when inner generator raises."""
        async def failing_inner():
            yield "first"
            raise ValueError("Test error")

        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(return_value=False)

        chunks = []
        async for chunk in _keepalive_generator(failing_inner(), mock_request):
            chunks.append(chunk)

        assert "first" in chunks
        # Should have an error event (generic message, not raw exception)
        error_chunks = [c for c in chunks if "error" in c and "Internal processing error" in c]
        assert len(error_chunks) >= 1

    @pytest.mark.asyncio
    async def test_handles_inner_generator_error_with_done_when_start_time_supplied(
        self,
        monkeypatch,
    ):
        """Endpoint wrapper should finalize errored streams so FE can stop thinking."""
        async def failing_inner():
            yield "first"
            raise ValueError("Test error")

        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(return_value=False)

        import app.api.v1.chat_stream as module

        monkeypatch.setattr(module.time, "time", lambda: 105.0)

        chunks = []
        async for chunk in _keepalive_generator(
            failing_inner(),
            mock_request,
            start_time=100.0,
        ):
            chunks.append(chunk)

        assert "first" in chunks
        assert any("event: error" in chunk for chunk in chunks)
        done_chunks = [chunk for chunk in chunks if "event: done" in chunk]
        assert len(done_chunks) == 1
        assert '"processing_time": 5.0' in done_chunks[0]

    @pytest.mark.asyncio
    async def test_empty_inner_generator(self):
        """Should handle an inner generator that yields nothing."""
        async def empty_inner():
            return
            yield  # Make it an async generator

        mock_request = MagicMock()
        mock_request.is_disconnected = AsyncMock(return_value=False)

        chunks = []
        async for chunk in _keepalive_generator(empty_inner(), mock_request):
            chunks.append(chunk)

        assert chunks == []
