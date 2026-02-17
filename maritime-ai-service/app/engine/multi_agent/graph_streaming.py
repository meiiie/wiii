"""
Multi-Agent Graph Streaming - Extracted from graph.py

Handles streaming execution of the multi-agent graph, yielding
progressive SSE events for real-time UI updates.

**Feature: v3-full-graph-streaming**

REFACTORED v3 (2026-02-09):
- Token-level streaming with asyncio.sleep delays for natural UX
- Real AI thinking content from agent nodes (not just status labels)
- Fixed direct node duplicate response
- Smaller chunk sizes for smoother streaming appearance

REFACTORED v4 (2026-02-12):
- Strict separation: status events (pipeline progress) vs thinking events (AI reasoning)
- Supervisor routing and grader scores are STATUS, not THINKING
- No truncation of real AI thinking content
- _extract_thinking_content() forwards raw thinking without summarization

Sprint 69:
- Event bus for intra-node streaming (thinking_delta from inside nodes)
- _EVENT_QUEUES registry keyed by request ID
- Concurrent graph + queue consumption for real-time events

Sprint 70: True Interleaved Thinking (Claude pattern)
- Concurrent merged-queue consumption: graph events + bus events in real-time
- Nodes push thinking_delta via .astream() during LLM inference
- Bus events yielded IMMEDIATELY (not only between node completions)
- Skip bulk thinking re-emission when bus already streamed deltas
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, Optional, AsyncGenerator

from app.core.config import settings
from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.graph import (
    get_multi_agent_graph_async,
    _build_domain_config,
)
from app.engine.agents import get_agent_registry

from app.engine.multi_agent.stream_utils import (
    StreamEvent,
    NODE_DESCRIPTIONS,
    create_status_event,
    create_thinking_event,
    create_thinking_start_event,
    create_thinking_end_event,
    create_thinking_delta_event,
    create_answer_event,
    create_sources_event,
    create_metadata_event,
    create_done_event,
    create_error_event,
    create_tool_call_event,
    create_tool_result_event,
    create_domain_notice_event,
)

logger = logging.getLogger(__name__)

# Token streaming config — simulate natural typing speed
TOKEN_CHUNK_SIZE = 40          # ~8-10 words per chunk (Sprint 103b: was 12)
TOKEN_DELAY_SEC = 0.008        # 8ms between chunks (Sprint 103b: was 18ms, ~125 tokens/sec)

# =============================================================================
# EVENT BUS — Intra-node streaming (Sprint 69)
# =============================================================================
# Module-level dict keyed by bus_id (UUID string) → asyncio.Queue.
# Nodes push events here; graph_streaming consumes them concurrently.
_EVENT_QUEUES: Dict[str, asyncio.Queue] = {}
_EVENT_QUEUE_CREATED: Dict[str, float] = {}  # Sprint 83: Track creation time for leak detection
_EVENT_QUEUE_MAX_AGE_SEC = 900  # 15 minutes — no request should take longer


def _get_event_queue(bus_id: str) -> Optional[asyncio.Queue]:
    """Get event queue by bus ID (called from inside nodes)."""
    return _EVENT_QUEUES.get(bus_id)


def _cleanup_stale_queues() -> int:
    """Sprint 83: Remove event queues older than MAX_AGE to prevent memory leak."""
    import time
    now = time.time()
    stale = [
        bid for bid, created in _EVENT_QUEUE_CREATED.items()
        if now - created > _EVENT_QUEUE_MAX_AGE_SEC
    ]
    for bid in stale:
        _EVENT_QUEUES.pop(bid, None)
        _EVENT_QUEUE_CREATED.pop(bid, None)
    if stale:
        logger.warning("[EVENT_BUS] Cleaned up %d stale queues", len(stale))
    return len(stale)


async def _convert_bus_event(event: dict) -> StreamEvent:
    """Convert an intra-node bus event dict to a StreamEvent."""
    etype = event.get("type", "status")
    node = event.get("node")

    if etype == "thinking_delta":
        return await create_thinking_delta_event(
            content=event.get("content", ""),
            node=node,
        )
    elif etype == "tool_call":
        tc = event.get("content", {})
        return await create_tool_call_event(
            tool_name=tc.get("name", ""),
            tool_args=tc.get("args", {}),
            tool_call_id=tc.get("id", ""),
            node=node,
        )
    elif etype == "tool_result":
        tc = event.get("content", {})
        return await create_tool_result_event(
            tool_name=tc.get("name", ""),
            result_summary=tc.get("result", ""),
            tool_call_id=tc.get("id", ""),
            node=node,
        )
    elif etype == "answer_delta":
        # Sprint 74: Answer tokens streamed in real-time from tutor final generation
        return await create_answer_event(event.get("content", ""))
    elif etype == "thinking_start":
        return await create_thinking_start_event(
            label=str(event.get("content", "")),
            node=node or "",
        )
    elif etype == "thinking_end":
        return await create_thinking_end_event(
            node=node or "",
        )
    else:
        return await create_status_event(
            str(event.get("content", "")),
            node=node,
        )

# Vietnamese labels for thinking block headers (Sprint 64)
_NODE_LABELS = {
    "guardian": "Kiểm tra an toàn",
    "supervisor": "Phân tích câu hỏi",
    "rag_agent": "Tra cứu tri thức",
    "tutor_agent": "Giảng dạy",
    "grader": "Kiểm tra chất lượng",
    "synthesizer": "Tổng hợp câu trả lời",
    "memory_agent": "Truy xuất bộ nhớ",
    "direct": "Trả lời trực tiếp",
}


def _is_likely_english(text: str) -> bool:
    """Detect if text is primarily English (lacks Vietnamese diacritics)."""
    if not text or len(text) < 30:
        return False
    vn_diacritics = set(
        "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợ"
        "ùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆ"
        "ÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ"
    )
    vn_count = sum(1 for c in text if c in vn_diacritics)
    return vn_count / max(len(text), 1) < 0.01


async def _ensure_vietnamese(text: str) -> str:
    """Translate English text to Vietnamese if needed. Universal catch for all nodes."""
    if not text or not _is_likely_english(text):
        return text
    try:
        from app.engine.llm_pool import get_llm_light
        from langchain_core.messages import HumanMessage, SystemMessage

        llm = get_llm_light()
        if not llm:
            return text

        messages = [
            SystemMessage(content=(
                "Dịch đoạn văn sau sang tiếng Việt tự nhiên, chính xác. "
                "Giữ nguyên thuật ngữ chuyên ngành hàng hải/giao thông bằng tiếng Anh "
                "nếu cần (ví dụ: COLREGs, SOLAS, starboard). "
                "CHỈ trả lời bản dịch tiếng Việt, KHÔNG thêm giải thích hay ghi chú. "
                "KHÔNG bao gồm quá trình suy nghĩ."
            )),
            HumanMessage(content=text),
        ]
        response = await llm.ainvoke(messages)

        from app.services.output_processor import extract_thinking_from_response
        translated, _ = extract_thinking_from_response(response.content)
        result = translated.strip()
        if result and len(result) > 20:
            logger.info("[STREAM] Translated answer to Vietnamese: %d→%d chars", len(text), len(result))
            return result
        return text
    except Exception as e:
        logger.warning("[STREAM] Translation failed, using original: %s", e)
        return text


async def _stream_answer_tokens(
    text: str,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Stream answer text in small token-like chunks with delays.

    Instead of dumping 150-char blocks instantly, this produces
    ~12-char chunks with 18ms delays — matching Claude/ChatGPT's
    visual streaming speed.
    """
    # Sprint 64: Ensure answer is in Vietnamese before streaming
    text = await _ensure_vietnamese(text)

    for i in range(0, len(text), TOKEN_CHUNK_SIZE):
        chunk = text[i : i + TOKEN_CHUNK_SIZE]
        yield await create_answer_event(chunk)
        await asyncio.sleep(TOKEN_DELAY_SEC)


def _extract_thinking_content(node_output: dict) -> str:
    """
    Extract raw AI thinking/reasoning content from a node's output.

    Returns the full thinking text without truncation — the frontend
    handles display (collapsible block with markdown rendering).

    Sources (in priority order):
    1. `thinking_content` — structured summary from <thinking> tags (Vietnamese)
    2. `thinking` field — from Gemini extended thinking (may be English)

    Does NOT use `agent_outputs` — those contain answer text (not reasoning).
    Prefers thinking_content because it follows prompt language instructions
    (Vietnamese), while Gemini's native thinking often defaults to English.
    """
    # 1. Structured thinking content (from <thinking> tags — follows prompt language)
    thinking_content = node_output.get("thinking_content", "")
    if thinking_content and len(thinking_content) > 20:
        return thinking_content

    # 2. Raw thinking (Gemini native extended thinking — may be English)
    thinking = node_output.get("thinking", "")
    if thinking and len(thinking) > 20:
        return thinking

    return ""


async def process_with_multi_agent_streaming(
    query: str,
    user_id: str,
    session_id: str = "",
    context: dict = None,
    domain_id: Optional[str] = None,
    thinking_effort: Optional[str] = None,
) -> AsyncGenerator[StreamEvent, None]:
    """
    Process with Multi-Agent graph with token-level streaming.

    v3 REFACTORED (2026-02-09):
    - Token-level answer streaming (12-char chunks with 18ms delays)
    - Real AI thinking content from nodes
    - Proper status → thinking → answer → sources → metadata flow

    Yields StreamEvents at each graph node:
    - Supervisor: routing decision (thinking event)
    - RAG/TutorAgent: tool calls + actual reasoning (thinking events)
    - GraderAgent: quality score (thinking event)
    - Synthesizer: token-streamed final_response (answer events)
    """
    # Sprint 121b: Ensure session_id is always a string (callers may pass UUID)
    session_id = str(session_id) if session_id else ""
    domain_id = domain_id or settings.default_domain
    start_time = time.time()
    graph = await get_multi_agent_graph_async()
    registry = get_agent_registry()

    # Start trace
    trace_id = registry.start_request_trace()
    logger.info("[MULTI_AGENT_STREAM] Started streaming trace: %s", trace_id)

    try:
        # Yield initial status
        yield await create_status_event("🚀 Bắt đầu xử lý câu hỏi...", None)

        # Build domain config for streaming
        domain_config = _build_domain_config(domain_id)

        # Sprint 69: Create event bus for intra-node streaming
        import time as _time
        bus_id = str(uuid.uuid4())
        event_queue: asyncio.Queue = asyncio.Queue()
        _EVENT_QUEUES[bus_id] = event_queue
        _EVENT_QUEUE_CREATED[bus_id] = _time.time()

        # Sprint 83: Periodically clean stale queues (leak prevention)
        _cleanup_stale_queues()

        # Create initial state
        initial_state: AgentState = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "context": context or {},
            "messages": [],
            "current_agent": "",
            "next_agent": "",
            "agent_outputs": {},
            "grader_score": 0.0,
            "grader_feedback": "",
            "final_response": "",
            "sources": [],
            "iteration": 0,
            "max_iterations": 3,
            "error": None,
            "domain_id": domain_id,
            "domain_config": domain_config,
            "thinking_effort": thinking_effort,
            "_event_bus_id": bus_id,
        }

        final_state = None
        answer_emitted = False
        partial_answer_emitted = False
        rag_answer_text = ""
        # Sprint 70: Track nodes that streamed via event bus (skip bulk re-emit)
        _bus_streamed_nodes: set = set()
        # Sprint 74: Track nodes that streamed answer_delta via bus
        _bus_answer_nodes: set = set()

        # Build config for thread persistence with per-user isolation (Sprint 16)
        invoke_config = {}
        # Sprint 121b: Defensive str() conversion at call site
        _sid = str(session_id) if session_id else ""
        _uid = str(user_id) if user_id else ""
        if _sid and _uid:
            from app.core.thread_utils import build_thread_id
            thread_id = build_thread_id(_uid, _sid)
            invoke_config = {"configurable": {"thread_id": thread_id}}
        elif _sid:
            invoke_config = {"configurable": {"thread_id": _sid}}

        # Timeout: max 5 min per graph node, 15 min total
        GRAPH_NODE_TIMEOUT = 300
        GRAPH_TOTAL_TIMEOUT = 900

        # Sprint 70: Concurrent merged-queue pattern for true interleaved streaming
        # Two event sources merged into one queue:
        #   1. Graph node completions ("graph", state_update)
        #   2. Intra-node bus events ("bus", event_dict)
        # This ensures thinking_delta tokens are yielded IMMEDIATELY
        # during LLM inference, not only between node completions.
        _SENTINEL = object()
        merged_queue: asyncio.Queue = asyncio.Queue()

        async def _forward_graph():
            """Forward graph node completions to merged queue."""
            try:
                async for update in graph.astream(
                    initial_state, config=invoke_config, stream_mode="updates"
                ):
                    await merged_queue.put(("graph", update))
            except asyncio.TimeoutError:
                await merged_queue.put(("error", "Processing timeout exceeded"))
            except Exception as e:
                logger.exception("[STREAM] Graph error: %s", e)
                await merged_queue.put(("error", f"Graph error: {type(e).__name__}: {e}"))
            finally:
                await merged_queue.put(("graph_done", None))

        async def _forward_bus():
            """Forward intra-node bus events to merged queue."""
            while True:
                try:
                    event = await event_queue.get()
                    if event is _SENTINEL:
                        break
                    # Sprint 70: Track which nodes streamed via bus
                    node = event.get("node")
                    etype = event.get("type")
                    if node and etype == "thinking_delta":
                        _bus_streamed_nodes.add(node)
                    # Sprint 74: Track answer_delta via bus
                    if node and etype == "answer_delta":
                        _bus_answer_nodes.add(node)
                    await merged_queue.put(("bus", event))
                except Exception:
                    break

        graph_task = asyncio.create_task(_forward_graph())
        bus_task = asyncio.create_task(_forward_bus())

        try:
          while True:
            elapsed = time.time() - start_time
            if elapsed > GRAPH_TOTAL_TIMEOUT:
                logger.warning(
                    "[STREAM] Total graph timeout exceeded (%ds)",
                    GRAPH_TOTAL_TIMEOUT,
                )
                yield await create_error_event("Processing timeout exceeded")
                break

            try:
                msg_type, payload = await asyncio.wait_for(
                    merged_queue.get(), timeout=GRAPH_NODE_TIMEOUT
                )
            except asyncio.TimeoutError:
                logger.warning("[STREAM] Merged queue timeout (%ds)", GRAPH_NODE_TIMEOUT)
                yield await create_error_event("Processing timeout exceeded")
                break

            if msg_type == "bus":
                yield await _convert_bus_event(payload)
                continue
            elif msg_type == "error":
                yield await create_error_event(str(payload))
                break
            elif msg_type == "graph_done":
                # Final drain of any remaining bus events
                while not merged_queue.empty():
                    try:
                        mt, pl = merged_queue.get_nowait()
                        if mt == "bus":
                            yield await _convert_bus_event(pl)
                    except Exception:
                        break
                break
            elif msg_type != "graph":
                continue

            state_update = payload
            for node_name, node_output in state_update.items():
                logger.debug("[STREAM] Node completed: %s", node_name)

                node_start = time.time()

                # ---- SUPERVISOR NODE ----
                if node_name == "supervisor":
                    next_agent = node_output.get("next_agent", "")
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("supervisor", "🎯 Phân tích câu hỏi"),
                        "supervisor",
                    )

                    # Thinking lifecycle: open → content → close
                    yield await create_thinking_start_event(
                        _NODE_LABELS.get("supervisor", "Phan tich cau hoi"),
                        "supervisor",
                    )

                    # Sprint 70: Skip bulk thinking if bus already streamed deltas
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "supervisor" not in _bus_streamed_nodes:
                        yield await create_thinking_event(
                            thinking_content,
                            "routing",
                        )

                    if next_agent:
                        # Routing is pipeline status, not AI reasoning
                        desc = NODE_DESCRIPTIONS.get(next_agent, next_agent)
                        yield await create_status_event(
                            f"→ {desc}",
                            "supervisor",
                        )

                    yield await create_thinking_end_event(
                        "supervisor",
                        duration_ms=int((time.time() - node_start) * 1000),
                    )

                # ---- RAG AGENT NODE ----
                elif node_name == "rag_agent":
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("rag_agent", "📚 Tra cứu tri thức"),
                        "rag_agent",
                    )

                    # Sprint 64 fix: Tool calls OUTSIDE thinking block
                    # Flow: status → tool_calls → thinking_block → partial_answer
                    # This creates the interleaved pattern:
                    #   supervisor thinking → tool_calls → rag thinking → answer
                    tool_call_events = node_output.get("tool_call_events", [])
                    if tool_call_events:
                        for tc_event in tool_call_events:
                            yield await create_tool_call_event(
                                tool_name=tc_event.get("name", ""),
                                tool_args=tc_event.get("args", {}),
                                tool_call_id=tc_event.get("id", ""),
                                node="rag_agent",
                            )
                            if "result" in tc_event:
                                result_str = str(
                                    tc_event.get("result", ""),
                                )[:200]
                                yield await create_tool_result_event(
                                    tool_name=tc_event.get("name", ""),
                                    result_summary=result_str,
                                    tool_call_id=tc_event.get("id", ""),
                                    node="rag_agent",
                                )

                    # Emit pipeline status for tools/sources (always visible)
                    tools_used = node_output.get("tools_used", [])
                    sources = node_output.get("sources", [])
                    if tools_used:
                        tool_names = [
                            t.get("name", "tool") if isinstance(t, dict) else str(t)
                            for t in tools_used
                        ]
                        yield await create_status_event(
                            f"📚 Đã tra cứu: {', '.join(tool_names)}",
                            "rag_agent",
                        )
                    if sources:
                        yield await create_status_event(
                            f"📄 Tìm thấy {len(sources)} nguồn tham khảo",
                            "rag_agent",
                        )

                    # Thinking lifecycle: open → content → close (AFTER tool calls)
                    # Sprint 70: Skip bulk thinking if bus already streamed deltas
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "rag_agent" not in _bus_streamed_nodes:
                        yield await create_thinking_start_event(
                            _NODE_LABELS.get("rag_agent", "Tra cứu tri thức"),
                            "rag_agent",
                        )
                        yield await create_thinking_event(
                            thinking_content,
                            "retrieval",
                        )
                        yield await create_thinking_end_event(
                            "rag_agent",
                            duration_ms=int((time.time() - node_start) * 1000),
                        )

                    # Sprint 64: RAG partial answer — emit answer early
                    # so user sees content before synthesizer runs
                    agent_output_text = node_output.get("final_response", "")
                    if not agent_output_text:
                        # Try agent_outputs for RAG response text
                        agent_outputs = node_output.get("agent_outputs", {})
                        if isinstance(agent_outputs, dict):
                            for val in agent_outputs.values():
                                if isinstance(val, str) and len(val) > 20:
                                    agent_output_text = val
                                    break
                    if agent_output_text and not answer_emitted:
                        rag_answer_text = agent_output_text
                        async for event in _stream_answer_tokens(agent_output_text):
                            yield event
                        partial_answer_emitted = True

                # ---- TUTOR AGENT NODE ----
                elif node_name == "tutor_agent":
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("tutor_agent", "👨‍🏫 Tạo bài giảng"),
                        "tutor_agent",
                    )

                    # Tool calls OUTSIDE thinking block (same pattern as RAG)
                    tool_call_events = node_output.get("tool_call_events", [])
                    if tool_call_events:
                        for tc_event in tool_call_events:
                            yield await create_tool_call_event(
                                tool_name=tc_event.get("name", ""),
                                tool_args=tc_event.get("args", {}),
                                tool_call_id=tc_event.get("id", ""),
                                node="tutor_agent",
                            )
                            if "result" in tc_event:
                                result_str = str(
                                    tc_event.get("result", ""),
                                )[:200]
                                yield await create_tool_result_event(
                                    tool_name=tc_event.get("name", ""),
                                    result_summary=result_str,
                                    tool_call_id=tc_event.get("id", ""),
                                    node="tutor_agent",
                                )

                    # Emit pipeline status for tools (always visible)
                    tools_used = node_output.get("tools_used", [])
                    if tools_used:
                        yield await create_status_event(
                            f"👨‍🏫 Đã phân tích từ {len(tools_used)} nguồn",
                            "tutor_agent",
                        )

                    # Thinking lifecycle: open → content → close (AFTER tool calls)
                    # Sprint 70: Skip bulk thinking if bus already streamed deltas
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "tutor_agent" not in _bus_streamed_nodes:
                        yield await create_thinking_start_event(
                            _NODE_LABELS.get("tutor_agent", "Giảng dạy"),
                            "tutor_agent",
                        )
                        yield await create_thinking_event(
                            thinking_content,
                            "analysis",
                        )
                        yield await create_thinking_end_event(
                            "tutor_agent",
                            duration_ms=int((time.time() - node_start) * 1000),
                        )

                    # Sprint 64: Tutor partial answer — emit response early
                    # (same pattern as RAG partial answer)
                    tutor_response = node_output.get("tutor_output", "")
                    if not tutor_response:
                        agent_outputs = node_output.get("agent_outputs", {})
                        if isinstance(agent_outputs, dict):
                            tutor_response = agent_outputs.get("tutor", "")
                    # Fallback: if response is empty but thinking has content,
                    # use thinking as answer (Gemini quirk: entire response in thinking)
                    if not tutor_response:
                        thinking_fallback = node_output.get("thinking", "")
                        if thinking_fallback and len(thinking_fallback) > 50:
                            logger.warning(
                                "[STREAM] Tutor response empty, recovering from "
                                "thinking field (%d chars)",
                                len(thinking_fallback),
                            )
                            tutor_response = thinking_fallback
                    if tutor_response and not answer_emitted:
                        # Sprint 74: Skip post-hoc answer emission if bus already streamed
                        _answer_via_bus = "tutor_agent" in _bus_answer_nodes
                        _answer_as_thinking = node_output.get("_answer_streamed_via_bus", False)
                        if not _answer_via_bus and not _answer_as_thinking:
                            async for event in _stream_answer_tokens(tutor_response):
                                yield event
                        partial_answer_emitted = True
                        answer_emitted = True
                        final_state = node_output

                # ---- GRADER NODE ----
                elif node_name == "grader":
                    # Sprint 74: Status only — no thinking_start/end (empty blocks look like glitch)
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("grader", "✅ Kiểm tra chất lượng"),
                        "grader",
                    )

                    score = node_output.get("grader_score", 0)
                    if score > 0:
                        status_icon = "✅" if score >= 6 else "⚠️"
                        yield await create_status_event(
                            f"{status_icon} Chất lượng: {score}/10",
                            "grader",
                        )

                # ---- SYNTHESIZER NODE (FINAL) ----
                elif node_name == "synthesizer":
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("synthesizer", "📝 Tổng hợp câu trả lời"),
                        "synthesizer",
                    )

                    # Token-stream the final response
                    final_response = node_output.get("final_response", "")
                    if final_response and not answer_emitted:
                        # Sprint 64: Skip re-emission if synthesizer output
                        # matches RAG partial answer (pass-through case)
                        if partial_answer_emitted and final_response == rag_answer_text:
                            logger.debug("[STREAM] Synthesizer pass-through, skipping re-emission")
                        else:
                            async for event in _stream_answer_tokens(final_response):
                                yield event
                        answer_emitted = True

                    final_state = node_output

                # ---- MEMORY NODE (Sprint 72: stream response) ----
                elif node_name == "memory_agent":
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("memory_agent", "🧠 Truy xuất bộ nhớ"),
                        "memory_agent",
                    )
                    yield await create_thinking_start_event(
                        _NODE_LABELS.get("memory_agent", "Truy xuat bo nho"),
                        "memory_agent",
                    )

                    # Sprint 72: Emit thinking content if available
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "memory_agent" not in _bus_streamed_nodes:
                        yield await create_thinking_event(
                            thinking_content,
                            "memory",
                        )

                    yield await create_thinking_end_event(
                        "memory_agent",
                        duration_ms=int((time.time() - node_start) * 1000),
                    )

                    # Sprint 72: Stream memory response as answer
                    memory_response = node_output.get("memory_output", "")
                    if not memory_response:
                        agent_outputs = node_output.get("agent_outputs", {})
                        if isinstance(agent_outputs, dict):
                            memory_response = agent_outputs.get("memory", "")
                    if memory_response and not answer_emitted:
                        async for event in _stream_answer_tokens(memory_response):
                            yield event
                        partial_answer_emitted = True
                        answer_emitted = True
                        final_state = node_output

                # ---- DIRECT NODE ----
                elif node_name == "direct":
                    # Thinking lifecycle: open
                    yield await create_thinking_start_event(
                        _NODE_LABELS.get("direct", "Tra loi truc tiep"),
                        "direct",
                    )

                    # Emit thinking from direct node (if LLM generated)
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content:
                        yield await create_thinking_event(
                            thinking_content,
                            "direct_response",
                        )

                    # Thinking lifecycle: close
                    yield await create_thinking_end_event(
                        "direct",
                        duration_ms=int((time.time() - node_start) * 1000),
                    )

                    # Direct response — token-stream it
                    final_response = node_output.get("final_response", "")
                    if final_response and not answer_emitted:
                        async for event in _stream_answer_tokens(final_response):
                            yield event
                        answer_emitted = True
                    final_state = node_output

                    # Sprint 80b: Emit domain notice if set by DIRECT node
                    domain_notice = node_output.get("domain_notice")
                    if domain_notice:
                        yield await create_domain_notice_event(domain_notice)

                # ---- GUARDIAN NODE ----
                elif node_name == "guardian":
                    # Sprint 74: Status only — no thinking_start/end (empty blocks look like glitch)
                    yield await create_status_event(
                        _NODE_LABELS.get("guardian", "Kiểm tra an toàn"),
                        "guardian",
                    )
                    logger.debug(
                        "[STREAM] Guardian passed: %s",
                        node_output.get("guardian_passed"),
                    )

          # Safety net: if no answer was emitted by any node, extract from final_state
          if not answer_emitted and final_state:
              fallback = final_state.get("final_response", "")
              if not fallback:
                  for val in final_state.get("agent_outputs", {}).values():
                      if isinstance(val, str) and len(val) > 20:
                          fallback = val
                          break
              if not fallback:
                  fallback = final_state.get("thinking", "")
              if fallback:
                  logger.warning(
                      "[STREAM] No answer emitted — using fallback (%d chars)",
                      len(fallback),
                  )
                  async for event in _stream_answer_tokens(fallback):
                      yield event
                  answer_emitted = True

          # Emit sources if available
          if final_state:
              sources = final_state.get("sources", [])
              if sources:
                  formatted_sources = []
                  for s in sources:
                      if isinstance(s, dict):
                          formatted_sources.append(
                              {
                                  "title": s.get("title", ""),
                                  "content": (
                                      s.get("content", "")[
                                          :MAX_CONTENT_SNIPPET_LENGTH
                                      ]
                                      if s.get("content") else ""
                                  ),
                                  "image_url": s.get("image_url"),
                                  "page_number": s.get("page_number"),
                                  "document_id": s.get("document_id"),
                              }
                          )
                  if formatted_sources:
                      yield await create_sources_event(formatted_sources)

              # Emit metadata with reasoning_trace
              reasoning_trace = final_state.get("reasoning_trace")
              reasoning_dict = None
              if reasoning_trace:
                  try:
                      reasoning_dict = reasoning_trace.model_dump()
                  except AttributeError:
                      try:
                          reasoning_dict = reasoning_trace.dict()
                      except Exception as e:
                          logger.warning("Failed to serialize reasoning trace: %s", e)
                          reasoning_dict = None

              processing_time = time.time() - start_time
              # Sprint 120: Include mood in metadata for desktop
              _mood_data = None
              try:
                  if settings.enable_emotional_state:
                      from app.engine.emotional_state import get_emotional_state_manager
                      _esm = get_emotional_state_manager()
                      _user_id = context.get("user_id", "")
                      if _user_id:
                          _es = _esm.get_state(_user_id)
                          _mood_data = {
                              "positivity": round(_es.positivity, 3),
                              "energy": round(_es.energy, 3),
                              "mood": _es.mood.value,
                          }
              except Exception:
                  pass

              yield await create_metadata_event(
                  reasoning_trace=reasoning_dict,
                  processing_time=processing_time,
                  confidence=final_state.get("grader_score", 0) / 10,
                  model=f"{settings.rag_model_version}-streaming",
                  doc_count=len(sources),
                  thinking=final_state.get("thinking"),
                  agent_type=final_state.get("next_agent", "rag_agent"),
                  mood=_mood_data,
                  # Sprint 121b: Include session_id so frontend can reuse it
                  session_id=final_state.get("session_id", session_id),
              )

          # Done signal
          total_time = time.time() - start_time
          yield await create_done_event(total_time)

          # End trace
          trace_summary = registry.end_request_trace(trace_id)
          logger.info(
              "[MULTI_AGENT_STREAM] Completed in %.2fs, %d spans",
              total_time, trace_summary.get('span_count', 0),
          )

        except Exception as e:
            logger.exception(f"[MULTI_AGENT_STREAM] Inner loop error: {e}")
            yield await create_error_event(f"Internal processing error: {type(e).__name__}")
        finally:
            # Sprint 70: Stop bus forwarder and clean up tasks
            try:
                event_queue.put_nowait(_SENTINEL)
            except Exception:
                pass
            for t in (graph_task, bus_task):
                if not t.done():
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass

    except Exception as e:
        logger.exception(f"[MULTI_AGENT_STREAM] Error: {e}")
        yield await create_error_event(f"Internal processing error: {type(e).__name__}")
        registry.end_request_trace(trace_id)
    finally:
        # Sprint 69: Clean up event bus
        _EVENT_QUEUES.pop(bus_id, None)
        _EVENT_QUEUE_CREATED.pop(bus_id, None)
