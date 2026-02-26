"""
Streaming Chat API - Server-Sent Events (SSE)

CHỈ THỊ LMS INTEGRATION: Streaming response cho real-time UX
- Event types: thinking, answer, sources, suggested_questions, metadata, done, error
- Flow: Tool execution first, then stream final answer

**Feature: streaming-api**
"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from app.api.deps import RequireAuth
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.schemas import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


def format_sse(event: str, data: dict, event_id: int | None = None) -> str:
    """Format data as Server-Sent Event with optional id for reconnection."""
    parts = []
    if event_id is not None:
        parts.append(f"id: {event_id}")
    parts.append(f"event: {event}")
    parts.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    parts.append("")
    parts.append("")
    return "\n".join(parts)


SSE_KEEPALIVE = ": keepalive\n\n"
KEEPALIVE_INTERVAL_SEC = 15  # Send keepalive every 15 seconds


async def _keepalive_generator(
    inner_gen: AsyncGenerator[str, None],
    request: Request,
) -> AsyncGenerator[str, None]:
    """
    Wrap an SSE generator with keepalive heartbeats and client disconnect detection.

    Sprint 26: Fixes CRITICAL-6 (no heartbeat) and CRITICAL-7 (no disconnect detection).
    Pattern: Claude API `ping` events / SSE spec comment lines.

    - Sends `: keepalive\\n\\n` every 15s during idle periods
    - Checks `request.is_disconnected()` to abort when client disconnects
    """
    import asyncio

    # Use an asyncio.Queue to bridge the inner generator and keepalive logic
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    done = False

    async def _producer():
        nonlocal done
        try:
            async for chunk in inner_gen:
                await queue.put(chunk)
        except Exception as e:
            logger.error("SSE producer error: %s", e)
            await queue.put(format_sse("error", {"message": "Internal processing error", "type": "internal_error"}))
        finally:
            done = True
            await queue.put(None)  # Sentinel

    producer_task = asyncio.create_task(_producer())

    try:
        while True:
            # Check client disconnect
            if await request.is_disconnected():
                logger.info("[SSE] Client disconnected, aborting stream")
                producer_task.cancel()
                return

            try:
                item = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_INTERVAL_SEC)
                if item is None:
                    return  # Stream complete
                yield item
            except asyncio.TimeoutError:
                # No data for 15s — send keepalive
                yield SSE_KEEPALIVE
    finally:
        if not producer_task.done():
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass


# =============================================================================
# P3+ SOTA: Full CRAG Pipeline + True Token Streaming (Dec 2025)
# Pattern: OpenAI Responses API + Claude Extended Thinking + Gemini astream
# Best of both worlds: V1 quality + V2 streaming UX
# =============================================================================

@router.post("/chat/stream/v3")
@limiter.limit("30/minute")
async def chat_stream_v3(
    request: Request,
    chat_request: ChatRequest,
    background_tasks: BackgroundTasks,
    auth: RequireAuth
):
    """
    V3 SOTA: Full Multi-Agent Graph + Interleaved Streaming
    
    ==================================================================
    REFACTORED (2025-12-21): Now uses SAME pipeline as V1 (/chat)
    but with progressive streaming at each graph node.
    ==================================================================
    
    Architecture:
    - Quality: Full Multi-Agent Graph (Supervisor → TutorAgent → GraderAgent → Synthesizer)
    - UX: Progressive events at each step + token streaming from Synthesizer
    - Result: V1 quality + streaming transparency
    
    Event Types (OpenAI Responses API pattern):
    - status: Processing stage updates (typing indicator, shows current node)
    - thinking: AI reasoning steps (routing, tool calls, quality check)
    - answer: Response tokens (streamed from Synthesizer)
    - sources: Citation list with image_url for PDF highlighting
    - metadata: reasoning_trace, confidence, timing
    - done: Stream complete
    - error: Error occurred
    
    Timeline (expected):
    - 0s: First status event (user sees progress immediately)
    - 4-6s: Supervisor routing complete
    - 40-50s: TutorAgent + CRAG complete
    - 55-60s: GraderAgent quality check (or skipped if high confidence)
    - 65-75s: Synthesizer + answer tokens + done
    
    **Feature: v3-full-graph-streaming**
    """
    start_time = time.time()

    logger.info(
        "[STREAM-V3] Request from %s: %s...",
        chat_request.user_id, chat_request.message[:50]
    )
    
    # SSE reconnection support: read Last-Event-ID header
    last_event_id = request.headers.get("last-event-id")
    if last_event_id:
        logger.info("[STREAM-V3] Reconnect with Last-Event-ID: %s", last_event_id)

    async def generate_events_v3() -> AsyncGenerator[str, None]:
        # SSE spec: retry field tells browser reconnection interval (ms)
        yield "retry: 3000\n\n"
        event_counter = 0

        # Sprint 165: Emit first status event IMMEDIATELY — user sees progress within <100ms
        event_counter += 1
        yield format_sse("status", {
            "content": "Đang chuẩn bị...",
            "step": "preparing",
            "node": "system",
        }, event_id=event_counter)

        # Sprint 154: Facebook cookie for logged-in search
        fb_cookie = request.headers.get("x-facebook-cookie", "")
        if fb_cookie and settings.enable_facebook_cookie:
            from app.engine.search_platforms.facebook_context import set_facebook_cookie
            set_facebook_cookie(fb_cookie)

        try:
            # Import Multi-Agent streaming function
            from app.engine.multi_agent.graph import process_with_multi_agent_streaming

            # Sprint 121b: Use SAME context-building pipeline as sync /chat endpoint
            # Previously V3 built a minimal context dict (no history, no facts, no save).
            # Now we go through ChatOrchestrator-equivalent steps for full context.
            from app.services.chat_service import get_chat_service
            chat_svc = get_chat_service()
            orchestrator = chat_svc._orchestrator

            # STAGE 1: Session management (same as sync path)
            session_id_input = chat_request.session_id or ""
            session = orchestrator._session_manager.get_or_create_session(
                str(chat_request.user_id), session_id_input or None
            )
            effective_session_id = session.session_id
            effective_session_id_str = str(effective_session_id)

            # STAGE 2: Save user message to DB (same as sync path)
            if orchestrator._chat_history and orchestrator._chat_history.is_available():
                try:
                    orchestrator._chat_history.save_message(
                        effective_session_id, "user", chat_request.message
                    )
                except Exception as save_err:
                    logger.warning("[STREAM-V3] Failed to save user message: %s", save_err)

            # STAGE 3: Build full context via InputProcessor (loads history, facts, memory)
            context = {}
            try:
                chat_context = await orchestrator._input_processor.build_context(
                    request=chat_request,
                    session_id=effective_session_id,
                    user_name=session.user_name
                )
                # Convert ChatContext to dict for multi-agent graph
                context = {
                    "user_id": chat_request.user_id,
                    "user_role": chat_request.role.value,
                    "user_name": chat_context.user_name,
                    "conversation_history": chat_context.conversation_history or "",
                    "langchain_messages": chat_context.langchain_messages or [],
                    "semantic_context": chat_context.semantic_context or "",
                    "core_memory_block": chat_context.core_memory_block or "",
                    "user_facts": getattr(chat_context, 'user_facts', []),
                    "pronoun_style": getattr(chat_context, 'pronoun_style', None)
                        or getattr(session.state, 'pronoun_style', None),
                    "conversation_summary": chat_context.conversation_summary or "",
                    "history_list": chat_context.history_list or [],
                    "mood_hint": getattr(chat_context, 'mood_hint', ""),
                    "is_follow_up": bool(chat_context.history_list),
                    # Sprint 203: Compute conversation phase (Pi/Gemini-inspired)
                    "conversation_phase": (
                        "opening" if getattr(session.state, 'total_responses', 0) == 0
                        else ("engaged" if getattr(session.state, 'total_responses', 0) < 5
                              else ("deep" if getattr(session.state, 'total_responses', 0) < 20 else "closing"))
                    ),
                    "total_responses": getattr(session.state, 'total_responses', 0),
                    "name_usage_count": getattr(session.state, 'name_usage_count', 0),
                    "recent_phrases": getattr(session.state, 'recent_phrases', []),
                    # Sprint 166: Preview settings from ChatRequest
                    "show_previews": chat_request.show_previews,
                    "preview_types": chat_request.preview_types,
                    "preview_max_count": chat_request.preview_max_count,
                    # Sprint 179: Multimodal Vision images
                    "images": [img.model_dump() for img in chat_context.images] if getattr(chat_context, 'images', None) else None,
                }
            except Exception as ctx_err:
                logger.warning("[STREAM-V3] Full context build failed, using minimal: %s", ctx_err)
                context = {
                    "user_id": chat_request.user_id,
                    "user_role": chat_request.role.value,
                    "user_name": None,
                    "conversation_history": "",
                }

            # Store for post-stream message saving
            _v3_orchestrator = orchestrator
            _v3_session_id = effective_session_id
            _accumulated_answer: list[str] = []

            # Stream events from Multi-Agent Graph
            async for event in process_with_multi_agent_streaming(
                query=chat_request.message,
                user_id=chat_request.user_id,
                session_id=effective_session_id_str,
                context=context,
                domain_id=chat_request.domain_id,
                thinking_effort=getattr(chat_request, 'thinking_effort', None),
            ):
                # Convert StreamEvent to SSE format
                # IMPORTANT: status and thinking are separate SSE event types.
                # Status = pipeline progress (always visible in progress panel).
                # Thinking = AI reasoning (respects show_thinking setting).
                event_type = event.type

                if event_type == "status":
                    event_counter += 1
                    sse_data = {
                        "content": event.content,
                        "step": event.step,
                        "node": event.node,
                    }
                    if event.details:
                        sse_data["details"] = event.details
                    yield format_sse("status", sse_data, event_id=event_counter)

                elif event_type == "thinking":
                    event_counter += 1
                    yield format_sse("thinking", {
                        "content": event.content,
                        "step": event.step,
                        "confidence": event.confidence,
                        "details": event.details,
                    }, event_id=event_counter)

                elif event_type == "answer":
                    event_counter += 1
                    _accumulated_answer.append(event.content)
                    yield format_sse("answer", {"content": event.content}, event_id=event_counter)

                elif event_type == "tool_call":
                    event_counter += 1
                    yield format_sse("tool_call", {
                        "content": event.content,
                        "node": event.node,
                        "step": event.step,
                    }, event_id=event_counter)

                elif event_type == "thinking_start":
                    event_counter += 1
                    data = {
                        "type": "thinking_start",
                        "content": event.content,
                        "node": event.node,
                    }
                    if event.details:
                        data.update(event.details)
                    # Sprint 145: Forward summary for Claude-like collapsed header
                    if event.details and event.details.get("summary"):
                        data["summary"] = event.details["summary"]
                    yield format_sse("thinking_start", data, event_id=event_counter)

                elif event_type == "thinking_end":
                    event_counter += 1
                    data = {
                        "type": "thinking_end",
                        "node": event.node,
                    }
                    if event.details:
                        data.update(event.details)
                    yield format_sse("thinking_end", data, event_id=event_counter)

                elif event_type == "thinking_delta":
                    event_counter += 1
                    yield format_sse("thinking_delta", {
                        "content": event.content,
                        "node": event.node,
                    }, event_id=event_counter)

                elif event_type == "tool_result":
                    event_counter += 1
                    yield format_sse("tool_result", {
                        "content": event.content,
                        "node": event.node,
                        "step": event.step,
                    }, event_id=event_counter)

                elif event_type == "action_text":
                    # Sprint 147: Bold narrative between thinking blocks
                    event_counter += 1
                    yield format_sse("action_text", {
                        "content": event.content,
                        "node": event.node,
                    }, event_id=event_counter)

                elif event_type == "browser_screenshot":
                    # Sprint 153: Browser screenshot for visual transparency
                    event_counter += 1
                    yield format_sse("browser_screenshot", {
                        "content": event.content,
                        "node": event.node,
                    }, event_id=event_counter)

                elif event_type == "preview":
                    # Sprint 166: Rich preview card
                    event_counter += 1
                    yield format_sse("preview", {
                        "content": event.content,
                        "node": event.node,
                    }, event_id=event_counter)

                elif event_type == "artifact":
                    # Sprint 167: Interactive artifact (code, HTML, data)
                    # L-6: Feature-gated — skip if artifacts disabled
                    if not settings.enable_artifacts:
                        continue
                    event_counter += 1
                    yield format_sse("artifact", {
                        "content": event.content,
                        "node": event.node,
                    }, event_id=event_counter)

                elif event_type == "domain_notice":
                    event_counter += 1
                    yield format_sse("domain_notice", {
                        "content": event.content,
                    }, event_id=event_counter)

                elif event_type == "emotion":
                    # Sprint 135: Soul emotion event for avatar control
                    event_counter += 1
                    yield format_sse("emotion", event.content, event_id=event_counter)

                elif event_type == "sources":
                    event_counter += 1
                    yield format_sse("sources", {"sources": event.content}, event_id=event_counter)

                elif event_type == "metadata":
                    event_counter += 1
                    metadata = event.content
                    metadata["streaming_version"] = "v3-graph"
                    yield format_sse("metadata", metadata, event_id=event_counter)

                elif event_type == "done":
                    event_counter += 1
                    yield format_sse("done", event.content, event_id=event_counter)

                elif event_type == "error":
                    event_counter += 1
                    yield format_sse("error", {
                        "message": event.content.get("message", str(event.content)),
                        "type": "stream_error",
                    }, event_id=event_counter)
                    return

                else:
                    logger.warning("[STREAM-V3] Unknown event type: %s", event_type)

                # Micro delay for flush
                await asyncio.sleep(0.01)

            # Sprint 121b: Save assistant response to DB for conversation continuity
            if _accumulated_answer and _v3_orchestrator._chat_history and _v3_orchestrator._chat_history.is_available():
                try:
                    full_answer = "".join(_accumulated_answer)
                    _v3_orchestrator._chat_history.save_message(
                        _v3_session_id, "assistant", full_answer
                    )
                    logger.info("[STREAM-V3] Saved assistant message (%d chars) to session %s",
                                len(full_answer), _v3_session_id)
                except Exception as save_err:
                    logger.warning("[STREAM-V3] Failed to save assistant message: %s", save_err)

            # Sprint 170: Update Living Agent emotional state on conversation
            if settings.enable_living_agent:
                try:
                    from app.engine.living_agent.emotion_engine import get_emotion_engine
                    from app.engine.living_agent.models import LifeEvent, LifeEventType
                    get_emotion_engine().process_event(LifeEvent(
                        event_type=LifeEventType.USER_CONVERSATION,
                        description=chat_request.message[:200],
                        importance=0.5,
                    ))
                except Exception:
                    pass  # Non-blocking: never affect user chat

            # Final processing time log
            processing_time = time.time() - start_time
            logger.info("[STREAM-V3] Completed in %.3fs (full graph)", processing_time)

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error("[STREAM-V3] Error: %s\n%s", e, tb)
            yield format_sse("error", {
                "message": f"Internal processing error: {type(e).__name__}",
                "type": "internal_error"
            })
            # Sprint 189b: Always emit "done" so frontend exits streaming state
            yield format_sse("done", {"processing_time": time.time() - start_time})

    # Sprint 26: Wrap with keepalive heartbeat + client disconnect detection
    return StreamingResponse(
        _keepalive_generator(generate_events_v3(), request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

