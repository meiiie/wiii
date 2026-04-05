"""Opening-phase helpers for direct_execution."""

from __future__ import annotations

import asyncio


async def start_direct_opening_phase_impl(
    *,
    query: str,
    state,
    push_event,
    infer_direct_reasoning_cue,
    stream_direct_wait_heartbeats,
) -> tuple[str, asyncio.Event, asyncio.Task, bool]:
    opening_cue = infer_direct_reasoning_cue(query, state, [])
    opening_thinking_started = False

    thinking_stop = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        stream_direct_wait_heartbeats(
            push_event,
            query=query,
            phase="attune",
            cue=opening_cue,
            stop_signal=thinking_stop,
        )
    )
    return opening_cue, thinking_stop, heartbeat_task, opening_thinking_started


async def finalize_direct_opening_phase_impl(
    *,
    thinking_stop: asyncio.Event,
    heartbeat_task: asyncio.Task,
    logger_obj,
) -> None:
    thinking_stop.set()
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger_obj.debug("[DIRECT] Initial heartbeat shutdown skipped: %s", exc)
