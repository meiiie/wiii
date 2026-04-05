"""Finalization helpers for graph_streaming.py."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


async def emit_fallback_answer_if_needed_impl(
    *,
    answer_emitted: bool,
    final_state,
    soul_emotion_emitted: bool,
    extract_and_stream_emotion_then_answer,
    is_pipeline_summary,
    logger_obj,
) -> tuple[list[Any], bool, bool]:
    """Emit one last answer if no node surfaced it during the stream."""
    events: list[Any] = []
    if answer_emitted or not final_state:
        return events, answer_emitted, soul_emotion_emitted

    fallback = final_state.get("final_response", "")
    if not fallback:
        for val in final_state.get("agent_outputs", {}).values():
            if isinstance(val, str) and len(val) > 20:
                fallback = val
                break
    if not fallback:
        thinking_fallback = final_state.get("thinking", "")
        if thinking_fallback and not is_pipeline_summary(thinking_fallback):
            fallback = thinking_fallback
    if not fallback:
        return events, answer_emitted, soul_emotion_emitted

    logger_obj.warning(
        "[STREAM] No answer emitted - using fallback (%d chars)",
        len(fallback),
    )
    async for event in extract_and_stream_emotion_then_answer(
        fallback,
        soul_emotion_emitted,
    ):
        if getattr(event, "type", None) == "emotion":
            soul_emotion_emitted = True
        events.append(event)
    return events, True, soul_emotion_emitted


async def emit_stream_completion_impl(
    *,
    answer_emitted: bool,
    final_state,
    initial_state,
    soul_emotion_emitted: bool,
    session_id: str,
    context,
    start_time: float,
    resolve_runtime_llm_metadata,
    create_sources_event,
    create_metadata_event,
    create_done_event,
    record_llm_runtime_observation,
    registry,
    trace_id,
    emit_stream_finalization,
    extract_and_stream_emotion_then_answer,
    is_pipeline_summary,
    logger_obj,
) -> tuple[list[Any], bool, bool]:
    """Run safety-net answer emission and terminal metadata/done events."""
    events, answer_emitted, soul_emotion_emitted = await emit_fallback_answer_if_needed_impl(
        answer_emitted=answer_emitted,
        final_state=final_state,
        soul_emotion_emitted=soul_emotion_emitted,
        extract_and_stream_emotion_then_answer=extract_and_stream_emotion_then_answer,
        is_pipeline_summary=is_pipeline_summary,
        logger_obj=logger_obj,
    )

    async for event in emit_stream_finalization(
        final_state=final_state,
        initial_state=initial_state,
        session_id=session_id,
        context=context,
        start_time=start_time,
        resolve_runtime_llm_metadata=resolve_runtime_llm_metadata,
        create_sources_event=create_sources_event,
        create_metadata_event=create_metadata_event,
        create_done_event=create_done_event,
        record_llm_runtime_observation=record_llm_runtime_observation,
        registry=registry,
        trace_id=trace_id,
    ):
        events.append(event)

    return events, answer_emitted, soul_emotion_emitted


async def cleanup_stream_tasks_impl(
    *,
    event_queue,
    sentinel,
    tasks: list[asyncio.Task],
) -> None:
    """Cancel background queue forwarders without leaking pending tasks."""
    try:
        event_queue.put_nowait(sentinel)
    except Exception:
        pass

    for task in tasks:
        if task.done():
            continue
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
