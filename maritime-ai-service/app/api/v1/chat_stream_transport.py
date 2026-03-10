"""Transport helpers for streaming SSE responses."""

import asyncio
import logging
from collections.abc import Callable
from typing import AsyncGenerator


logger = logging.getLogger(__name__)

SSE_KEEPALIVE = ": keepalive\n\n"
DEFAULT_KEEPALIVE_INTERVAL_SEC = 15


async def wrap_sse_with_keepalive(
    *,
    inner_gen: AsyncGenerator[str, None],
    request,
    keepalive_chunk: str = SSE_KEEPALIVE,
    keepalive_interval_sec: float = DEFAULT_KEEPALIVE_INTERVAL_SEC,
    on_inner_error: Callable[[], list[str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Wrap an SSE generator with keepalive heartbeats and disconnect checks.
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _producer() -> None:
        try:
            async for chunk in inner_gen:
                await queue.put(chunk)
        except Exception as exc:
            logger.error("SSE producer error: %s", exc)
            if on_inner_error:
                for chunk in on_inner_error():
                    await queue.put(chunk)
        finally:
            await queue.put(None)

    producer_task = asyncio.create_task(_producer())

    try:
        while True:
            if await request.is_disconnected():
                logger.info("[SSE] Client disconnected, aborting stream")
                producer_task.cancel()
                return

            try:
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=keepalive_interval_sec,
                )
                if item is None:
                    return
                yield item
            except asyncio.TimeoutError:
                yield keepalive_chunk
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
