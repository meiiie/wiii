"""Canonical streaming surface for the WiiiRunner-backed runtime."""

from __future__ import annotations

from typing import Any, AsyncGenerator

from app.engine.multi_agent.runtime_contracts import WiiiStreamEvent, WiiiTurnRequest
from app.engine.multi_agent.stream_utils import StreamEvent


async def process_with_multi_agent_streaming(
    *args: Any,
    **kwargs: Any,
) -> AsyncGenerator[StreamEvent, None]:
    """Dispatch to the runner-backed streaming entrypoint.

    The lazy import preserves legacy test patch paths while production callers
    move to the canonical streaming module name.
    """
    from app.engine.multi_agent.graph_streaming import (
        process_with_multi_agent_streaming as stream,
    )

    async for event in stream(*args, **kwargs):
        yield event


async def stream_wiii_turn(
    request: WiiiTurnRequest,
) -> AsyncGenerator[WiiiStreamEvent, None]:
    """Stream one native Wiii turn while preserving existing wire events."""

    async for event in process_with_multi_agent_streaming(**request.to_runtime_kwargs()):
        yield WiiiStreamEvent.from_legacy_tuple(event)


__all__ = ["process_with_multi_agent_streaming", "stream_wiii_turn"]
