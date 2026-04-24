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
    idle_timeout_sec: float | None = None,
    on_inner_error: Callable[[], list[str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Wrap an SSE generator with keepalive heartbeats and disconnect checks.
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    last_inner_chunk_at = loop.time()
    sent_keepalive_since_inner = False

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
                wait_timeout = keepalive_interval_sec
                idle_enabled = bool(idle_timeout_sec and idle_timeout_sec > 0)
                if idle_enabled:
                    idle_remaining = float(idle_timeout_sec) - (loop.time() - last_inner_chunk_at)
                    if idle_remaining <= 0:
                        raise asyncio.TimeoutError
                    wait_timeout = min(keepalive_interval_sec, idle_remaining)
                item = await asyncio.wait_for(
                    queue.get(),
                    timeout=wait_timeout,
                )
                if item is None:
                    return
                last_inner_chunk_at = loop.time()
                sent_keepalive_since_inner = False
                yield item
            except asyncio.TimeoutError:
                if idle_timeout_sec and idle_timeout_sec > 0:
                    idle_elapsed = loop.time() - last_inner_chunk_at
                    if idle_elapsed >= idle_timeout_sec:
                        if (
                            not sent_keepalive_since_inner
                            and keepalive_interval_sec < idle_timeout_sec
                        ):
                            sent_keepalive_since_inner = True
                            yield keepalive_chunk
                            continue
                        logger.warning(
                            "[SSE] Inner generator idle timeout after %.2fs",
                            idle_timeout_sec,
                        )
                        producer_task.cancel()
                        if on_inner_error:
                            for chunk in on_inner_error():
                                yield chunk
                        return
                sent_keepalive_since_inner = True
                yield keepalive_chunk
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
