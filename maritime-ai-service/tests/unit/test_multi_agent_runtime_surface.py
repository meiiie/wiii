"""Guards for canonical WiiiRunner runtime import surfaces."""

from unittest.mock import AsyncMock, patch

import pytest

from app.engine.multi_agent.runtime import process_with_multi_agent
from app.engine.multi_agent.streaming_runtime import process_with_multi_agent_streaming
from app.engine.multi_agent.stream_utils import create_status_event


@pytest.mark.asyncio
async def test_runtime_surface_delegates_to_sync_entrypoint():
    process = AsyncMock(return_value={"response": "ok"})

    with patch("app.engine.multi_agent.graph.process_with_multi_agent", new=process):
        result = await process_with_multi_agent(
            query="hello",
            user_id="user-1",
            session_id="session-1",
        )

    assert result == {"response": "ok"}
    process.assert_awaited_once()


@pytest.mark.asyncio
async def test_streaming_runtime_surface_delegates_to_streaming_entrypoint():
    expected_event = await create_status_event("ok")

    async def stream(*_args, **_kwargs):
        yield expected_event

    with patch(
        "app.engine.multi_agent.graph_streaming.process_with_multi_agent_streaming",
        new=stream,
    ):
        events = [
            event
            async for event in process_with_multi_agent_streaming(
                query="hello",
                user_id="user-1",
                session_id="session-1",
            )
        ]

    assert events == [expected_event]
