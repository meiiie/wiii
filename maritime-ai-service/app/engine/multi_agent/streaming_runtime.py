"""Canonical streaming surface for the WiiiRunner-backed runtime."""

from __future__ import annotations

from typing import Any, AsyncGenerator

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

__all__ = ["process_with_multi_agent_streaming"]
