import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.v1.chat_stream_transport import (
    DEFAULT_KEEPALIVE_INTERVAL_SEC,
    SSE_KEEPALIVE,
    wrap_sse_with_keepalive,
)


def test_keepalive_transport_defaults():
    assert SSE_KEEPALIVE == ": keepalive\n\n"
    assert DEFAULT_KEEPALIVE_INTERVAL_SEC == 15


@pytest.mark.asyncio
async def test_wrap_sse_with_keepalive_passes_through_chunks():
    async def inner():
        yield "chunk1"
        yield "chunk2"

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    chunks = []
    async for chunk in wrap_sse_with_keepalive(
        inner_gen=inner(),
        request=mock_request,
    ):
        chunks.append(chunk)

    assert chunks == ["chunk1", "chunk2"]


@pytest.mark.asyncio
async def test_wrap_sse_with_keepalive_sends_heartbeat_on_idle():
    async def slow_inner():
        await asyncio.sleep(0.05)
        yield "data"

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    chunks = []
    async for chunk in wrap_sse_with_keepalive(
        inner_gen=slow_inner(),
        request=mock_request,
        keepalive_interval_sec=0.01,
    ):
        chunks.append(chunk)
        if len(chunks) > 10:
            break

    assert SSE_KEEPALIVE in chunks
    assert "data" in chunks


@pytest.mark.asyncio
async def test_wrap_sse_with_keepalive_uses_error_callback():
    async def failing_inner():
        yield "first"
        raise ValueError("boom")

    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    chunks = []
    async for chunk in wrap_sse_with_keepalive(
        inner_gen=failing_inner(),
        request=mock_request,
        on_inner_error=lambda: ["error-chunk"],
    ):
        chunks.append(chunk)

    assert chunks == ["first", "error-chunk"]
