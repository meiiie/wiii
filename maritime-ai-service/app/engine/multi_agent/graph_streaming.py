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
import json
import logging
import re
import time
import uuid
from typing import Dict, Optional, AsyncGenerator

from app.core.config import settings
from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH, PREVIEW_MAX_PER_MESSAGE, PREVIEW_SNIPPET_MAX_LENGTH
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
    create_emotion_event,
    create_action_text_event,
    create_browser_screenshot_event,
    create_preview_event,
    create_artifact_event,
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
            summary=event.get("summary"),
        )
    elif etype == "thinking_end":
        return await create_thinking_end_event(
            node=node or "",
        )
    elif etype == "action_text":
        # Sprint 148: Bold narrative from tool_report_progress phase transitions
        return await create_action_text_event(
            content=str(event.get("content", "")),
            node=node,
        )
    elif etype == "browser_screenshot":
        # Sprint 153: Playwright screenshot for visual transparency
        _sc = event.get("content", {})
        return await create_browser_screenshot_event(
            url=str(_sc.get("url", "")),
            image_base64=str(_sc.get("image", "")),
            label=str(_sc.get("label", "")),
            node=node,
        )
    elif etype == "preview":
        # Sprint 166: Rich preview card
        _pv = event.get("content", {})
        return await create_preview_event(
            preview_type=str(_pv.get("preview_type", "document")),
            preview_id=str(_pv.get("preview_id", "")),
            title=str(_pv.get("title", "")),
            snippet=str(_pv.get("snippet", "")),
            url=_pv.get("url"),
            image_url=_pv.get("image_url"),
            citation_index=_pv.get("citation_index"),
            node=node,
            metadata=_pv.get("metadata"),
        )
    elif etype == "artifact":
        # Sprint 167: Interactive artifact (code, HTML, data)
        _af = event.get("content", {})
        return await create_artifact_event(
            artifact_type=str(_af.get("artifact_type", "code")),
            artifact_id=str(_af.get("artifact_id", "")),
            title=str(_af.get("title", "")),
            content=str(_af.get("content", "")),
            language=str(_af.get("language", "")),
            node=node,
            metadata=_af.get("metadata"),
        )
    else:
        return await create_status_event(
            str(event.get("content", "")),
            node=node,
            details=event.get("details"),
        )

# Vietnamese labels for thinking block headers (Sprint 64)
_NODE_LABELS = {
    "guardian": "Kiểm tra an toàn",
    "supervisor": "Phân tích câu hỏi",
    "rag_agent": "Tra cứu tri thức",
    "tutor_agent": "Soạn bài giảng",
    "grader": "Kiểm tra chất lượng",
    "synthesizer": "Tổng hợp câu trả lời",
    "memory_agent": "Truy xuất bộ nhớ",
    "direct": "Suy nghĩ câu trả lời",
    "product_search_agent": "Tìm kiếm sản phẩm",
    "colleague_agent": "Hỏi ý kiến Bro",
    "parallel_dispatch": "Triển khai song song",
    "aggregator": "Tổng hợp báo cáo",
    # Sprint 164: Per-worker subagent labels (short names from parallel_dispatch)
    "rag": "Tra cứu tri thức",
    "tutor": "Soạn bài giảng",
    "search": "Tìm kiếm sản phẩm",
}

# Sprint 147: Bold narrative text emitted after Supervisor routing
# Provides Claude-like contextual narrative between thinking blocks
_INTENT_ACTION_TEXT = {
    "lookup": "Wiii sẽ tìm kiếm tài liệu liên quan trong cơ sở tri thức...",
    "learning": "Để giải thích rõ ràng, Wiii sẽ tra cứu kiến thức chuyên ngành và soạn bài giảng...",
    "web_search": "Wiii cần tìm thông tin mới nhất trên web để trả lời chính xác...",
    "personal": "Wiii nhớ lại những gì biết về bạn...",
    "social": "Wiii sẽ trò chuyện cùng bạn...",
    "off_topic": "Wiii sẽ suy nghĩ và trả lời câu hỏi chung...",
    "product_search": "Wiii sẽ tìm kiếm sản phẩm trên nhiều sàn thương mại điện tử...",
}

def _generate_thinking_summary(node_output: dict, query: str) -> str:
    """Generate Claude-style one-line summary for the thinking block header.

    Sprint 145: Creates a concise Vietnamese summary from the routing decision,
    used as the collapsed header text in the Claude-like thinking UI.
    """
    intent = ""
    if isinstance(node_output.get("routing_metadata"), dict):
        intent = node_output["routing_metadata"].get("intent", "")
    next_agent = node_output.get("next_agent", "")

    _summaries = {
        "lookup": f"Tra cứu kiến thức về: {query[:50]}",
        "learning": f"Phân tích và giảng dạy: {query[:50]}",
        "social": "Trò chuyện cùng người dùng",
        "personal": "Truy xuất bộ nhớ cá nhân",
        "web_search": f"Tìm kiếm web: {query[:50]}",
        "off_topic": f"Trả lời câu hỏi chung: {query[:50]}",
        "product_search": f"Tìm kiếm sản phẩm: {query[:50]}",
    }

    if intent and intent in _summaries:
        return _summaries[intent]

    # Fallback based on next_agent
    _agent_summaries = {
        "rag_agent": f"Tra cứu kiến thức: {query[:50]}",
        "tutor_agent": f"Soạn bài giảng: {query[:50]}",
        "memory_agent": "Truy xuất bộ nhớ cá nhân",
        "direct": f"Suy nghĩ câu trả lời: {query[:50]}",
        "product_search_agent": f"Tìm kiếm sản phẩm: {query[:50]}",
    }
    if next_agent and next_agent in _agent_summaries:
        return _agent_summaries[next_agent]

    return f"Phân tích câu hỏi: {query[:60]}"


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


async def _extract_and_stream_emotion_then_answer(
    text: str,
    soul_emitted: bool,
) -> AsyncGenerator[StreamEvent, None]:
    """Sprint 135: Extract soul emotion from full-text answer, yield emotion + answer events."""
    if not soul_emitted and settings.enable_soul_emotion:
        from app.engine.soul_emotion import extract_soul_emotion
        result = extract_soul_emotion(text)
        if result.emotion:
            yield await create_emotion_event(
                mood=result.emotion.mood,
                face=result.emotion.face,
                intensity=result.emotion.intensity,
            )
        text = result.clean_text

    async for event in _stream_answer_tokens(text):
        yield event


def _is_pipeline_summary(text: str) -> bool:
    """Check if text is a ReasoningTracer pipeline dump, not actual AI reasoning.

    Sprint 140b defense-in-depth: After the root cause fix in corrective_rag.py
    (pipeline steps no longer assigned to ``thinking`` field), this filter
    catches any remaining edge cases where ``build_thinking_summary()`` output
    leaks through.

    Detects the canonical ``**Quá trình suy nghĩ:**`` / ``Quá trình suy nghĩ``
    header from ``ReasoningTracer.build_thinking_summary()``.

    NOTE: ``[RAG Analysis]`` prefix is NOT filtered here — after the root fix,
    combined ``[RAG Analysis]\\n{genuine_thinking}`` is valid content from
    tutor_node when native Gemini reasoning IS available.
    """
    prefix = text[:300]
    if "Quá trình suy nghĩ" in prefix:
        return True
    return False


def _extract_thinking_content(node_output: dict) -> str:
    """
    Extract actual AI reasoning for the thinking display block.

    Sprint 140b: Follows Claude Code pattern — thinking = model reasoning,
    status = pipeline progress.  Pipeline step summaries from ReasoningTracer
    are filtered out; those belong in status events / StreamingIndicator.

    Priority:
    1. ``thinking`` — native model reasoning (Gemini extended thinking,
       Claude thinking, Qwen <think> blocks).  May be English.
    2. ``thinking_content`` — from <thinking> tags in agent prompts.
       Only used if it's NOT a pipeline summary.

    Returns empty string when no genuine AI reasoning is available,
    which correctly results in no thinking block being created.
    """
    # 1. Native AI reasoning (preferred — actual model thought process)
    thinking = node_output.get("thinking", "")
    if thinking and len(thinking) > 20:
        if not _is_pipeline_summary(thinking):
            return thinking

    # 2. Structured thinking from <thinking> tags (fallback)
    #    Skip if it's a ReasoningTracer pipeline dump
    thinking_content = node_output.get("thinking_content", "")
    if thinking_content and len(thinking_content) > 20:
        if not _is_pipeline_summary(thinking_content):
            return thinking_content

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

    # Sprint 153: Initialize before outer try to prevent NameError in finally
    bus_id = None

    try:
        # Yield initial status
        yield await create_status_event("🚀 Bắt đầu xử lý câu hỏi...", None)

        # Build domain config for streaming
        domain_config = _build_domain_config(domain_id)

        # Sprint 69: Create event bus for intra-node streaming
        bus_id = str(uuid.uuid4())
        event_queue: asyncio.Queue = asyncio.Queue()
        _EVENT_QUEUES[bus_id] = event_queue
        _EVENT_QUEUE_CREATED[bus_id] = time.time()

        # Sprint 83: Periodically clean stale queues (leak prevention)
        _cleanup_stale_queues()

        # Sprint 189b: Deserialize langchain messages from context (was hardcoded [])
        # Same logic as sync path in graph.py:1611-1620
        langchain_messages = (context or {}).get("langchain_messages", [])
        serialized_messages = []
        for m in langchain_messages:
            if isinstance(m, dict):
                serialized_messages.append(m)
            else:
                serialized_messages.append({
                    "role": getattr(m, "type", "human"),
                    "content": m.content,
                })

        # Create initial state
        initial_state: AgentState = {
            "query": query,
            "user_id": user_id,
            "session_id": session_id,
            "context": context or {},
            "messages": serialized_messages,
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
            "routing_metadata": None,  # Sprint 189b-R5: parity with sync (graph.py:1643)
            "organization_id": (context or {}).get("organization_id"),  # Sprint 170c
            "_event_bus_id": bus_id,
        }

        # Sprint 222: Graph-level host context injection (sync/stream parity)
        from app.engine.multi_agent.graph import _inject_host_context
        _host_prompt = _inject_host_context(initial_state)
        if _host_prompt:
            initial_state["host_context_prompt"] = _host_prompt

        final_state = None
        answer_emitted = False
        partial_answer_emitted = False
        rag_answer_text = ""
        # Sprint 70: Track nodes that streamed via event bus (skip bulk re-emit)
        _bus_streamed_nodes: set = set()
        # Sprint 74: Track nodes that streamed answer_delta via bus
        _bus_answer_nodes: set = set()

        # Sprint 166: Preview dedup — track emitted preview IDs per request
        _emitted_preview_ids: set = set()
        # Sprint 166: Preview settings from context (ChatRequest)
        _preview_enabled = settings.enable_preview
        _preview_types: set | None = None
        _preview_max = PREVIEW_MAX_PER_MESSAGE
        if context:
            if context.get("show_previews") is False:
                _preview_enabled = False
            if context.get("preview_types"):
                _preview_types = set(context["preview_types"])
            if context.get("preview_max_count"):
                _preview_max = int(context["preview_max_count"])

        # Sprint 135: Soul emotion buffer — intercepts first ~512 bytes of answer
        _soul_buffer = None
        _soul_emotion_emitted = False
        if settings.enable_soul_emotion:
            from app.engine.soul_emotion_buffer import SoulEmotionBuffer
            _soul_buffer = SoulEmotionBuffer(
                max_bytes=settings.soul_emotion_buffer_bytes,
            )

        # Build config for thread persistence with per-user isolation (Sprint 16)
        # Sprint 170c: Include org_id for cross-org thread isolation
        invoke_config = {}
        # Sprint 121b: Defensive str() conversion at call site
        _sid = str(session_id) if session_id else ""
        _uid = str(user_id) if user_id else ""
        _org_id = (context or {}).get("organization_id")
        if _sid and _uid:
            from app.core.thread_utils import build_thread_id
            thread_id = build_thread_id(_uid, _sid, org_id=_org_id)
            invoke_config = {"configurable": {"thread_id": thread_id}}
        elif _sid:
            invoke_config = {"configurable": {"thread_id": _sid}}

        # Sprint 144b: Attach LangSmith per-request callback for dashboard tracing
        from app.core.langsmith import get_langsmith_callback, is_langsmith_enabled
        if is_langsmith_enabled():
            ls_cb = get_langsmith_callback(_uid, _sid, domain_id)
            if ls_cb:
                invoke_config.setdefault("callbacks", []).append(ls_cb)

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
                await merged_queue.put(("error", "Graph processing error"))
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
                    # Sprint 144: Also track thinking_start (progressive RAG events)
                    node = event.get("node")
                    etype = event.get("type")
                    if node and etype in ("thinking_delta", "thinking_start"):
                        _bus_streamed_nodes.add(node)
                    # Sprint 74: Track answer_delta via bus
                    if node and etype == "answer_delta":
                        _bus_answer_nodes.add(node)
                    await merged_queue.put(("bus", event))
                except Exception as _bus_err:
                    logger.warning("[STREAM] Bus forwarding stopped: %s", _bus_err)
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
                # Sprint 135: Intercept answer_delta for soul emotion extraction
                if (
                    settings.enable_soul_emotion
                    and _soul_buffer is not None
                    and not _soul_buffer.is_done
                    and payload.get("type") == "answer_delta"
                ):
                    chunk = payload.get("content", "")
                    try:
                        emotion, clean_chunks = _soul_buffer.feed(chunk)
                    except Exception as _buf_err:
                        logger.warning("[SOUL] Buffer feed failed: %s, passing through", _buf_err)
                        emotion, clean_chunks = None, [chunk] if chunk else []
                    if emotion and not _soul_emotion_emitted:
                        yield await create_emotion_event(
                            mood=emotion.mood,
                            face=emotion.face,
                            intensity=emotion.intensity,
                        )
                        _soul_emotion_emitted = True  # set AFTER successful yield
                    for cc in clean_chunks:
                        if cc:
                            yield await create_answer_event(cc)
                    continue
                # Sprint 135: Flush buffer on non-answer event
                if (
                    settings.enable_soul_emotion
                    and _soul_buffer is not None
                    and not _soul_buffer.is_done
                ):
                    try:
                        emotion, clean_chunks = _soul_buffer.flush()
                    except Exception as _buf_err:
                        logger.warning("[SOUL] Buffer flush failed: %s", _buf_err)
                        emotion, clean_chunks = None, []
                    if emotion and not _soul_emotion_emitted:
                        yield await create_emotion_event(
                            mood=emotion.mood,
                            face=emotion.face,
                            intensity=emotion.intensity,
                        )
                        _soul_emotion_emitted = True  # set AFTER successful yield
                    for cc in clean_chunks:
                        if cc:
                            yield await create_answer_event(cc)

                yield await _convert_bus_event(payload)
                continue
            elif msg_type == "error":
                yield await create_error_event(str(payload))
                break
            elif msg_type == "graph_done":
                # Final drain of any remaining bus events in merged_queue
                while not merged_queue.empty():
                    try:
                        mt, pl = merged_queue.get_nowait()
                        if mt == "bus":
                            if pl.get("type") == "answer_delta":
                                answer_emitted = True
                            yield await _convert_bus_event(pl)
                    except Exception as _drain_err:
                        logger.debug("[STREAM] Merged queue drain stopped: %s", _drain_err)
                        break
                # Sprint 150 fix: Also drain event_queue directly.
                # _forward_bus may not have forwarded all events before
                # graph_done arrived (race condition — answer_delta events
                # pushed synchronously via put_nowait just before node returns
                # have minimal time for _forward_bus to process them).
                while not event_queue.empty():
                    try:
                        evt = event_queue.get_nowait()
                        if evt is _SENTINEL:
                            continue
                        if evt.get("type") == "answer_delta":
                            answer_emitted = True
                        yield await _convert_bus_event(evt)
                    except Exception as _drain_err:
                        logger.debug("[STREAM] Event queue drain stopped: %s", _drain_err)
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

                    # Sprint 145: Generate summary for Claude-like collapsed header
                    _summary = _generate_thinking_summary(node_output, query)

                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("supervisor", "🎯 Phân tích câu hỏi"),
                        "supervisor",
                    )

                    # Thinking lifecycle: open → content → close
                    yield await create_thinking_start_event(
                        _NODE_LABELS.get("supervisor", "Phan tich cau hoi"),
                        "supervisor",
                        summary=_summary,
                    )

                    # Sprint 145: Prioritize native thinking first, then structured metadata
                    _routing_parts = []

                    # 1. Native LLM thinking (preferred — actual model reasoning)
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "supervisor" not in _bus_streamed_nodes:
                        _routing_parts.append(thinking_content)

                    # 2. Structured routing metadata (append below native thinking)
                    _routing_meta = node_output.get("routing_metadata", {})
                    if isinstance(_routing_meta, dict):
                        _intent = _routing_meta.get("intent", "")
                        _confidence = _routing_meta.get("confidence", 0)
                        _reasoning = _routing_meta.get("reasoning", "")
                        _method = _routing_meta.get("method", "")

                        _intent_labels = {
                            "lookup": "Tra cứu kiến thức",
                            "learning": "Học tập/Giải thích",
                            "personal": "Cá nhân/Bộ nhớ",
                            "social": "Giao tiếp xã hội",
                            "off_topic": "Ngoài chuyên ngành",
                            "web_search": "Tìm kiếm web",
                        }
                        if _intent:
                            _routing_parts.append(
                                f"Ý định: {_intent_labels.get(_intent, _intent)}"
                            )
                        if _reasoning and _reasoning not in ("rule-based (no LLM)",):
                            _routing_parts.append(f"Phân tích: {_reasoning}")
                        if _confidence:
                            _routing_parts.append(
                                f"Độ tin cậy: {_confidence:.0%}"
                            )
                        if _method and _method != "structured":
                            _routing_parts.append(f"Phương pháp: {_method}")

                    # 3. Routing destination
                    if next_agent:
                        route_label = _NODE_LABELS.get(next_agent, next_agent)
                        _routing_parts.append(f"→ Chuyển đến: {route_label}")

                    # Emit combined thinking
                    if _routing_parts:
                        yield await create_thinking_delta_event(
                            "\n".join(_routing_parts),
                            "supervisor",
                        )

                    # Also emit status for pipeline indicator
                    if next_agent:
                        desc = NODE_DESCRIPTIONS.get(next_agent, next_agent)
                        yield await create_status_event(
                            f"→ {desc}",
                            "supervisor",
                        )

                    yield await create_thinking_end_event(
                        "supervisor",
                        duration_ms=int((time.time() - node_start) * 1000),
                    )

                    # Sprint 147: Emit bold action text after supervisor routing
                    _routing_meta = node_output.get("routing_metadata", {})
                    _intent = _routing_meta.get("intent", "") if isinstance(_routing_meta, dict) else ""
                    _action_text = _INTENT_ACTION_TEXT.get(_intent)
                    if _action_text:
                        yield await create_action_text_event(
                            _action_text,
                            "supervisor",
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

                    # Sprint 166: Emit document preview cards for RAG sources
                    if _preview_enabled and sources and (not _preview_types or "document" in _preview_types):
                        for idx, src in enumerate(sources[:_preview_max]):
                            _pid = f"doc-{src.get('node_id', src.get('document_id', idx))}"
                            if _pid in _emitted_preview_ids:
                                continue
                            _emitted_preview_ids.add(_pid)
                            yield await create_preview_event(
                                preview_type="document",
                                preview_id=_pid,
                                title=src.get("title", "Nguồn tham khảo"),
                                snippet=str(src.get("content", ""))[:PREVIEW_SNIPPET_MAX_LENGTH],
                                url=None,
                                image_url=src.get("image_url"),
                                citation_index=idx + 1,
                                node="rag_agent",
                                metadata={
                                    "relevance_score": src.get("score"),
                                    "page_number": src.get("page_number"),
                                },
                            )

                    # Thinking lifecycle: open → content → close (AFTER tool calls)
                    # Sprint 70: Skip bulk thinking if bus already streamed deltas
                    # Sprint 141b: Use thinking_delta (not thinking) so content appears in streamingBlocks
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "rag_agent" not in _bus_streamed_nodes:
                        yield await create_thinking_start_event(
                            _NODE_LABELS.get("rag_agent", "Tra cứu tri thức"),
                            "rag_agent",
                        )
                        yield await create_thinking_delta_event(
                            thinking_content,
                            "rag_agent",
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
                        # Sprint 144: Skip post-hoc answer if bus already streamed tokens
                        if "rag_agent" not in _bus_answer_nodes:
                            rag_answer_text = agent_output_text
                            async for event in _extract_and_stream_emotion_then_answer(
                                agent_output_text, _soul_emotion_emitted,
                            ):
                                if event.type == "emotion":
                                    _soul_emotion_emitted = True
                                yield event
                        else:
                            rag_answer_text = agent_output_text
                            logger.debug("[STREAM] RAG answer already streamed via bus, skipping bulk emission")
                        partial_answer_emitted = True
                    # Sprint 153: Set final_state for RAG (matches tutor/direct/product_search)
                    final_state = node_output

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
                    # Sprint 141b: Use thinking_delta (not thinking) so content appears in streamingBlocks
                    # Sprint 144: Also check _answer_streamed_via_bus flag — reliable
                    #   because _bus_streamed_nodes has a race condition (graph event
                    #   can arrive in merged_queue before all bus events are forwarded)
                    thinking_content = _extract_thinking_content(node_output)
                    _tutor_already_streamed = (
                        "tutor_agent" in _bus_streamed_nodes
                        or node_output.get("_answer_streamed_via_bus", False)
                    )
                    if thinking_content and not _tutor_already_streamed:
                        yield await create_thinking_start_event(
                            _NODE_LABELS.get("tutor_agent", "Giảng dạy"),
                            "tutor_agent",
                        )
                        yield await create_thinking_delta_event(
                            thinking_content,
                            "tutor_agent",
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
                    # Sprint 140b: Skip pipeline dumps — those are debug info
                    if not tutor_response:
                        thinking_fallback = node_output.get("thinking", "")
                        if (thinking_fallback and len(thinking_fallback) > 50
                                and not _is_pipeline_summary(thinking_fallback)):
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
                            async for event in _extract_and_stream_emotion_then_answer(
                                tutor_response, _soul_emotion_emitted,
                            ):
                                if event.type == "emotion":
                                    _soul_emotion_emitted = True
                                yield event
                            answer_emitted = True
                        elif _answer_via_bus:
                            # Bus confirmed answer delivery — safe to mark emitted
                            answer_emitted = True
                        # else: _answer_as_thinking=True but bus not confirmed yet.
                        # Don't set answer_emitted — let safety net catch lost events.
                        partial_answer_emitted = True
                        final_state = node_output

                # ---- GRADER NODE ----
                # Sprint 145: Demoted to status-only (quality check feedback, not deep thinking)
                elif node_name == "grader":
                    score = node_output.get("grader_score", 0)
                    feedback = node_output.get("grader_feedback", "")

                    if score > 0:
                        status_icon = "✅" if score >= 6 else "⚠️"
                        _status_msg = f"{status_icon} Chất lượng: {score:.1f}/10"
                        if feedback and len(feedback) > 10:
                            _status_msg += f" — {feedback[:80]}"
                        yield await create_status_event(_status_msg, "grader")
                    else:
                        yield await create_status_event(
                            "✅ Đánh giá chất lượng câu trả lời...",
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
                            async for event in _extract_and_stream_emotion_then_answer(
                                final_response, _soul_emotion_emitted,
                            ):
                                if event.type == "emotion":
                                    _soul_emotion_emitted = True
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
                    # Sprint 141b: Use thinking_delta (not thinking) so content appears in streamingBlocks
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "memory_agent" not in _bus_streamed_nodes:
                        yield await create_thinking_delta_event(
                            thinking_content,
                            "memory_agent",
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
                        async for event in _extract_and_stream_emotion_then_answer(
                            memory_response, _soul_emotion_emitted,
                        ):
                            if event.type == "emotion":
                                _soul_emotion_emitted = True
                            yield event
                        partial_answer_emitted = True
                        answer_emitted = True
                        final_state = node_output

                # ---- DIRECT NODE ----
                elif node_name == "direct":
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("direct", "💬 Wiii đang suy nghĩ câu trả lời..."),
                        "direct",
                    )

                    # Thinking lifecycle: open
                    yield await create_thinking_start_event(
                        _NODE_LABELS.get("direct", "Trả lời trực tiếp"),
                        "direct",
                    )

                    # Sprint 145: Prioritize native thinking FIRST, then fallback
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "direct" not in _bus_streamed_nodes:
                        yield await create_thinking_delta_event(
                            thinking_content,
                            "direct",
                        )
                    elif "direct" not in _bus_streamed_nodes:
                        # No native thinking — provide context from tools_used
                        _tools_used = node_output.get("tools_used", [])
                        if _tools_used:
                            _direct_parts = [f"Đã sử dụng {len(_tools_used)} công cụ:"]
                            for _t in _tools_used[:5]:
                                _tname = _t if isinstance(_t, str) else str(_t)
                                _direct_parts.append(f"  • {_tname}")
                            yield await create_thinking_delta_event(
                                "\n".join(_direct_parts),
                                "direct",
                            )
                        else:
                            yield await create_thinking_delta_event(
                                "Trả lời trực tiếp từ kiến thức chung của LLM",
                                "direct",
                            )

                    # Thinking lifecycle: close
                    yield await create_thinking_end_event(
                        "direct",
                        duration_ms=int((time.time() - node_start) * 1000),
                    )

                    # Sprint 166: Emit web preview cards from direct node tool results
                    _direct_tc_events = node_output.get("tool_call_events", [])
                    if _preview_enabled and (not _preview_types or "web" in _preview_types):
                        _web_count = 0
                        for tc in _direct_tc_events:
                            _tcname = tc.get("name", "")
                            if "search" not in _tcname and "web" not in _tcname and "news" not in _tcname:
                                continue
                            if tc.get("type") != "result" or _web_count >= _preview_max:
                                continue
                            _raw = tc.get("result", "")
                            try:
                                # Try JSON first (product search, structured results)
                                _results = []
                                try:
                                    _parsed = json.loads(_raw) if isinstance(_raw, str) else _raw
                                    if isinstance(_parsed, dict):
                                        _results = _parsed.get("results", _parsed.get("organic", []))
                                    elif isinstance(_parsed, list):
                                        _results = _parsed
                                except (ValueError, TypeError):
                                    pass

                                if _results:
                                    # JSON path — structured results
                                    for _wi, _wr in enumerate(_results[:8]):
                                        if not isinstance(_wr, dict):
                                            continue
                                        _wurl = _wr.get("url") or _wr.get("link", "")
                                        _pid = f"web-{_wi}-{hash(_wurl) % 10000}"
                                        if _pid in _emitted_preview_ids:
                                            continue
                                        _emitted_preview_ids.add(_pid)
                                        _web_count += 1
                                        yield await create_preview_event(
                                            preview_type="web",
                                            preview_id=_pid,
                                            title=str(_wr.get("title", ""))[:120],
                                            snippet=str(_wr.get("snippet", _wr.get("description", "")))[:300],
                                            url=_wurl or None,
                                            node="direct",
                                            metadata={
                                                "date": _wr.get("date"),
                                                "source": _wr.get("source"),
                                            },
                                        )
                                else:
                                    # Text path — parse markdown-formatted results
                                    # Format: **Title** (date) [source]\nbody\nURL: href\n---\n
                                    _blocks = re.split(r'\n---\n', str(_raw))
                                    for _bi, _block in enumerate(_blocks[:8]):
                                        _block = _block.strip()
                                        if not _block:
                                            continue
                                        # Extract title: **Title** or first line
                                        _tmatch = re.match(r'\*\*(.+?)\*\*', _block)
                                        _title = _tmatch.group(1) if _tmatch else _block.split('\n')[0][:120]
                                        # Extract URL
                                        _umatch = re.search(r'URL:\s*(https?://\S+)', _block)
                                        _wurl = _umatch.group(1) if _umatch else ""
                                        # Extract date
                                        _dmatch = re.search(r'\((\d{4}-\d{2}-\d{2}[^)]*)\)', _block)
                                        _date = _dmatch.group(1) if _dmatch else None
                                        # Extract source [Source]
                                        _smatch = re.search(r'\[([^\]]+)\]', _block)
                                        _source = _smatch.group(1) if _smatch else None
                                        # Extract body (lines after title, before URL)
                                        _lines = _block.split('\n')
                                        _body_lines = [l for l in _lines[1:] if not l.startswith('URL:')]
                                        _snippet = ' '.join(_body_lines).strip()[:300]

                                        _pid = f"web-{_bi}-{hash(_wurl or _title) % 10000}"
                                        if _pid in _emitted_preview_ids:
                                            continue
                                        _emitted_preview_ids.add(_pid)
                                        _web_count += 1
                                        yield await create_preview_event(
                                            preview_type="web",
                                            preview_id=_pid,
                                            title=_title[:120],
                                            snippet=_snippet,
                                            url=_wurl or None,
                                            node="direct",
                                            metadata={
                                                "date": _date,
                                                "source": _source,
                                            },
                                        )
                                        if _web_count >= _preview_max:
                                            break
                            except Exception as _pv_err:
                                logger.debug("[STREAM] Web preview parse failed: %s", _pv_err)
                                continue

                    # Direct response — token-stream it
                    final_response = node_output.get("final_response", "")
                    if final_response and not answer_emitted:
                        # Sprint 153: Match tutor pattern — check bus before post-hoc emission
                        _answer_via_bus = "direct" in _bus_answer_nodes
                        _answer_as_thinking = node_output.get("_answer_streamed_via_bus", False)
                        if not _answer_via_bus and not _answer_as_thinking:
                            async for event in _extract_and_stream_emotion_then_answer(
                                final_response, _soul_emotion_emitted,
                            ):
                                if event.type == "emotion":
                                    _soul_emotion_emitted = True
                                yield event
                            answer_emitted = True
                        elif _answer_via_bus:
                            answer_emitted = True
                    final_state = node_output

                    # Sprint 80b: Emit domain notice if set by DIRECT node
                    domain_notice = node_output.get("domain_notice")
                    if domain_notice:
                        yield await create_domain_notice_event(domain_notice)

                # ---- PRODUCT SEARCH NODE (Sprint 148) ----
                elif node_name == "product_search_agent":
                    yield await create_status_event(
                        NODE_DESCRIPTIONS.get("product_search_agent", "🛒 Wiii đang tìm kiếm sản phẩm..."),
                        "product_search_agent",
                    )

                    # Thinking lifecycle: open
                    yield await create_thinking_start_event(
                        _NODE_LABELS.get("product_search_agent", "Tìm kiếm sản phẩm"),
                        "product_search_agent",
                    )

                    # Emit native thinking if not already streamed via bus
                    thinking_content = _extract_thinking_content(node_output)
                    if thinking_content and "product_search_agent" not in _bus_streamed_nodes:
                        yield await create_thinking_delta_event(
                            thinking_content,
                            "product_search_agent",
                        )
                    elif "product_search_agent" not in _bus_streamed_nodes:
                        _tools_used = node_output.get("tools_used", [])
                        if _tools_used:
                            _parts = [f"Đã tìm trên {len(_tools_used)} nền tảng:"]
                            for _t in _tools_used[:6]:
                                _tname = _t.get("name", "") if isinstance(_t, dict) else str(_t)
                                _parts.append(f"  • {_tname}")
                            yield await create_thinking_delta_event(
                                "\n".join(_parts),
                                "product_search_agent",
                            )

                    # Thinking lifecycle: close
                    yield await create_thinking_end_event(
                        "product_search_agent",
                        duration_ms=int((time.time() - node_start) * 1000),
                    )

                    # Sprint 166→200: Emit product preview cards from tool_call_events
                    # Sprint 200: Skip post-hoc emission if real-time emission is active
                    # (product_search_node.py emits previews via event bus during ReAct loop)
                    _realtime_preview = False
                    try:
                        from app.core.config import get_settings as _gs200
                        _realtime_preview = _gs200().enable_product_preview_cards
                    except Exception:
                        pass

                    if _preview_enabled and not _realtime_preview and (not _preview_types or "product" in _preview_types):
                        _product_count = 0
                        for tc in node_output.get("tool_call_events", []):
                            if tc.get("type") != "result" or _product_count >= _preview_max:
                                continue
                            _raw = tc.get("result", "")
                            try:
                                _parsed = json.loads(_raw) if isinstance(_raw, str) else _raw
                                if not isinstance(_parsed, dict):
                                    continue
                                _platform = _parsed.get("platform", "")
                                for _pi, _prod in enumerate(_parsed.get("results", [])[:10]):
                                    if not isinstance(_prod, dict):
                                        continue
                                    _pid = f"prod-{_platform}-{_pi}"
                                    if _pid in _emitted_preview_ids:
                                        continue
                                    _emitted_preview_ids.add(_pid)
                                    _product_count += 1
                                    yield await create_preview_event(
                                        preview_type="product",
                                        preview_id=_pid,
                                        title=str(_prod.get("title", _prod.get("name", "Sản phẩm")))[:120],
                                        snippet=str(_prod.get("description", ""))[:300],
                                        url=_prod.get("url") or _prod.get("link"),
                                        image_url=_prod.get("image") or _prod.get("image_url") or _prod.get("thumbnail"),
                                        node="product_search_agent",
                                        metadata={
                                            "price": _prod.get("price"),
                                            "rating": _prod.get("rating"),
                                            "seller": _prod.get("seller") or _prod.get("shop"),
                                            "platform": _platform,
                                        },
                                    )
                            except Exception as _pv_err:
                                logger.debug("[STREAM] Product preview parse failed: %s", _pv_err)
                                continue

                    # Product search response — token-stream it
                    final_response = node_output.get("final_response", "")
                    if final_response and not answer_emitted:
                        # Sprint 153: Match tutor pattern — check bus before post-hoc emission
                        _answer_via_bus = "product_search_agent" in _bus_answer_nodes
                        _answer_as_thinking = node_output.get("_answer_streamed_via_bus", False)
                        if not _answer_via_bus and not _answer_as_thinking:
                            async for event in _extract_and_stream_emotion_then_answer(
                                final_response, _soul_emotion_emitted,
                            ):
                                if event.type == "emotion":
                                    _soul_emotion_emitted = True
                                yield event
                            answer_emitted = True
                        elif _answer_via_bus:
                            answer_emitted = True
                    final_state = node_output

                # ---- GUARDIAN NODE ----
                # Sprint 145: Demoted to status-only (safety check, not deep reasoning)
                elif node_name == "guardian":
                    guardian_passed = node_output.get("guardian_passed")
                    logger.debug("[STREAM] Guardian passed: %s", guardian_passed)
                    if not guardian_passed:
                        # Blocked — show reason as status
                        guardian_reason = (
                            node_output.get("guardian_reason", "")
                            or node_output.get("final_response", "")
                        )
                        yield await create_status_event(
                            f"⚠️ Nội dung không phù hợp: {guardian_reason[:100]}" if guardian_reason
                            else "⚠️ Nội dung không phù hợp",
                            "guardian",
                        )
                    else:
                        yield await create_status_event(
                            "✓ Kiểm tra an toàn — Cho phép xử lý",
                            "guardian",
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
                  _think_fb = final_state.get("thinking", "")
                  # Sprint 140b: Don't use pipeline dump as answer
                  if _think_fb and not _is_pipeline_summary(_think_fb):
                      fallback = _think_fb
              if fallback:
                  logger.warning(
                      "[STREAM] No answer emitted — using fallback (%d chars)",
                      len(fallback),
                  )
                  async for event in _extract_and_stream_emotion_then_answer(
                      fallback, _soul_emotion_emitted,
                  ):
                      if event.type == "emotion":
                          _soul_emotion_emitted = True
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
                                  "content_type": s.get("content_type"),      # Sprint 189b
                                  "bounding_boxes": s.get("bounding_boxes"),  # Sprint 189b
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
                      _user_id = (context or {}).get("user_id", "")
                      if _user_id:
                          _es = _esm.get_state(_user_id)
                          _mood_data = {
                              "positivity": round(_es.positivity, 3),
                              "energy": round(_es.energy, 3),
                              "mood": _es.mood.value,
                          }
              except Exception as _mood_err:
                  logger.debug("[STREAM] Emotional state retrieval failed: %s", _mood_err)

              yield await create_metadata_event(
                  reasoning_trace=reasoning_dict,
                  processing_time=processing_time,
                  confidence=final_state.get("grader_score", 0) / 10,
                  model=f"{settings.rag_model_version}-streaming",
                  doc_count=len(sources),
                  thinking=final_state.get("thinking"),
                  thinking_content=final_state.get("thinking_content"),  # Sprint 189b-R5
                  agent_type=final_state.get("next_agent", "rag_agent"),
                  mood=_mood_data,
                  # Sprint 121b: Include session_id so frontend can reuse it
                  session_id=final_state.get("session_id", session_id),
                  # Sprint 189b: Evidence images for document thumbnails
                  evidence_images=final_state.get("evidence_images", []),
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
            logger.exception("[MULTI_AGENT_STREAM] Inner loop error: %s", e)
            yield await create_error_event("Internal processing error")
            # Sprint 153: Always emit done so frontend exits streaming state
            yield await create_done_event(time.time() - start_time)
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
        logger.exception("[MULTI_AGENT_STREAM] Error: %s", e)
        yield await create_error_event("Internal processing error")
        # Sprint 153: Always emit done so frontend exits streaming state
        yield await create_done_event(time.time() - start_time)
        registry.end_request_trace(trace_id)
    finally:
        # Sprint 139: Clean up tracer from module-level storage
        if final_state:
            from app.engine.multi_agent.graph import _cleanup_tracer
            _cleanup_tracer(final_state.get("_trace_id"))
        # Sprint 69+153: Clean up event bus (guard against None bus_id)
        if bus_id:
            _EVENT_QUEUES.pop(bus_id, None)
            _EVENT_QUEUE_CREATED.pop(bus_id, None)
