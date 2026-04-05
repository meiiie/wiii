import asyncio

import pytest

from app.core.exceptions import ProviderUnavailableError
from app.engine.multi_agent.graph_stream_merge_runtime import (
    forward_graph_events_impl,
)


class _ExplodingGraph:
    def __init__(self, exc):
        self._exc = exc

    async def astream(self, *_args, **_kwargs):
        raise self._exc
        yield  # pragma: no cover


@pytest.mark.asyncio
async def test_forward_graph_events_preserves_provider_unavailable():
    merged_queue: asyncio.Queue = asyncio.Queue()
    exc = ProviderUnavailableError(
        provider="google",
        reason_code="rate_limit",
        message="Provider tam thoi bi gioi han.",
    )

    await forward_graph_events_impl(
        graph=_ExplodingGraph(exc),
        initial_state={},
        invoke_config={},
        merged_queue=merged_queue,
    )

    msg_type, payload = await merged_queue.get()
    assert msg_type == "provider_unavailable"
    assert payload is exc

    done_type, done_payload = await merged_queue.get()
    assert done_type == "graph_done"
    assert done_payload is None
