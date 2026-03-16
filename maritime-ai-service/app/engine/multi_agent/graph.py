"""
Multi-Agent Graph - Phase 8.4

LangGraph workflow for multi-agent orchestration.

Pattern: Supervisor with specialized worker agents

**Integrated with agents/ framework for registry and tracing.**

**CHỈ THỊ SỐ 30: Universal ReasoningTrace for ALL paths**
"""

import asyncio
from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
import re
import uuid
from typing import Any, Dict, Optional, Literal


from langgraph.graph import StateGraph, END

from app.core.config import settings
from app.engine.tools.invocation import get_tool_by_name, invoke_tool_with_runtime
from app.engine.tools.runtime_context import (
    build_tool_runtime_context,
    filter_tools_for_role,
)
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.supervisor import get_supervisor_agent
from app.engine.multi_agent.agents.rag_node import get_rag_agent_node
from app.engine.multi_agent.agents.tutor_node import get_tutor_agent_node
from app.engine.multi_agent.agents.memory_agent import get_memory_agent_node
from app.engine.multi_agent.agents.grader_agent import get_grader_agent_node
from app.engine.reasoning import ReasoningRenderRequest, get_reasoning_narrator
from app.engine.reasoning.reasoning_narrator import build_tool_context_summary
from app.engine.multi_agent.visual_intent_resolver import (
    detect_visual_patch_request,
    filter_tools_for_visual_intent,
    preferred_visual_tool_name,
    resolve_visual_intent,
)

# Agent Registry integration
from app.engine.agents import get_agent_registry

# CHỈ THỊ SỐ 30: Universal ReasoningTrace
from app.engine.reasoning_tracer import get_reasoning_tracer, StepNames, ReasoningTracer

logger = logging.getLogger(__name__)

# Sprint 79: Generate session summary at these message milestones
_SUMMARY_MILESTONES = {6, 12, 20, 30}

# Sprint 139: Module-level tracer storage to avoid msgpack serialization failures.
# ReasoningTracer is NOT msgpack-serializable, so we store it outside AgentState.
# State only carries a string _trace_id key (serializable).
_TRACERS: Dict[str, ReasoningTracer] = {}


def _get_or_create_tracer(state: AgentState) -> ReasoningTracer:
    """
    Get existing tracer from module-level storage or create new one.

    CHỈ THỊ SỐ 30: Enables tracer inheritance across nodes for unified trace.
    State carries only a serializable _trace_id string; the actual
    ReasoningTracer lives in _TRACERS dict (never checkpointed).

    Args:
        state: Current agent state

    Returns:
        ReasoningTracer instance (either inherited or new)
    """
    trace_id = state.get("_trace_id")
    if trace_id and trace_id in _TRACERS:
        return _TRACERS[trace_id]
    # Create new tracer and assign a unique trace_id
    tracer = get_reasoning_tracer()
    trace_id = str(uuid.uuid4())
    _TRACERS[trace_id] = tracer
    state["_trace_id"] = trace_id
    return tracer


def _cleanup_tracer(trace_id: Optional[str]) -> None:
    """Remove tracer from module-level storage after graph completes."""
    if trace_id and trace_id in _TRACERS:
        del _TRACERS[trace_id]


def _build_turn_local_state_defaults(context: Optional[dict] = None) -> dict:
    """Reset request-local fields that must never bleed across checkpointed turns."""
    ctx = context or {}
    return {
        "rag_output": "",
        "tutor_output": "",
        "memory_output": "",
        "tools_used": [],
        "reasoning_trace": None,
        "thinking_content": None,
        "thinking": None,
        "_trace_id": None,
        "guardian_passed": None,
        "skill_context": None,
        "capability_context": None,
        "tool_call_events": [],
        "_answer_streamed_via_bus": False,
        "domain_notice": None,
        "evidence_images": [],
        "conversation_phase": ctx.get("conversation_phase"),
        "host_context": ctx.get("host_context"),
        "subagent_reports": [],
        "_aggregator_action": None,
        "_aggregator_reasoning": None,
        "_reroute_count": 0,
        "_parallel_targets": [],
    }


def _build_recent_conversation_context(state: AgentState) -> str:
    """Build a compact conversation context for narrator prompts."""
    ctx = state.get("context", {}) or {}
    parts: list[str] = []
    summary = str(ctx.get("conversation_summary", "") or "").strip()
    if summary:
        parts.append(summary)

    lc_messages = ctx.get("langchain_messages", []) or []
    if lc_messages:
        recent: list[str] = []
        for msg in lc_messages[-4:]:
            role = getattr(msg, "type", "")
            content = getattr(msg, "content", "")
            if isinstance(msg, dict):
                role = msg.get("role", role)
                content = msg.get("content", content)
            if not content:
                continue
            speaker = "User" if role in ("human", "user") else "Wiii"
            recent.append(f"{speaker}: {str(content)[:220]}")
        if recent:
            parts.append("\n".join(recent))

    return "\n\n".join(part for part in parts if part)


async def _render_reasoning(
    *,
    state: AgentState,
    node: str,
    phase: str,
    intent: str = "",
    cue: str = "",
    next_action: str = "",
    tool_names: Optional[list[str]] = None,
    result: object = None,
    observations: Optional[list[str]] = None,
    confidence: float = 0.0,
    visibility_mode: str = "rich",
    style_tags: Optional[list[str]] = None,
) -> "ReasoningRenderResult":
    """Render narrator-driven visible reasoning from semantic state."""
    ctx = state.get("context", {}) or {}
    request = ReasoningRenderRequest(
        node=node,
        phase=phase,
        intent=intent or str((state.get("routing_metadata") or {}).get("intent", "")),
        cue=cue,
        user_goal=state.get("query", ""),
        conversation_context=_build_recent_conversation_context(state),
        memory_context=str(state.get("memory_output") or ""),
        capability_context=str(state.get("capability_context") or ""),
        tool_context=build_tool_context_summary(tool_names, result=result),
        confidence=confidence,
        next_action=next_action,
        visibility_mode=visibility_mode,
        organization_id=state.get("organization_id") or ctx.get("organization_id"),
        user_id=state.get("user_id", "__global__"),
        personality_mode=ctx.get("personality_mode"),
        mood_hint=ctx.get("mood_hint"),
        observations=[item for item in (observations or []) if item],
        style_tags=style_tags or [],
    )
    return await get_reasoning_narrator().render(request)


# =============================================================================
# Node Functions with Tracing
# =============================================================================

async def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor node - routes to appropriate agent.

    CHỈ THỊ SỐ 30: Adds ROUTING step to reasoning trace.
    """
    registry = get_agent_registry()
    
    # CHỈ THỊ SỐ 30: Universal tracing - start routing step
    tracer = _get_or_create_tracer(state)
    tracer.start_step(StepNames.ROUTING, "Phân tích và định tuyến câu hỏi")
    
    with registry.tracer.span("supervisor", "route"):
        supervisor = get_supervisor_agent()
        result_state = await supervisor.process(state)
        
        # Record routing decision
        next_agent = result_state.get("next_agent", "unknown")
        tracer.end_step(
            result=f"Định tuyến đến: {next_agent}",
            confidence=0.9,
            details={"routed_to": next_agent}
        )
        
        # Propagate trace_id to result state (tracer lives in _TRACERS dict)
        result_state["_trace_id"] = state.get("_trace_id")

        # Sprint 147: Set thinking_effort from routing intent if not already set
        if not state.get("thinking_effort"):
            _intent = ""
            _routing_meta = result_state.get("routing_metadata")
            if isinstance(_routing_meta, dict):
                _intent = _routing_meta.get("intent", "")
            _effort_map = {
                "social": "low",
                "personal": "medium",
                "lookup": "medium",
                "learning": "high",
                "web_search": "high",
                "off_topic": "medium",
                "product_search": "high",
                "colleague_consult": "medium",
            }
            result_state["thinking_effort"] = _effort_map.get(_intent, "medium")

        return result_state


async def rag_node(state: AgentState) -> AgentState:
    """RAG agent node - knowledge retrieval."""
    registry = get_agent_registry()
    with registry.tracer.span("rag_agent", "process"):
        rag_agent = get_rag_agent_node()
        return await rag_agent.process(state)


async def tutor_node(state: AgentState) -> AgentState:
    """Tutor agent node - teaching."""
    registry = get_agent_registry()
    with registry.tracer.span("tutor_agent", "process"):
        tutor_agent = get_tutor_agent_node()
        return await tutor_agent.process(state)


async def memory_node(state: AgentState) -> AgentState:
    """
    Memory agent node — Sprint 72: Retrieve-Extract-Respond.

    CHỈ THỊ SỐ 30: Adds MEMORY_LOOKUP step to reasoning trace.
    """
    registry = get_agent_registry()

    # CHỈ THỊ SỐ 30: Universal tracing
    tracer = _get_or_create_tracer(state)
    tracer.start_step(StepNames.MEMORY_LOOKUP, "Truy xuất ngữ cảnh và bộ nhớ người dùng")

    with registry.tracer.span("memory_agent", "process"):
        # Sprint 72: Get LLM via AgentConfigRegistry for response generation
        from app.engine.multi_agent.agent_config import AgentConfigRegistry
        try:
            thinking_effort = state.get("thinking_effort")
            llm = AgentConfigRegistry.get_llm("memory", effort_override=thinking_effort)
        except Exception as e:
            logger.warning("[MEMORY_NODE] Failed to get LLM: %s", e)
            llm = None

        # Get semantic memory engine
        from app.engine.semantic_memory import get_semantic_memory_engine
        try:
            semantic_memory = get_semantic_memory_engine()
        except Exception as e:
            logger.warning("[MEMORY_NODE] Failed to get memory engine: %s", e)
            semantic_memory = None

        memory_agent = get_memory_agent_node(semantic_memory=semantic_memory)
        result_state = await memory_agent.process(state, llm=llm)

        # End step with result
        memory_output = result_state.get("memory_output", "")
        tracer.end_step(
            result=f"Truy xuất ngữ cảnh: {len(memory_output)} chars",
            confidence=0.85,
            details={"has_context": bool(memory_output)}
        )

        # Propagate trace_id (tracer lives in _TRACERS dict)
        result_state["_trace_id"] = state.get("_trace_id")

        return result_state


async def colleague_agent_node(state: AgentState) -> AgentState:
    """
    Colleague agent node — cross-soul consultation via SoulBridge (Sprint 215).

    Routes admin questions to peer soul (Bro) and returns the response.
    Skips grader (like product_search — external data, not knowledge retrieval).
    """
    registry = get_agent_registry()
    tracer = _get_or_create_tracer(state)
    tracer.start_step("COLLEAGUE_CONSULT", "Hỏi ý kiến Bro")

    with registry.tracer.span("colleague_agent", "process"):
        from app.engine.multi_agent.agents.colleague_node import colleague_agent_process
        result_state = await colleague_agent_process(state)

        tracer.end_step(
            result="Nhận phản hồi từ Bro",
            confidence=0.85,
            details={"peer": "bro"},
        )
        result_state["_trace_id"] = state.get("_trace_id")
        return result_state


async def product_search_node(state: AgentState) -> AgentState:
    """
    Product Search agent node — multi-platform e-commerce search (Sprint 148).

    Skips grader (like tutor/memory/direct — comparison data doesn't need grading).
    """
    registry = get_agent_registry()
    tracer = _get_or_create_tracer(state)
    tracer.start_step("PRODUCT_SEARCH", "Tìm kiếm sản phẩm trên nhiều sàn TMĐT")

    with registry.tracer.span("product_search_agent", "process"):
        from app.engine.multi_agent.agents.product_search_node import get_product_search_agent_node
        agent = get_product_search_agent_node()
        result_state = await agent.process(state)

        tracer.end_step(
            result="Hoàn tất tìm kiếm sản phẩm",
            confidence=0.85,
            details={"tools_used": len(result_state.get("tools_used", []))},
        )
        result_state["_trace_id"] = state.get("_trace_id")
        return result_state


async def grader_node(state: AgentState) -> AgentState:
    """
    Grader agent node - quality control.
    
    CHỈ THỊ SỐ 30: Adds QUALITY_CHECK step to reasoning trace.
    """
    registry = get_agent_registry()
    
    # CHỈ THỊ SỐ 30: Universal tracing
    tracer = _get_or_create_tracer(state)
    tracer.start_step(StepNames.QUALITY_CHECK, "Kiểm tra chất lượng câu trả lời")
    
    with registry.tracer.span("grader_agent", "process"):
        grader_agent = get_grader_agent_node()
        result_state = await grader_agent.process(state)
        
        # End step with grader result
        score = result_state.get("grader_score", 0)
        tracer.end_step(
            result=f"Điểm chất lượng: {score}/10",
            confidence=score / 10,
            details={"score": score, "passed": score >= 6}
        )
        
        # Propagate trace_id (tracer lives in _TRACERS dict)
        result_state["_trace_id"] = state.get("_trace_id")

        return result_state


# Sprint 78c: Greeting sentence starters to detect (case-insensitive, diacritic-aware)
_GREETING_STARTERS = [
    "chào", "xin chào", "hello", "hi ",
    "rất vui", "rat vui",
]


def _strip_greeting_prefix(text: str) -> str:
    """
    Strip greeting sentences from the start of a follow-up response.

    Sprint 78c: Deterministic post-filter — no LLM needed.
    Removes leading sentences that start with greeting words.
    Handles: "Chào Nam! Rất vui được tiếp tục hỗ trợ bạn. Nội dung..."
           → "Nội dung..."
    """
    if not text:
        return text

    # Split into sentences by . ! or newline (keep delimiters)
    parts = re.split(r'(?<=[.!?\n])\s*', text, maxsplit=5)

    # Remove leading greeting sentences
    removed = 0
    for part in parts:
        part_lower = part.lower().strip()
        if not part_lower:
            removed += 1
            continue
        if any(part_lower.startswith(g) for g in _GREETING_STARTERS):
            removed += 1
        else:
            break

    if removed == 0:
        return text

    remaining = " ".join(parts[removed:]).strip()

    # Safety: don't strip if it removes >60% of content
    if not remaining or len(remaining) < len(text) * 0.4:
        return text

    # Capitalize first char
    if remaining[0].islower():
        remaining = remaining[0].upper() + remaining[1:]

    return remaining


async def synthesizer_node(state: AgentState) -> AgentState:
    """
    Synthesizer node - combine outputs into final response.

    CHỈ THỊ SỐ 30: Adds SYNTHESIS step and builds final reasoning_trace.
    CHỈ THỊ SỐ 31: Merges CRAG trace with graph trace for complete picture.

    This is the final node where trace is compiled for non-direct paths.
    """
    # CHỈ THỊ SỐ 30: Universal tracing
    tracer = _get_or_create_tracer(state)
    tracer.start_step(StepNames.SYNTHESIS, "Tổng hợp câu trả lời cuối cùng")
    
    supervisor = get_supervisor_agent()
    
    # Synthesize outputs
    final_response = await supervisor.synthesize(state)

    # Sprint 78c: Strip greeting prefix on follow-up messages (deterministic post-filter)
    # Sprint 203: Skip when natural conversation enabled (positive framing prevents at source)
    if not getattr(settings, "enable_natural_conversation", False):
        is_follow_up = state.get("context", {}).get("is_follow_up", False)
        if is_follow_up and final_response:
            stripped = _strip_greeting_prefix(final_response)
            if stripped != final_response:
                logger.debug("[SYNTHESIZER] Greeting stripped from follow-up response")
                final_response = stripped

    state["final_response"] = final_response

    # End synthesis step
    tracer.end_step(
        result=f"Tổng hợp hoàn tất: {len(final_response)} chars",
        confidence=0.9,
        details={"response_length": len(final_response)}
    )
    
    # CHỈ THỊ SỐ 31 v3 SOTA: Priority Merge - ONLY merge CRAG trace (not graph trace)
    # CRAG trace has was_corrected attribute, graph trace doesn't
    existing_trace = state.get("reasoning_trace")
    is_crag_trace = (
        existing_trace and 
        hasattr(existing_trace, 'was_corrected') and  # CRAG-specific field
        hasattr(existing_trace, 'steps') and 
        len(existing_trace.steps) > 0
    )
    if is_crag_trace:
        # CRAG trace exists - merge graph steps AROUND it
        tracer.merge_trace(existing_trace, position="after_first")
        logger.info("[SYNTHESIZER] Merged CRAG trace (%d steps) with graph trace", len(existing_trace.steps))
    
    # Build final merged trace
    state["reasoning_trace"] = tracer.build_trace()
    logger.info("[SYNTHESIZER] Final trace: %d steps", state['reasoning_trace'].total_steps)
    
    logger.info("[SYNTHESIZER] Final response generated, length=%d", len(final_response))

    # Tracer cleanup happens in process_with_multi_agent() after graph.ainvoke()
    # _trace_id in state is just a string key — safe for msgpack serialization

    return state




# =============================================================================
# Sprint 99: Intent-based forced tool calling (Tier 2 — VTuber pattern)
# =============================================================================

# Keywords that signal the query needs web search (diacritics-free for matching)
_WEB_INTENT_KEYWORDS: list[str] = [
    # Explicit web requests
    "tim tren mang", "tim tren web", "search web", "tim kiem web",
    "search online", "tim tren internet", "tra cuu tren mang",
    "tra cuu tren web", "google",
    # News / current events
    "tin tuc", "ban tin", "news", "thoi su",
    "su kien", "cap nhat", "update", "bao chi",
    # Temporal signals (today, recently, latest)
    "hom nay", "ngay hom nay", "moi nhat", "moi day", "gan day",
    "latest", "today", "thoi tiet", "gia vang", "ty gia",
    # Explicit search verbs
    "tra cuu", "look up", "find out",
    # Sprint 102: Legal search signals
    "phap luat", "van ban phap luat", "nghi dinh", "thong tu",
    "luat so", "bo luat", "thu vien phap luat",
    "nghi quyet", "quyet dinh so", "van ban quy pham",
    # Sprint 102: Maritime web signals
    "imo regulation", "imo quy dinh", "maritime news",
    "tin hang hai", "shipping news", "vinamarine",
    "cuc hang hai",
]

# Keywords that signal the query needs current datetime
_DATETIME_INTENT_KEYWORDS: list[str] = [
    "ngay may", "may gio", "hom nay la ngay",
    "gio hien tai", "ngay hien tai", "thoi gian hien tai",
    "what time", "what date", "current time", "current date",
    "bay gio", "bay gio la",
]


def _normalize_for_intent(text: str) -> str:
    """Strip diacritics + lowercase for intent matching.

    Reuses TextNormalizer.strip_diacritics when available,
    falls back to unicodedata NFD decomposition.
    """
    try:
        from app.engine.content_filter import TextNormalizer
        return TextNormalizer.strip_diacritics(text.lower().strip())
    except Exception:
        import unicodedata
        nfkd = unicodedata.normalize("NFKD", text.lower().strip())
        return "".join(c for c in nfkd if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D")


def _needs_web_search(query: str) -> bool:
    """Detect if query requires web search (diacritics-insensitive)."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _WEB_INTENT_KEYWORDS)


def _needs_datetime(query: str) -> bool:
    """Detect if query requires current datetime (diacritics-insensitive)."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _DATETIME_INTENT_KEYWORDS)


# Sprint 102: Additional intent detectors for logging/observability
_NEWS_INTENT_KEYWORDS: list[str] = [
    "tin tuc", "thoi su", "ban tin", "bao chi", "news",
    "su kien hom nay", "tin moi", "diem tin",
]

_LEGAL_INTENT_KEYWORDS: list[str] = [
    "phap luat", "nghi dinh", "thong tu", "luat so", "bo luat",
    "van ban phap luat", "thu vien phap luat", "quy dinh phap luat",
    "nghi quyet", "quyet dinh so", "van ban quy pham",
]

_ANALYSIS_INTENT_KEYWORDS: list[str] = [
    "python",
    "code python",
    "chay python",
    "chay code",
    "viet code",
    "doan code",
    "sandbox",
    "ve bieu do",
    "bieu do",
    "chart",
    "plot",
    "matplotlib",
    "pandas",
    "xlsx",
    "excel bang python",
]

_CODE_STUDIO_INTENT_KEYWORDS: list[str] = [
    *_ANALYSIS_INTENT_KEYWORDS,
    "html",
    "css",
    "javascript",
    "typescript",
    "react",
    "landing page",
    "website",
    "web app",
    "microsite",
    "tao file html",
]


def _needs_news_search(query: str) -> bool:
    """Detect if query needs news search (Sprint 102)."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _NEWS_INTENT_KEYWORDS)


def _needs_legal_search(query: str) -> bool:
    """Detect if query needs legal search (Sprint 102)."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _LEGAL_INTENT_KEYWORDS)


def _needs_analysis_tool(query: str) -> bool:
    """Detect requests that should prefer Python/code execution tooling."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _ANALYSIS_INTENT_KEYWORDS)


def _needs_code_studio(query: str) -> bool:
    """Detect requests that belong to the code studio capability lane."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _CODE_STUDIO_INTENT_KEYWORDS)


# Sprint 175: LMS intent detection keywords
_LMS_INTENT_KEYWORDS: list[str] = [
    "diem so", "diem cua toi", "ket qua hoc tap", "bang diem",
    "bai tap", "deadline", "han nop", "sap den han",
    "mon hoc", "khoa hoc", "tien do hoc",
    "kiem tra", "bai kiem tra", "quiz",
    "nguy co", "sinh vien yeu", "hoc kem",
    "lop hoc", "tong quan lop",
    "grade", "assignment", "course", "enrollment",
]


def _needs_lms_query(query: str) -> bool:
    """Detect if query needs LMS data tools (Sprint 175)."""
    from app.core.config import settings as _s
    if not _s.enable_lms_integration:
        return False
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _LMS_INTENT_KEYWORDS)


def _build_direct_tools_context(
    settings_obj,
    domain_name_vi: str,
    user_role: str = "student",
) -> str:
    """Build tools context string for direct node from settings + knowledge limits.

    Sprint 100: Extracted from direct_response_node f-string soup.
    Produces the same content as Sprint 97b-99 tool hints + knowledge limits.
    """
    # Sprint 204: Natural guidance vs legacy constraint prompts
    try:
        _natural_guidance = getattr(settings_obj, "enable_natural_conversation", False) is True
    except Exception:
        _natural_guidance = False

    tool_hints = []
    if settings_obj.enable_character_tools:
        tool_hints.append(
            "- tool_character_note: Ghi chú khi user chia sẻ thông tin cá nhân MỚI."
        )

    if _natural_guidance:
        # Sprint 204: Identity-based guidance (Anthropic 2026: "Describe WHO, not WHAT MUST NOT")
        tool_hints.append(
            "- tool_current_datetime: Lấy ngày giờ hiện tại (UTC+7). "
            "Wiii luôn chính xác — khi cần biết thời gian, Wiii dùng tool để đảm bảo."
        )
        tool_hints.append(
            "- tool_web_search: Tìm kiếm TỔNG HỢP trên web. "
            "Dùng cho thời tiết, giá vàng, thông tin chung không thuộc tin tức hay pháp luật."
        )
        tool_hints.append(
            "- tool_search_news: Tìm kiếm TIN TỨC Việt Nam. "
            "Wiii chọn tool này khi người dùng quan tâm tin tức, thời sự, bản tin. "
            "Nguồn: VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí + RSS."
        )
        tool_hints.append(
            "- tool_search_legal: Tìm kiếm VĂN BẢN PHÁP LUẬT VN. "
            "Wiii chọn tool này khi câu hỏi liên quan luật, nghị định, thông tư, mức phạt. "
            "Nguồn: Thư viện Pháp luật, Cổng TTĐT Chính phủ."
        )
    else:
        # LEGACY: constraint-based tool hints
        tool_hints.append(
            "- tool_current_datetime: Lấy ngày giờ hiện tại (UTC+7). "
            "BẮT BUỘC gọi khi user hỏi 'hôm nay ngày mấy', 'bây giờ mấy giờ', hoặc bất kỳ câu hỏi về thời gian hiện tại."
        )
        tool_hints.append(
            "- tool_web_search: Tìm kiếm TỔNG HỢP trên web. "
            "Dùng khi câu hỏi KHÔNG thuộc tin tức, pháp luật, hay hàng hải. "
            "VD: thời tiết, giá vàng, thông tin chung."
        )
        tool_hints.append(
            "- tool_search_news: Tìm kiếm TIN TỨC Việt Nam. "
            "BẮT BUỘC khi user hỏi 'tin tức', 'thời sự', 'bản tin', 'sự kiện hôm nay'. "
            "Nguồn: VnExpress, Tuổi Trẻ, Thanh Niên, Dân Trí + RSS."
        )
        tool_hints.append(
            "- tool_search_legal: Tìm kiếm VĂN BẢN PHÁP LUẬT VN. "
            "BẮT BUỘC khi user hỏi về luật, nghị định, thông tư, mức phạt, bộ luật. "
            "Nguồn: Thư viện Pháp luật, Cổng TTĐT Chính phủ."
        )

    tool_hints.append(
        "- tool_search_maritime: Tìm kiếm HÀNG HẢI quốc tế. "
        "Dùng khi hỏi về IMO, quy định quốc tế, shipping news, DNV, Cục Hàng hải."
    )
    # WAVE-001: code/chart/document/browser tool hints removed from direct.
    # These capabilities are handled by code_studio_agent.
    # Direct now focuses on: conversation, web search, knowledge, character, LMS.

    # Sprint 229d: Visual tools available to direct for inline rich visuals.
    if getattr(settings, "enable_structured_visuals", False):
        tool_hints.append(
            "- tool_generate_visual: TOOL CHINH cho moi visual giai thich. "
            "Tao 2-3 figures co cau truc (comparison, process, matrix, architecture, concept, infographic, chart, timeline, map_lite). "
            "LUON goi NHIEU LAN (2-3 calls) de tao multi-figure explanation. "
            "Frontend render inline ngay trong stream."
        )
        tool_hints.append(
            "- Neu user follow-up de sua/hightlight/loc visual vua tao, goi tool_generate_visual voi CUNG visual_session_id va operation='patch'."
        )
        tool_hints.append(
            "- tool_generate_rich_visual: CHI dung cho simulation (Canvas+sliders), quiz trac nghiem, hoac react_app. "
            "KHONG dung cho comparison, process, matrix, architecture, concept, infographic — nhung loai nay PHAI dung tool_generate_visual."
        )
    else:
        tool_hints.append(
            "- tool_generate_rich_visual: TAO VISUAL TUONG TAC inline (comparison, process, matrix, "
            "architecture, concept, infographic, simulation, quiz, interactive_table, react_app). "
            "Goi tool nay khi can GIAI THICH TRUC QUAN, SO SANH, hoac QUIZ."
        )

    parts = []
    parts.append("## CÔNG CỤ CÓ SẴN:\n" + "\n".join(tool_hints))

    if _natural_guidance:
        # Sprint 204: Identity-based knowledge context (positive framing)
        parts.append(
            "\n## VỀ KIẾN THỨC CỦA WIII:"
            "\n- Wiii có kiến thức huấn luyện đến đầu 2024."
            "\n- Khi cần thông tin mới (tin tức, thời tiết, giá cả, sự kiện sau 2024), "
            "Wiii dùng tool tìm kiếm để đảm bảo chính xác."
            "\n- Khi cần biết ngày giờ, Wiii dùng tool_current_datetime."
        )
        parts.append(
            "\n## CÁCH WIII SỬ DỤNG TOOL:"
            "\n- Wiii chọn tool phù hợp nhất với nội dung câu hỏi:"
            "\n   - Tin tức / thời sự → tool_search_news"
            "\n   - Luật / nghị định / mức phạt → tool_search_legal"
            "\n   - Hàng hải / IMO / shipping → tool_search_maritime"
            "\n   - Thời tiết, giá cả, thông tin chung → tool_web_search"
            "\n- Wiii tra cứu trước, trả lời sau — luôn dựa trên dữ liệu thực."
            "\n- Có thể dùng nhiều tool cùng lúc khi cần."
            "\n- Wiii trung thực: nếu tool không trả về kết quả, Wiii nói thẳng."
            "\n- Wiii tập trung trả lời đúng câu hỏi, không gợi ý chuyển chủ đề."
        )
    else:
        # LEGACY: constraint-based rules
        parts.append(
            "\n## GIỚI HẠN KIẾN THỨC (QUAN TRỌNG):"
            "\n- Kiến thức huấn luyện của bạn CŨ — ngắt vào đầu năm 2024."
            "\n- Bạn KHÔNG CÓ Internet trực tiếp — chỉ có thể truy cập web QUA tool_web_search."
            "\n- Bạn KHÔNG BIẾT ngày giờ hiện tại — chỉ biết qua tool_current_datetime."
            "\n- Bất kỳ câu hỏi về sự kiện, tin tức, thời tiết, giá cả SAU năm 2024 → PHẢI gọi tool."
        )
        parts.append(
            "\n## QUY TẮC BẮT BUỘC VỀ TOOL:"
            "\n1. PHẢI gọi tool_current_datetime khi hỏi về ngày/giờ. TUYỆT ĐỐI KHÔNG tự đoán."
            "\n2. CHỌN ĐÚNG TOOL tìm kiếm:"
            "\n   - Tin tức / thời sự / bản tin → tool_search_news"
            "\n   - Luật / nghị định / thông tư / mức phạt → tool_search_legal"
            "\n   - Hàng hải quốc tế / IMO / shipping → tool_search_maritime"
            "\n   - Thời tiết, giá cả, thông tin chung → tool_web_search"
            "\n3. GỌI TOOL TRƯỚC — trả lời SAU. Không bao giờ trả lời trước rồi mới gọi tool."
            "\n4. Nếu không chắc thông tin có còn đúng không → gọi tool tìm kiếm để xác minh."
            "\n5. Có thể gọi NHIỀU tool cùng lúc."
            "\n6. KHÔNG BAO GIỜ tự bịa tin tức, sự kiện, số liệu, nhiệt độ, độ ẩm, tốc độ gió."
            "\n   Nếu tool thất bại hoặc không gọi được → nói thẳng 'Mình không tra cứu được lúc này'."
            "\n7. KHÔNG gợi ý chuyển chủ đề. Trả lời đúng câu hỏi của user, KHÔNG hỏi ngược về chủ đề khác."
        )
    # Sprint 121: Only mention domain expertise if relevant
    # Removed unconditional domain mention — it caused LLM to redirect
    # off-topic queries back to domain topics (e.g., weather → SOLAS)
    return "\n".join(parts)


def _build_code_studio_tools_context(
    settings_obj,
    user_role: str = "student",
    query: str = "",
) -> str:
    """Build focused tool guidance for the code studio capability.

    WAVE-002: added explicit chart tool priority — execute_python produces real PNG artifacts;
    Mermaid tools are for diagrams/structures when sandbox is unavailable.
    """
    has_execute_python = getattr(settings_obj, "enable_code_execution", False) and user_role == "admin"
    structured_visuals_enabled = getattr(settings_obj, "enable_structured_visuals", False)
    visual_decision = resolve_visual_intent(query)

    tool_hints = []

    if has_execute_python:
        tool_hints.append(
            "- tool_execute_python: Chay Python trong sandbox de tinh toan, phan tich, tao bieu do, va sinh artifact that. "
            "Khi lam chart/plot/visualization, UU TIEN dung tool nay voi matplotlib/seaborn de luu ra file PNG that. "
            "Day la cong cu chinh cho moi yeu cau 've bieu do', 'plot', 'chart data'."
        )

    tool_hints += [
        "- tool_generate_html_file: Tao file HTML hoan chinh khi user can landing page, microsite, email template, web preview, hoac bat ky artifact HTML nao.",
        "- tool_generate_excel_file: Tao file Excel (.xlsx) tu du lieu bang khi user can spreadsheet hoac bang tong hop de tai xuong.",
        "- tool_generate_word_document: Tao file Word (.docx) tu noi dung co cau truc khi user can memo, report, proposal, hoac handout.",
    ]

    if structured_visuals_enabled and visual_decision.force_tool and visual_decision.mode == "template":
        tool_hints.append(
            "- tool_generate_interactive_chart: KHONG phai lua chon chinh cho query hien tai. "
            "Chi dung khi user can dashboard so hoc / hover tooltip / raw numeric chart. "
            "Neu chart dung de giai thich khai niem, co che, trade-off, hoac so sanh -> dung tool_generate_visual."
        )
    else:
        tool_hints.append(
            "- tool_generate_interactive_chart: TAO BIEU DO TUONG TAC (bar, line, pie, doughnut, radar) "
            "voi Chart.js cho dashboard du lieu so hoc, hover tooltip, va metric widgets. "
            "UU TIEN tool nay khi user can data chart tuong tac don le. "
            "Tra ve ```widget code block — FE tu render."
        )

    if structured_visuals_enabled:
        tool_hints.append(
            "- tool_generate_visual: TOOL CHINH — tao 2-3 structured figures cho moi giai thich. "
            "Types: comparison, process, matrix, architecture, concept, infographic, chart, timeline, map_lite. "
            "GOI NHIEU LAN (2-3 calls) de tao multi-figure explanation nhu Claude Artifacts. "
            "Frontend render inline ngay khi stream, khong can copy payload."
        )
        # Phase 4: LLM code-gen HTML for unique visuals
        if getattr(settings_obj, "enable_llm_code_gen_visuals", False):
            tool_hints.append(
                "- code_html param (trong tool_generate_visual): Khi can visual PHUC TAP, CUSTOM, hoac doc dao — "
                "viet HTML/CSS/SVG truc tiep. Moi visual se unique, dep, khong bi giong nhau. "
                "Dung CSS vars: --bg, --bg2, --text, --text2, --text3, --accent, --green, --purple, --amber, --teal, --pink, --border, --radius. "
                "Dark mode tu dong. Uu tien CSS animation > JavaScript. "
                "UU TIEN code_html khi: diagram mang luoi, flowchart phuc tap, SVG custom, data viz doc dao, "
                "hoac bat ky visual nao ma spec_json cua type co san khong the dien dat tot."
            )
        tool_hints.append(
            "- Follow-up visual edits: neu user muon chinh visual vua co, reuse visual_session_id va set operation='patch'."
        )
        tool_hints.append(
            "- tool_generate_rich_visual: CHI dung cho simulation (Canvas+sliders), quiz trac nghiem, react_app. "
            "KHONG dung cho comparison/process/matrix/architecture/concept/infographic — dung tool_generate_visual."
        )
    else:
        tool_hints.append(
            "- tool_generate_rich_visual: TAO VISUAL TUONG TAC CAP CAO (Claude-level). "
            "10 loai: comparison, process, matrix, architecture, concept, infographic, "
            "simulation (Canvas + sliders), quiz (trac nghiem), interactive_table (sap xep/tim kiem), "
            "react_app (FULL REACT APP — React 18 + Tailwind + Recharts — cung kien truc nhu Claude Artifacts). "
            "Voi react_app: viet function App() component, dung Tailwind classes, Recharts charts. "
            "UU TIEN react_app cho: dashboards phuc tap, UI tuong tac nhieu component, data viz voi Recharts. "
            "UU TIEN simulation cho: vat ly, toan hoc, animation Canvas. "
            "UU TIEN quiz cho: kiem tra kien thuc. "
            "Tra ve ```widget code block — FE tu render trong sandboxed iframe."
        )

    if has_execute_python:
        tool_hints.append(
            "- tool_generate_mermaid / tool_generate_chart: Du phong cho bieu do khi sandbox khong kha dung. "
            "Chi dung khi khong the chay tool_execute_python. Output la Mermaid syntax (SVG), khong phai PNG that."
        )
    else:
        tool_hints.append(
            "- tool_generate_mermaid / tool_generate_chart: Tao so do, bieu do cau truc (flowchart, sequence, pie chart) "
            "bang Mermaid syntax. FE se render thanh SVG. Chi dung cho so do/quy trinh, KHONG cho data visualization."
        )

    if (
        user_role == "admin"
        and getattr(settings_obj, "enable_browser_agent", False)
        and getattr(settings_obj, "enable_privileged_sandbox", False)
        and getattr(settings_obj, "sandbox_provider", "") == "opensandbox"
        and getattr(settings_obj, "sandbox_allow_browser_workloads", False)
    ):
        tool_hints.append(
            "- tool_browser_snapshot_url: Mo trang web trong browser sandbox de xem render that, chup snapshot, va xac minh artifact front-end.",
        )

    priority_rules = [
        "## NGUYEN TAC UU TIEN:",
        "- Uu tien tao output THAT (file, PNG, HTML, widget) thay vi chi mo ta bang loi.",
        "- Voi yeu cau 've bieu do / chart / thong ke / so lieu': " + (
            (
                "neu chart dung de GIAI THICH khai niem/co che/trade-off -> goi tool_generate_visual (type=chart, comparison, process...). "
                "Chi dung tool_execute_python hoac tool_generate_interactive_chart cho data dashboard / raw numeric plots khi hover, tooltip, metric widgets la muc tieu chinh."
                if structured_visuals_enabled else
                "goi tool_execute_python neu can tinh toan phuc tap, HOAC goi tool_generate_interactive_chart "
                "neu da co san labels + data. Widget chart hien thi INLINE trong chat, user co the tuong tac."
            )
            if has_execute_python else
            (
                "neu chart dung de GIAI THICH khai niem/co che/trade-off -> goi tool_generate_visual. "
                "Chi dung tool_generate_interactive_chart cho data dashboard / numeric chart. "
                "Chi dung tool_generate_mermaid cho so do/quy trinh (flowchart, mindmap), KHONG cho data chart."
                if structured_visuals_enabled else
                "goi tool_generate_interactive_chart (uu tien) de tao bieu do tuong tac inline. "
                "Chi dung tool_generate_mermaid cho so do/quy trinh (flowchart, mindmap), KHONG cho data chart."
            )
        ),
        "- Voi yeu cau 'tao trang web / HTML / landing page': luon goi tool_generate_html_file.",
        "- Voi yeu cau 'tao file Excel / spreadsheet': luon goi tool_generate_excel_file.",
        "- Voi yeu cau 'tao file Word / bao cao / report': luon goi tool_generate_word_document.",
        "- Voi yeu cau GIAI THICH khai niem / SO SANH / KIEN TRUC: goi "
        + ("tool_generate_visual 2-3 LAN de tao multi-figure" if structured_visuals_enabled else "tool_generate_rich_visual")
        + ". Visual types: comparison (2 cot so sanh), process (tung buoc), matrix (bang mau), "
        "architecture (layer diagram), concept (mind map), infographic (stats).",
        (
            "- SAU KHI goi tool_generate_interactive_chart HOAC tool_generate_rich_visual: "
            "COPY NGUYEN VAN widget code block vao response."
            if not structured_visuals_enabled
            else "- SAU KHI goi tool_generate_visual: khong copy payload JSON vao answer. Viet bridge prose + takeaway, frontend se chen figure tu dong. "
                 "Chi copy ```widget khi dang fallback sang rich_visual/interactive_chart cho legacy compatibility."
        ),
        "- Khi sandbox gap loi ket noi, noi ro gioi han va KHONG gia vo da chay code.",
    ]

    sections = ["## CODE STUDIO TOOLKIT:", *tool_hints, "", *priority_rules]

    # Phase 4: Append design system reference for visual code-gen
    if getattr(settings_obj, "enable_llm_code_gen_visuals", False):
        sections.append("")
        sections.append(_load_visual_code_gen_skill())

    return "\n".join(sections)


_VISUAL_CODE_GEN_SKILL_CACHE: str | None = None


def _load_visual_code_gen_skill() -> str:
    """Load and cache the visual code-gen design system skill reference."""
    global _VISUAL_CODE_GEN_SKILL_CACHE
    if _VISUAL_CODE_GEN_SKILL_CACHE is not None:
        return _VISUAL_CODE_GEN_SKILL_CACHE

    skill_path = (
        Path(__file__).resolve().parent.parent
        / "reasoning" / "skills" / "subagents" / "code_studio_agent" / "VISUAL_CODE_GEN.md"
    )
    try:
        raw = skill_path.read_text(encoding="utf-8")
        # Strip YAML frontmatter
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                _VISUAL_CODE_GEN_SKILL_CACHE = parts[2].strip()
                return _VISUAL_CODE_GEN_SKILL_CACHE
        _VISUAL_CODE_GEN_SKILL_CACHE = raw.strip()
        return _VISUAL_CODE_GEN_SKILL_CACHE
    except Exception as exc:
        logger.debug("[CODE_STUDIO] Visual code-gen skill unavailable: %s", exc)
        _VISUAL_CODE_GEN_SKILL_CACHE = ""
        return ""


def _log_visual_telemetry(event_name: str, **fields: object) -> None:
    if fields:
        logger.info("[VISUAL_TELEMETRY] %s %s", event_name, json.dumps(fields, ensure_ascii=False, sort_keys=True))
    else:
        logger.info("[VISUAL_TELEMETRY] %s", event_name)


def _summarize_tool_result_for_stream(tool_name: str, result: object) -> str:
    """Keep SSE tool_result concise for structured payload tools."""
    try:
        from app.engine.tools.visual_tools import parse_visual_payloads

        payloads = parse_visual_payloads(result)
        if payloads:
            if len(payloads) == 1:
                return f"Minh hoa da san sang: {payloads[0].title}"
            group_title = payloads[0].title
            return f"Nhom minh hoa da san sang: {group_title} va {len(payloads) - 1} figure lien ket"
    except Exception:
        pass
    return str(result)[:500]


def _collect_active_visual_session_ids(state: AgentState) -> list[str]:
    """Collect active inline visual sessions from client-provided visual context."""
    visual_ctx = ((state.get("context") or {}).get("visual_context") or {})
    if not isinstance(visual_ctx, dict):
        return []

    session_ids: list[str] = []
    active_items = visual_ctx.get("active_inline_visuals")
    if isinstance(active_items, list):
        for item in active_items:
            if not isinstance(item, dict):
                continue
            visual_session_id = str(item.get("visual_session_id") or item.get("session_id") or "").strip()
            if visual_session_id and visual_session_id not in session_ids:
                session_ids.append(visual_session_id)

    fallback_session_id = str(visual_ctx.get("last_visual_session_id") or "").strip()
    if fallback_session_id and fallback_session_id not in session_ids:
        session_ids.append(fallback_session_id)

    return session_ids


async def _maybe_emit_visual_event(
    *,
    push_event,
    tool_name: str,
    tool_call_id: str,
    result: object,
    node: str,
    tool_call_events: list[dict],
    previous_visual_session_ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Stream structured visual results immediately when available."""
    try:
        from app.engine.tools.visual_tools import parse_visual_payloads

        payloads = parse_visual_payloads(result)
        if not payloads:
            return [], []

        payloads = sorted(payloads, key=lambda payload: (payload.figure_index, payload.title))
        emitted_session_ids = [payload.visual_session_id for payload in payloads if payload.visual_session_id]
        disposed_session_ids: list[str] = []
        existing_session_ids = [
            session_id
            for session_id in (previous_visual_session_ids or [])
            if session_id
        ]

        first_event_type = (
            payloads[0].lifecycle_event
            if payloads[0].lifecycle_event in {"visual_open", "visual_patch"}
            else "visual_open"
        )
        if first_event_type == "visual_open":
            for previous_visual_session_id in existing_session_ids:
                if previous_visual_session_id in emitted_session_ids:
                    continue
                disposed_session_ids.append(previous_visual_session_id)
                await push_event({
                    "type": "visual_dispose",
                    "content": {
                        "visual_session_id": previous_visual_session_id,
                        "status": "disposed",
                        "reason": "superseded_by_new_visual",
                    },
                    "node": node,
                })
                tool_call_events.append({
                    "type": "visual_dispose",
                    "visual_session_id": previous_visual_session_id,
                    "reason": "superseded_by_new_visual",
                    "node": node,
                })
                _log_visual_telemetry(
                    "visual_disposed",
                    visual_session_id=previous_visual_session_id,
                    reason="superseded_by_new_visual",
                    node=node,
                )

        for payload in payloads:
            payload_dict = payload.model_dump(mode="json")
            event_type = payload.lifecycle_event if payload.lifecycle_event in {"visual_open", "visual_patch"} else "visual_open"
            await push_event({
                "type": event_type,
                "content": payload_dict,
                "node": node,
            })
            tool_call_events.append({
                "type": event_type,
                "name": tool_name,
                "id": tool_call_id,
                "visual": payload_dict,
                "visual_session_id": payload.visual_session_id,
                "figure_group_id": payload.figure_group_id,
                "figure_index": payload.figure_index,
            })
            _log_visual_telemetry(
                "visual_emitted",
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                visual_id=payload.id,
                visual_session_id=payload.visual_session_id,
                visual_type=payload.type,
                lifecycle_event=event_type,
                node=node,
                figure_group_id=payload.figure_group_id,
                figure_index=payload.figure_index,
                figure_total=payload.figure_total,
                pedagogical_role=payload.pedagogical_role,
                chrome_mode=payload.chrome_mode,
            )

        return emitted_session_ids, disposed_session_ids
    except Exception as exc:
        logger.warning("[VISUAL] Failed to emit structured visual event: %s", exc)
    return [], []


async def _emit_visual_commit_events(
    *,
    push_event,
    node: str,
    visual_session_ids: list[str],
    tool_call_events: list[dict],
) -> None:
    """Emit commit events for visual sessions touched in the current tool round."""
    emitted: set[str] = set()
    for visual_session_id in visual_session_ids:
        if not visual_session_id or visual_session_id in emitted:
            continue
        emitted.add(visual_session_id)
        await push_event({
            "type": "visual_commit",
            "content": {
                "visual_session_id": visual_session_id,
                "status": "committed",
            },
            "node": node,
        })
        tool_call_events.append({
            "type": "visual_commit",
            "visual_session_id": visual_session_id,
            "node": node,
        })
        _log_visual_telemetry(
            "visual_committed",
            visual_session_id=visual_session_id,
            node=node,
        )


def _collect_direct_tools(query: str, user_role: str = "student"):
    """Collect tools for direct response node and determine forced calling.

    Sprint 154: Extracted from direct_response_node.

    Returns:
        tuple: (tools_list, llm_with_tools_factory, llm_auto_factory, force_tools)
            - tools_list: List of available tools
            - force_tools: Whether to force tool calling (intent detected)
    """
    _direct_tools = []
    try:
        if settings.enable_character_tools:
            from app.engine.character.character_tools import get_character_tools
            _direct_tools = get_character_tools()
    except Exception as _e:
        logger.debug("[DIRECT] Character tools unavailable: %s", _e)

    # WAVE-001: code_execution, browser_sandbox removed from direct.
    # These capabilities now live exclusively in code_studio_agent.
    # Boundary enforced at tool-binding level (LLM-first, not keyword).

    try:
        from app.engine.tools.utility_tools import tool_current_datetime
        from app.engine.tools.web_search_tools import (
            tool_web_search, tool_search_news,
            tool_search_legal, tool_search_maritime,
        )
        _direct_tools = [
            *_direct_tools, tool_current_datetime,
            tool_web_search, tool_search_news,
            tool_search_legal, tool_search_maritime,
        ]
    except Exception as _e:
        logger.debug("[DIRECT] Utility/web search tools unavailable: %s", _e)

    # Sprint 214: Knowledge search for org KB (Direct can search internal docs)
    try:
        from app.engine.tools.rag_tools import tool_knowledge_search
        _direct_tools.append(tool_knowledge_search)
    except Exception as _e:
        logger.debug("[DIRECT] Knowledge search tool unavailable: %s", _e)

    # Sprint 175: LMS tools (role-aware)
    try:
        if settings.enable_lms_integration:
            from app.engine.tools.lms_tools import get_all_lms_tools
            _direct_tools.extend(get_all_lms_tools(role="student"))
    except Exception as _e:
        logger.debug("[DIRECT] LMS tools unavailable: %s", _e)

    # Structured visuals re-enable lightweight inline diagram/chart tools for direct,
    # but keep heavy artifact/file generation inside code_studio_agent.
    if getattr(settings, "enable_structured_visuals", False):
        try:
            from app.engine.tools.chart_tools import get_chart_tools

            _direct_tools.extend(get_chart_tools())
        except Exception as _e:
            logger.debug("[DIRECT] Chart tools unavailable: %s", _e)

    # Sprint 229d: Re-add visual tools to direct agent so it can generate
    # rich visuals (comparison, process, quiz, etc.) without routing to code_studio.
    # This fixes the issue where direct agent writes raw JSON in widget blocks.
    try:
        from app.engine.tools.visual_tools import get_visual_tools

        _direct_tools.extend(get_visual_tools())
    except Exception as _e:
        logger.debug("[DIRECT] Visual tools unavailable: %s", _e)

    visual_decision = resolve_visual_intent(query)
    _direct_tools = filter_tools_for_role(_direct_tools, user_role)
    _direct_tools = filter_tools_for_visual_intent(
        _direct_tools,
        visual_decision,
        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
    )
    _needs_visual_tool = (
        not _needs_analysis_tool(query)
        and visual_decision.force_tool
        and visual_decision.mode in {"template", "inline_html", "app", "mermaid"}
    )
    if _needs_visual_tool:
        _log_visual_telemetry(
            "visual_requested",
            mode=visual_decision.mode,
            visual_type=visual_decision.visual_type,
            user_role=user_role,
            query=query[:180],
        )
    force_tools = bool(_direct_tools) and (
        _needs_web_search(query) or _needs_datetime(query)
        or _needs_news_search(query) or _needs_legal_search(query)
        or _needs_lms_query(query) or _needs_visual_tool
    )
    return _direct_tools, force_tools


def _collect_code_studio_tools(query: str, user_role: str = "student"):
    """Collect tools for the code studio capability lane."""
    _tools = []

    try:
        if settings.enable_code_execution and user_role == "admin":
            from app.engine.tools.code_execution_tools import get_code_execution_tools

            _tools.extend(get_code_execution_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Code execution tools unavailable: %s", _e)

    try:
        from app.engine.tools.chart_tools import get_chart_tools

        _tools.extend(get_chart_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Chart tools unavailable: %s", _e)

    try:
        from app.engine.tools.visual_tools import get_visual_tools

        _tools.extend(get_visual_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Visual tools unavailable: %s", _e)

    try:
        from app.engine.tools.output_generation_tools import get_output_generation_tools

        _tools.extend(get_output_generation_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Output generation tools unavailable: %s", _e)

    try:
        if (
            user_role == "admin"
            and settings.enable_browser_agent
            and settings.enable_privileged_sandbox
            and settings.sandbox_provider == "opensandbox"
            and settings.sandbox_allow_browser_workloads
        ):
            from app.engine.tools.browser_sandbox_tools import get_browser_sandbox_tools

            _tools.extend(get_browser_sandbox_tools())
    except Exception as _e:
        logger.debug("[CODE_STUDIO] Browser sandbox tools unavailable: %s", _e)

    visual_decision = resolve_visual_intent(query)
    _tools = filter_tools_for_role(_tools, user_role)
    _tools = filter_tools_for_visual_intent(
        _tools,
        visual_decision,
        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
    )
    force_tools = bool(_tools)
    return _tools, force_tools


def _needs_browser_snapshot(query: str) -> bool:
    """Detect requests that should prefer the browser sandbox over plain web search."""
    lowered = query.lower()
    normalized = _normalize_for_intent(query)
    has_url = "http://" in lowered or "https://" in lowered or "www." in lowered
    screenshot_signal = any(
        signal in normalized
        for signal in (
            "anh chup man hinh",
            "chup man hinh",
            "screenshot",
            "browser sandbox",
            "duyet web",
            "xem trang",
            "mo trang",
            "open page",
        )
    )
    inspect_signal = has_url and any(
        signal in normalized
        for signal in (
            "mo",
            "open",
            "ghe qua",
            "vao",
            "noi gi",
            "hien thi gi",
            "render",
            "trang do",
        )
    )
    return screenshot_signal or inspect_signal


def _direct_required_tool_names(query: str, user_role: str = "student") -> list[str]:
    """Return must-have direct tools inferred from the current query."""
    required: list[str] = []
    normalized = _normalize_for_intent(query)
    visual_decision = resolve_visual_intent(query)

    if _needs_datetime(query):
        required.append("tool_current_datetime")
    if _needs_news_search(query):
        required.append("tool_search_news")
    if _needs_legal_search(query):
        required.append("tool_search_legal")
    if _needs_web_search(query):
        if any(
            signal in normalized
            for signal in ("imo", "shipping", "maritime", "hang hai", "vinamarine", "cuc hang hai")
        ):
            required.append("tool_search_maritime")
        else:
            required.append("tool_web_search")
    if _needs_lms_query(query):
        required.append("tool_knowledge_search")
    # WAVE-001: browser_snapshot and execute_python removed from direct.
    # These capabilities now live exclusively in code_studio_agent.

    if visual_decision.force_tool and not _needs_analysis_tool(query):
        _structured = getattr(settings, "enable_structured_visuals", False)
        if visual_decision.mode == "mermaid" and _structured:
            required.append("tool_generate_mermaid")
        elif _structured:
            # Structured mode: ALL visual intents → multi-figure tool
            required.append("tool_generate_visual")
        elif visual_decision.mode in {"template", "inline_html", "app"}:
            required.append("tool_generate_rich_visual")

    return required


def _code_studio_required_tool_names(query: str, user_role: str = "student") -> list[str]:
    """Return must-have tools inferred for the code studio capability."""
    normalized = _normalize_for_intent(query)
    required: list[str] = []
    visual_decision = resolve_visual_intent(query)

    if any(token in normalized for token in ("html", "landing page", "website", "web app", "microsite")):
        required.append("tool_generate_html_file")

    if any(token in normalized for token in ("excel", "xlsx", "spreadsheet")):
        required.append("tool_generate_excel_file")

    if any(token in normalized for token in ("word", "docx", "report", "memo", "proposal")):
        required.append("tool_generate_word_document")

    if user_role == "admin" and settings.enable_code_execution and _needs_analysis_tool(query):
        required.append("tool_execute_python")

    if (
        user_role == "admin"
        and settings.enable_browser_agent
        and settings.enable_privileged_sandbox
        and settings.sandbox_provider == "opensandbox"
        and settings.sandbox_allow_browser_workloads
        and _needs_browser_snapshot(query)
    ):
        required.append("tool_browser_snapshot_url")

    if visual_decision.force_tool:
        _structured = getattr(settings, "enable_structured_visuals", False)
        if visual_decision.mode == "mermaid" and _structured:
            required.append("tool_generate_mermaid")
        elif _structured:
            # Structured mode: ALL visual intents → multi-figure tool
            required.append("tool_generate_visual")
        elif visual_decision.mode in {"template", "inline_html", "app"}:
            required.append("tool_generate_rich_visual")

    return required


def _build_visual_tool_runtime_metadata(state: dict, query: str) -> dict[str, Any] | None:
    """Provide visual intent metadata and patch defaults to the tool runtime layer."""
    visual_decision = resolve_visual_intent(query)
    metadata: dict[str, Any] = {}

    if visual_decision.force_tool and visual_decision.mode in {"template", "inline_html", "app", "mermaid"}:
        metadata.update({
            "visual_user_query": query,
            "visual_intent_mode": visual_decision.mode,
            "visual_intent_reason": visual_decision.reason,
            "visual_force_tool": True,
        })
        if visual_decision.visual_type:
            metadata["visual_requested_type"] = visual_decision.visual_type

    if not detect_visual_patch_request(query):
        return metadata or None

    visual_ctx = ((state.get("context") or {}).get("visual_context") or {})
    if not isinstance(visual_ctx, dict):
        return metadata or None

    preferred_session_id = str(visual_ctx.get("last_visual_session_id") or "").strip()
    preferred_visual_type = str(visual_ctx.get("last_visual_type") or "").strip()

    if not preferred_session_id:
        active_items = visual_ctx.get("active_inline_visuals")
        if isinstance(active_items, list):
            for item in active_items:
                if not isinstance(item, dict):
                    continue
                preferred_session_id = str(item.get("visual_session_id") or item.get("session_id") or "").strip()
                preferred_visual_type = preferred_visual_type or str(item.get("type") or "").strip()
                if preferred_session_id:
                    break

    if not preferred_session_id:
        return metadata or None

    metadata.update({
        "preferred_visual_operation": "patch",
        "preferred_visual_session_id": preferred_session_id,
        "preferred_visual_patch_hint": "followup-patch",
    })
    if preferred_visual_type:
        metadata["preferred_visual_type"] = preferred_visual_type
    return metadata or None


def _bind_direct_tools(llm, tools: list, force: bool):
    """Bind tools to LLM with optional forced calling.

    Sprint 154: Extracted from direct_response_node.

    Returns:
        tuple: (llm_with_tools, llm_auto)
            - llm_with_tools: LLM for first call (may force tool_choice="any")
            - llm_auto: LLM for follow-up calls (tool_choice="auto")
    """
    if tools:
        llm_auto = llm.bind_tools(tools)
        if force:
            llm_with_tools = llm.bind_tools(tools, tool_choice="any")
        else:
            llm_with_tools = llm_auto
    else:
        llm_with_tools = llm
        llm_auto = llm
    return llm_with_tools, llm_auto


def _build_direct_system_messages(
    state: AgentState,
    query: str,
    domain_name_vi: str,
    *,
    role_name: str = "direct_agent",
    tools_context_override: Optional[str] = None,
):
    """Build system prompt and message list for direct-style nodes.

    Sprint 154: Extracted from direct_response_node.

    Returns:
        list: LangChain messages [SystemMessage, ...history, HumanMessage]
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.prompts.prompt_loader import get_prompt_loader

    ctx = state.get("context", {})
    loader = get_prompt_loader()
    tools_ctx = tools_context_override or _build_direct_tools_context(
        settings,
        domain_name_vi,
        ctx.get("user_role", "student"),
    )
    system_prompt = loader.build_system_prompt(
        role=role_name,
        user_name=ctx.get("user_name"),
        is_follow_up=ctx.get("is_follow_up", False),
        pronoun_style=ctx.get("pronoun_style"),
        user_facts=ctx.get("user_facts", []),
        recent_phrases=ctx.get("recent_phrases", []),
        tools_context=tools_ctx,
        total_responses=ctx.get("total_responses", 0),
        name_usage_count=ctx.get("name_usage_count", 0),
        mood_hint=ctx.get("mood_hint", ""),
        user_id=state.get("user_id", "__global__"),
        personality_mode=ctx.get("personality_mode"),
        conversation_phase=ctx.get("conversation_phase"),  # Sprint 203
        # Sprint 220c: Resolved LMS external identity
        lms_external_id=ctx.get("lms_external_id"),
        lms_connector_id=ctx.get("lms_connector_id"),
    )

    # Sprint 222: Append graph-level host context (replaces per-agent injection)
    _host_prompt = state.get("host_context_prompt", "")
    if _host_prompt:
        system_prompt = system_prompt + "\n\n" + _host_prompt
    _visual_prompt = state.get("visual_context_prompt", "")
    if _visual_prompt:
        system_prompt = system_prompt + "\n\n" + _visual_prompt
    _widget_feedback_prompt = state.get("widget_feedback_prompt", "")
    if _widget_feedback_prompt:
        system_prompt = system_prompt + "\n\n" + _widget_feedback_prompt
    _capability_prompt = state.get("capability_context", "")
    if _capability_prompt:
        system_prompt = system_prompt + "\n\n## Capability Handbook\n" + _capability_prompt
    if role_name == "code_studio_agent":
        system_prompt = system_prompt + "\n\n" + _build_code_studio_delivery_contract(query)

    messages = [SystemMessage(content=system_prompt)]
    lc_messages = ctx.get("langchain_messages", [])
    if lc_messages:
        messages.extend(lc_messages[-10:])

    # Sprint 179: Multimodal content blocks when images are present
    images = ctx.get("images") or []
    if images:
        content_blocks = [{"type": "text", "text": query}]
        for img in images:
            if img.get("type") == "base64":
                content_blocks.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img['media_type']};base64,{img['data']}",
                        "detail": img.get("detail", "auto"),
                    }
                })
            elif img.get("type") == "url":
                content_blocks.append({
                    "type": "image_url",
                    "image_url": {
                        "url": img["data"],
                        "detail": img.get("detail", "auto"),
                    }
                })
        messages.append(HumanMessage(content=content_blocks))
    else:
        messages.append(HumanMessage(content=query))
    return messages


async def _execute_direct_tool_rounds(
    llm_with_tools, llm_auto, messages: list, tools: list, push_event,
    runtime_context_base=None,
    max_rounds: int = 3,
    query: str = "",
    state: Optional[AgentState] = None,
):
    """Execute multi-round tool calling loop for direct response.

    Sprint 154: Extracted from direct_response_node.
    Gemini often calls tools sequentially (datetime → web_search → answer).

    Returns:
        tuple: (AIMessage, messages, tool_call_events) — final response, messages, and
               structured tool events for downstream preview emission (Sprint 166).
    """
    from langchain_core.messages import ToolMessage as _TM

    tool_call_events: list[dict] = []
    state = state or {}

    _opening_cue = _infer_direct_reasoning_cue(query, state, [])
    _opening_beat = await _render_reasoning(
        state=state,
        node="direct",
        phase="attune",
        cue=_opening_cue,
        next_action="Bắt nhịp rồi quyết định có cần kiểm thêm gì không.",
        style_tags=["direct", "opening"],
    )
    await push_event({
        "type": "thinking_start",
        "content": _opening_beat.label,
        "node": "direct",
        "summary": _opening_beat.summary,
        "details": {"phase": _opening_beat.phase},
    })
    await push_event({
        "type": "thinking_delta",
        "content": _opening_beat.summary,
        "node": "direct",
    })

    llm_response = await llm_with_tools.ainvoke(messages)
    _tc = getattr(llm_response, 'tool_calls', [])
    logger.warning("[DIRECT] LLM response: tool_calls=%d, content_len=%d",
                   len(_tc) if _tc else 0, len(str(llm_response.content)))
    await push_event({
        "type": "thinking_end",
        "content": "",
        "node": "direct",
    })

    for _tool_round in range(max_rounds):
        if not (tools and hasattr(llm_response, 'tool_calls') and llm_response.tool_calls):
            break
        _round_tool_names = [
            str(tc.get("name", "unknown"))
            for tc in llm_response.tool_calls
            if tc.get("name")
        ]
        _round_cue = _infer_direct_reasoning_cue(query, state, _round_tool_names)
        _round_phase = "verify" if _tool_round > 0 else "ground"
        _round_beat = await _render_reasoning(
            state=state,
            node="direct",
            phase=_round_phase,
            cue=_round_cue,
            tool_names=_round_tool_names,
            next_action="Mở các công cụ cần thiết rồi gạn lại điều đáng tin nhất.",
            observations=[f"Sắp gọi {len(_round_tool_names)} công cụ trong vòng này."],
            style_tags=["direct", "tooling"],
        )
        await push_event({
            "type": "thinking_start",
            "content": _round_beat.label,
            "node": "direct",
            "summary": _round_beat.summary,
            "details": {"phase": _round_beat.phase},
        })
        if _round_beat.summary:
            await push_event({
                "type": "thinking_delta",
                "content": _round_beat.summary,
                "node": "direct",
            })
        messages.append(llm_response)
        visual_session_ids: list[str] = []
        active_visual_session_ids = _collect_active_visual_session_ids(state)
        for tc in llm_response.tool_calls:
            _tc_id = tc.get("id", f"tc_{_tool_round}")
            _tc_name = tc.get("name", "unknown")
            await push_event({
                "type": "tool_call",
                "content": {"name": _tc_name, "args": tc.get("args", {}), "id": _tc_id},
                "node": "direct",
            })
            tool_call_events.append({
                "type": "call", "name": _tc_name,
                "args": tc.get("args", {}), "id": _tc_id,
            })
            matched = get_tool_by_name(tools, str(_tc_name).strip())
            try:
                if matched:
                    result = await invoke_tool_with_runtime(
                        matched,
                        tc["args"],
                        tool_name=_tc_name,
                        runtime_context_base=runtime_context_base,
                        tool_call_id=_tc_id,
                        query_snippet=str(tc.get("args", {}).get("query", ""))[:100],
                        prefer_async=False,
                        run_sync_in_thread=True,
                    )
                else:
                    result = "Unknown tool"
            except Exception as _te:
                logger.warning("[DIRECT] Tool %s failed: %s", _tc_name, _te)
                result = "Tool unavailable"
            # Sprint 205: Record tool usage for Skill↔Tool bridge
            await push_event({
                "type": "tool_result",
                "content": {
                    "name": _tc_name,
                    "result": _summarize_tool_result_for_stream(_tc_name, result),
                    "id": _tc_id,
                },
                "node": "direct",
            })
            _emitted_visual_session_ids, _disposed_visual_session_ids = await _maybe_emit_visual_event(
                push_event=push_event,
                tool_name=_tc_name,
                tool_call_id=_tc_id,
                result=result,
                node="direct",
                tool_call_events=tool_call_events,
                previous_visual_session_ids=active_visual_session_ids,
            )
            if _emitted_visual_session_ids:
                visual_session_ids.extend(_emitted_visual_session_ids)
                active_visual_session_ids = list(dict.fromkeys(_emitted_visual_session_ids))
            elif _disposed_visual_session_ids:
                active_visual_session_ids = [
                    session_id
                    for session_id in active_visual_session_ids
                    if session_id not in set(_disposed_visual_session_ids)
                ]
            _reflection = await _build_direct_tool_reflection(state, _tc_name, result)
            if _reflection:
                await push_event({
                    "type": "thinking_delta",
                    "content": f"\n\n{_reflection}",
                    "node": "direct",
                })
            # Sprint 166: Store full result for preview extraction
            tool_call_events.append({
                "type": "result", "name": _tc_name,
                "result": str(result), "id": _tc_id,
            })
            messages.append(_TM(content=str(result), tool_call_id=_tc_id))
        await _emit_visual_commit_events(
            push_event=push_event,
            node="direct",
            visual_session_ids=visual_session_ids,
            tool_call_events=tool_call_events,
        )
        await push_event({
            "type": "thinking_end",
            "content": "",
            "node": "direct",
        })
        llm_response = await llm_auto.ainvoke(messages)
        if tools and hasattr(llm_response, 'tool_calls') and llm_response.tool_calls:
            _transition = await _render_reasoning(
                state=state,
                node="direct",
                phase="act",
                cue=_round_cue,
                tool_names=_round_tool_names,
                next_action="Kiểm chéo thêm một lượt rồi mới chốt.",
                observations=["Đã có dữ liệu mới nhưng vẫn cần gạn thêm."],
                style_tags=["direct", "transition"],
            )
            await push_event({
                "type": "action_text",
                "content": _transition.action_text or _transition.summary,
                "node": "direct",
            })

    _synthesis_cue = _infer_direct_reasoning_cue(
        query,
        state,
        [
            str(event.get("name", ""))
            for event in tool_call_events
            if event.get("type") == "call"
        ],
    )
    _synthesis_beat = await _render_reasoning(
        state=state,
        node="direct",
        phase="synthesize",
        cue=_synthesis_cue,
        tool_names=[
            str(event.get("name", ""))
            for event in tool_call_events
            if event.get("type") == "call"
        ],
        next_action="Khâu dữ liệu lại thành một câu trả lời đủ chắc và đủ gần.",
        style_tags=["direct", "synthesis"],
    )

    if tool_call_events:
        await push_event({
            "type": "action_text",
            "content": _synthesis_beat.action_text or _synthesis_beat.summary,
            "node": "direct",
        })
        await push_event({
            "type": "thinking_start",
            "content": _synthesis_beat.label,
            "node": "direct",
            "summary": _synthesis_beat.summary,
            "details": {"phase": _synthesis_beat.phase},
        })
        await push_event({
            "type": "thinking_delta",
            "content": _synthesis_beat.summary,
            "node": "direct",
        })
        await push_event({
            "type": "thinking_end",
            "content": "",
            "node": "direct",
        })
    else:
        await push_event({
            "type": "action_text",
            "content": _synthesis_beat.action_text or _synthesis_beat.summary,
            "node": "direct",
        })
        await push_event({
            "type": "thinking_start",
            "content": _synthesis_beat.label,
            "node": "direct",
            "summary": _synthesis_beat.summary,
            "details": {"phase": _synthesis_beat.phase},
        })
        await push_event({
            "type": "thinking_delta",
            "content": _synthesis_beat.summary,
            "node": "direct",
        })
        await push_event({
            "type": "thinking_end",
            "content": "",
            "node": "direct",
        })

    # Legacy widget fallback: only auto-inject for non-structured turns.
    llm_response = _inject_widget_blocks_from_tool_results(
        llm_response,
        tool_call_events,
        query=query,
        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
    )

    return llm_response, messages, tool_call_events


def _extract_direct_response(llm_response, messages: list):
    """Extract response text, thinking content, and tools used from LLM result.

    Sprint 154: Extracted from direct_response_node.

    Returns:
        tuple: (response_text, thinking_content, tools_used_list)
    """
    from app.services.output_processor import extract_thinking_from_response
    text_content, thinking_content = extract_thinking_from_response(llm_response.content)
    response = text_content.strip()

    tools_used_names = set()
    for m in messages:
        if hasattr(m, 'tool_calls') and m.tool_calls:
            for tc in m.tool_calls:
                tools_used_names.add(tc.get("name", "unknown"))
    tools_used = [{"name": n} for n in sorted(tools_used_names)] if tools_used_names else []

    return response, thinking_content, tools_used


_DIRECT_TIME_TOOLS = {"tool_current_datetime"}
_DIRECT_NEWS_TOOLS = {"tool_search_news"}
_DIRECT_LEGAL_TOOLS = {"tool_search_legal"}
_DIRECT_WEB_TOOLS = {
    "tool_web_search",
    "tool_search_maritime",
    "tool_knowledge_search",
}
_DIRECT_MEMORY_TOOLS = {"tool_character_read", "tool_character_note"}
_DIRECT_BROWSER_TOOLS = {"tool_browser_snapshot_url"}
_DIRECT_ANALYSIS_PREFIXES = ("tool_execute_python", "tool_chart_", "tool_plot_")
_DIRECT_LMS_PREFIX = "tool_lms_"
_CODE_STUDIO_ACTION_JSON_RE = re.compile(
    r"""
    \{
        \s*"action"\s*:\s*"[^"]+"
        (?:
            \s*,\s*"action_input"\s*:\s*
            (?:
                "(?:\\.|[^"])*"
                |
                \{.*?\}
                |
                \[.*?\]
                |
                [^}\n]+
            )
        )?
        (?:
            \s*,\s*"thought"\s*:\s*"(?:\\.|[^"])*"
        )?
        \s*
    \}
    """,
    re.DOTALL | re.VERBOSE,
)
_CODE_STUDIO_SANDBOX_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(sandbox:[^)]+\)", re.IGNORECASE)
_CODE_STUDIO_SANDBOX_LINK_RE = re.compile(r"\[[^\]]+\]\(sandbox:[^)]+\)", re.IGNORECASE)
_CODE_STUDIO_SANDBOX_PATH_RE = re.compile(r"(?:sandbox:[^\s)]+|/(?:mnt/data|workspace)/[^\s)]+)")


def _direct_tool_names(items: list[dict] | None) -> list[str]:
    """Extract distinct tool names from tool usage payloads."""
    names: list[str] = []
    seen: set[str] = set()
    for item in items or []:
        name = ""
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
        elif item:
            name = str(item).strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names


_DOCUMENT_STUDIO_TOOLS = frozenset({
    "tool_generate_html_file",
    "tool_generate_excel_file",
    "tool_generate_word_document",
})
_DOCUMENT_STUDIO_EXTENSIONS = frozenset({".html", ".htm", ".xlsx", ".docx"})


def _extract_code_studio_artifact_names(tool_call_events: list[dict] | None) -> list[str]:
    """Extract artifact filenames from tool result events.

    Supports two result formats:
    - tool_execute_python: "Artifacts:\\n- chart.png (image/png) -> /path..."
    - output_generation_tools: JSON {"filename": "report.docx", "format": "docx", ...}

    WAVE-003: added JSON parsing for docx/xlsx/html tool results.
    """
    import json as _json

    names: list[str] = []
    seen: set[str] = set()

    for event in tool_call_events or []:
        if not isinstance(event, dict) or event.get("type") != "result":
            continue

        result = str(event.get("result", ""))
        tool_name = str(event.get("name", "")).strip()

        # Path 1: JSON result from output_generation_tools
        if tool_name in _DOCUMENT_STUDIO_TOOLS and result.strip().startswith("{"):
            try:
                parsed = _json.loads(result)
                filename = str(parsed.get("filename", "")).strip()
                if filename and any(filename.lower().endswith(ext) for ext in _DOCUMENT_STUDIO_EXTENSIONS):
                    if filename not in seen:
                        seen.add(filename)
                        names.append(filename)
                    continue
            except Exception:
                pass  # fall through to line-based parsing

        # Path 2: tool_execute_python "Artifacts:\n- file.png ..." format
        for line in result.splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            candidate = stripped[2:].split(" (", 1)[0].strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                names.append(candidate)

    return names


def _is_document_studio_tool_error(tool_name: str, result: object) -> bool:
    """Detect failed document studio tool calls (JSON error response).

    WAVE-003: terminal failure detection for output_generation_tools.
    """
    import json as _json

    if str(tool_name).strip() not in _DOCUMENT_STUDIO_TOOLS:
        return False
    result_str = str(result or "").strip()
    if not result_str.startswith("{"):
        return False
    try:
        parsed = _json.loads(result_str)
        return "error" in parsed
    except Exception:
        return False


def _build_code_studio_synthesis_observations(tool_call_events: list[dict] | None) -> list[str]:
    """Build synthesis observations from tool call results.

    WAVE-003: document studio tools (xlsx/docx/html) now produce human-readable observations
    instead of raw JSON first-lines. Artifact names are populated for all three tool families.
    """
    import json as _json

    observations: list[str] = []
    artifact_names = _extract_code_studio_artifact_names(tool_call_events)
    if artifact_names:
        observations.append(
            "Da tao artifact co the mo ra ngay: " + ", ".join(artifact_names[:3])
        )

    for event in tool_call_events or []:
        if not isinstance(event, dict) or event.get("type") != "result":
            continue
        tool_name = str(event.get("name", "")).strip()
        result_text = str(event.get("result", "")).strip()
        if not result_text:
            continue

        # Path A: tool_execute_python "Artifacts:" format
        if "Artifacts:" in result_text:
            if tool_name:
                observations.append(f"{tool_name} vua tra ve dau ra huu hinh.")
            continue

        # Path B: output_generation_tools JSON format (WAVE-003)
        if tool_name in _DOCUMENT_STUDIO_TOOLS and result_text.startswith("{"):
            try:
                parsed = _json.loads(result_text)
                if "error" not in parsed:
                    filename = parsed.get("filename", "")
                    fmt = parsed.get("format", tool_name)
                    if filename:
                        observations.append(
                            f"Da tao file {fmt.upper()} that: `{filename}` — san sang tai xuong hoac mo ngay."
                        )
                else:
                    observations.append(
                        f"{tool_name} gap loi: {str(parsed['error'])[:120]}"
                    )
                continue
            except Exception:
                pass  # fall through to generic first_line

        # Path C: generic first_line (other tools)
        first_line = next(
            (line.strip() for line in result_text.splitlines() if line.strip()),
            "",
        )
        if first_line and not first_line.startswith("{"):
            prefix = f"{tool_name}: " if tool_name else ""
            observations.append(f"{prefix}{first_line[:180]}")

        if len(observations) >= 4:
            break

    return observations[:4]


def _build_code_studio_delivery_contract(query: str) -> str:
    """Role-local answer contract for delivery-first technical responses.

    WAVE-002: added html/landing-page specific delivery line.
    """
    normalized = _normalize_for_intent(query)
    is_chart_request = any(
        token in normalized for token in ("bieu do", "chart", "plot", "matplotlib", "seaborn", "png", "svg")
    )
    is_html_request = any(
        token in normalized for token in ("html", "landing page", "website", "web app", "microsite", "trang web")
    )

    lines = [
        "## CODE STUDIO DELIVERY CONTRACT:",
        "- Voi tac vu ky thuat, mo dau answer bang ket qua da tao hoac da xac nhan. Khong mo dau bang loi chao, tu gioi thieu, hay small talk.",
        "- Khi vua tao artifact, neu ro ten file, loai san pham, va dieu nguoi dung co the mo ra ngay luc nay.",
        "- Neu yeu cau chua du du lieu cu the, tao mot demo trung tinh phu hop voi task va noi ro do la demo. Khong bien no thanh lore ca nhan cua Wiii.",
        "- Khong dua nhan vat phu, thu cung ao, catchphrase, hay chi tiet de thuong khong lien quan vao output ky thuat neu user khong yeu cau.",
        "- Uu tien 3 phan theo thu tu: da tao gi, no dung de lam gi, nguoi dung co the lam gi tiep theo.",
    ]
    if is_chart_request:
        lines.append(
            "- Voi yeu cau bieu do/chart mo ho, uu tien tao mot chart demo trung tinh va giao lai file PNG that (neu co sandbox), hoac Mermaid SVG khi khong co sandbox."
        )
    if is_html_request:
        lines.append(
            "- Voi yeu cau landing page/HTML, tao file HTML that va mo ta ro nhung gi nguoi dung co the xem/mo ngay."
        )
    return "\n".join(lines)


_CODE_STUDIO_CHATTER_TOKENS = (
    "rat vui duoc gap",
    "minh la wiii",
    "toi la wiii",
    "bong",
    "meo ao",
    "meo meo",
    "catchphrase",
)


def _is_code_studio_chatter_paragraph(paragraph: str) -> bool:
    """Detect social/persona chatter that should not lead a technical delivery."""
    normalized = _normalize_for_intent(paragraph)
    if not normalized:
        return False
    if any(token in normalized for token in _CODE_STUDIO_CHATTER_TOKENS):
        return True
    if normalized.startswith(("chao ", "xin chao", "hello ", "hi ", "alo ")):
        return True
    return False


def _strip_code_studio_chatter(cleaned: str) -> str:
    """Remove greeting/lore paragraphs when better technical paragraphs exist."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()]
    if not paragraphs:
        return cleaned

    filtered = [part for part in paragraphs if not _is_code_studio_chatter_paragraph(part)]
    if filtered and len(filtered) < len(paragraphs):
        return "\n\n".join(filtered).strip()
    return cleaned


def _ensure_code_studio_delivery_lede(cleaned: str, tool_call_events: list[dict] | None = None) -> str:
    """Ensure the answer starts from the artifact/result, not from social filler."""
    artifact_names = _extract_code_studio_artifact_names(tool_call_events)
    if not artifact_names:
        return cleaned

    first_paragraph = next((part.strip() for part in re.split(r"\n\s*\n", cleaned) if part.strip()), "")
    normalized_first = _normalize_for_intent(first_paragraph)
    normalized_artifact = _normalize_for_intent(artifact_names[0])
    if any(
        token in normalized_first
        for token in ("da tao", "da hoan thanh", "da xac nhan", "artifact", normalized_artifact)
    ):
        return cleaned

    lede = f"Minh da tao xong `{artifact_names[0]}` va gan kem artifact ngay ben duoi."
    return f"{lede}\n\n{cleaned}".strip()


def _sanitize_code_studio_response(
    response: str,
    tool_call_events: list[dict] | None = None,
) -> str:
    cleaned = response or ""
    had_raw_payload = False

    for pattern in (
        _CODE_STUDIO_ACTION_JSON_RE,
        _CODE_STUDIO_SANDBOX_IMAGE_RE,
        _CODE_STUDIO_SANDBOX_LINK_RE,
        _CODE_STUDIO_SANDBOX_PATH_RE,
    ):
        updated = pattern.sub("", cleaned)
        if updated != cleaned:
            had_raw_payload = True
            cleaned = updated

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    cleaned = _strip_code_studio_chatter(cleaned)
    cleaned = _ensure_code_studio_delivery_lede(cleaned, tool_call_events)

    if had_raw_payload:
        artifact_names = _extract_code_studio_artifact_names(tool_call_events)
        note = (
            f"File `{artifact_names[0]}` da duoc tao va gan kem trong artifact ngay ben duoi."
            if artifact_names
            else "Artifact ky thuat da duoc tao va gan kem ngay ben duoi."
        )
        if note not in cleaned:
            cleaned = f"{cleaned}\n\n{note}".strip()

    return cleaned


def _is_terminal_code_studio_tool_error(tool_name: str, result: object) -> bool:
    """Detect tool failures that should stop the code-studio loop immediately.

    WAVE-003: also catches document studio JSON error responses (xlsx/docx/html).
    """
    normalized_name = str(tool_name or "").strip().lower()

    # Sandbox tools: text-based failure messages
    if normalized_name in {"tool_execute_python", "tool_browser_snapshot_url"}:
        normalized_result = _normalize_for_intent(str(result or ""))
        if not normalized_result:
            return False
        if "tool unavailable" in normalized_result:
            return True
        return (
            "opensandbox execution failed" in normalized_result
            and "network connectivity error" in normalized_result
        )

    # Document studio tools: JSON error response
    if normalized_name in _DOCUMENT_STUDIO_TOOLS:
        return _is_document_studio_tool_error(normalized_name, result)

    return False


def _build_code_studio_terminal_failure_response(
    query: str,
    tool_call_events: list[dict] | None = None,
) -> str:
    """Create a short, delivery-first answer when sandbox execution is terminally unavailable."""
    artifact_names = _extract_code_studio_artifact_names(tool_call_events)
    normalized = _normalize_for_intent(query)
    is_chart_request = any(
        token in normalized for token in ("bieu do", "chart", "plot", "png", "matplotlib", "seaborn")
    )

    if artifact_names:
        return (
            f"Minh da bat dau chuan bi `{artifact_names[0]}`, nhung sandbox dang gap loi ket noi nen chua the "
            "hoan tat artifact nay o turn hien tai. Khi kenh thuc thi on dinh tro lai, minh co the chay lai va "
            "gui ket qua ngay."
        )

    if is_chart_request:
        return (
            "Minh chua the tao file PNG that luc nay vi sandbox dang gap loi ket noi. "
            "Khi kenh thuc thi on dinh tro lai, minh co the chay lai va gui cho cau artifact bieu do ngay."
        )

    return (
        "Minh da den buoc thuc thi, nhung sandbox dang gap loi ket noi nen chua the tao ket qua that ngay luc nay. "
        "Khi kenh nay on dinh tro lai, minh co the chay lai va giao artifact hoan chinh cho cau."
    )


def _has_prefixed_tool(tool_names: list[str], prefixes: tuple[str, ...]) -> bool:
    """Check whether any tool starts with one of the provided prefixes."""
    return any(name.startswith(prefix) for name in tool_names for prefix in prefixes)


def _uses_lms_tool(tool_names: list[str]) -> bool:
    """Check whether direct reasoning involved LMS tools."""
    return any(name.startswith(_DIRECT_LMS_PREFIX) for name in tool_names)


def _infer_direct_reasoning_cue(
    query: str,
    state: AgentState,
    tool_names: list[str] | None = None,
) -> str:
    """Map the current direct path into a stable reasoning cue."""
    tool_names = tool_names or []
    tool_set = set(tool_names)
    routing_meta = state.get("routing_metadata") or {}
    intent = str(routing_meta.get("intent", "")).strip().lower()
    context = state.get("context") or {}

    categories = 0
    categories += int(bool(tool_set & _DIRECT_TIME_TOOLS))
    categories += int(bool(tool_set & _DIRECT_NEWS_TOOLS))
    categories += int(bool(tool_set & _DIRECT_LEGAL_TOOLS))
    categories += int(bool(tool_set & _DIRECT_WEB_TOOLS))
    categories += int(_uses_lms_tool(tool_names))
    categories += int(bool(tool_set & _DIRECT_MEMORY_TOOLS))
    categories += int(bool(tool_set & _DIRECT_BROWSER_TOOLS))
    categories += int(_has_prefixed_tool(tool_names, _DIRECT_ANALYSIS_PREFIXES))
    if categories > 1:
        return "multi_source"

    if context.get("images"):
        return "visual"
    if "tool_current_datetime" in tool_set or _needs_datetime(query):
        return "datetime"
    if tool_set & _DIRECT_NEWS_TOOLS or _needs_news_search(query):
        return "news"
    if tool_set & _DIRECT_LEGAL_TOOLS or _needs_legal_search(query):
        return "legal"
    if tool_set & _DIRECT_WEB_TOOLS or _needs_web_search(query):
        return "web"
    if _uses_lms_tool(tool_names) or _needs_lms_query(query):
        return "lms"
    if tool_set & _DIRECT_MEMORY_TOOLS:
        return "memory"
    if tool_set & _DIRECT_BROWSER_TOOLS:
        return "browser"
    if _has_prefixed_tool(tool_names, _DIRECT_ANALYSIS_PREFIXES):
        return "analysis"
    if intent == "personal":
        return "personal"
    if intent == "social":
        return "social"
    if intent == "off_topic":
        return "off_topic"
    return "general"


def _infer_code_studio_reasoning_cue(
    query: str,
    tool_names: list[str] | None = None,
) -> str:
    """Map code-studio requests into stable reasoning cues."""
    tool_names = tool_names or []
    normalized = _normalize_for_intent(query)
    tool_set = set(tool_names)

    if "tool_browser_snapshot_url" in tool_set or _needs_browser_snapshot(query):
        return "browser"
    if "tool_generate_html_file" in tool_set or any(
        token in normalized for token in ("html", "landing page", "website", "web app", "microsite")
    ):
        return "html"
    if "tool_generate_excel_file" in tool_set or any(
        token in normalized for token in ("excel", "xlsx", "spreadsheet")
    ):
        return "spreadsheet"
    if "tool_generate_word_document" in tool_set or any(
        token in normalized for token in ("word", "docx", "memo", "proposal", "report")
    ):
        return "document"
    if "tool_execute_python" in tool_set or _needs_analysis_tool(query):
        if any(token in normalized for token in ("bieu do", "chart", "plot", "matplotlib", "seaborn", "png", "svg")):
            return "chart"
        return "python"
    return "build"


def _infer_reasoning_cue(
    node_name: str,
    query: str,
    state: AgentState,
    tool_names: list[str] | None = None,
) -> str:
    """Resolve reasoning cue per capability node."""
    if node_name == "code_studio_agent":
        return _infer_code_studio_reasoning_cue(query, tool_names)
    return _infer_direct_reasoning_cue(query, state, tool_names)


def _node_style_prefix(node_name: str) -> str:
    """Map graph node name to narrator style prefix."""
    if node_name == "code_studio_agent":
        return "code-studio"
    return node_name


async def _build_direct_reasoning_summary(
    query: str,
    state: AgentState,
    tool_names: list[str] | None = None,
) -> str:
    """Build safe, human-readable direct reasoning without exposing raw CoT."""
    cue = _infer_direct_reasoning_cue(query, state, tool_names)
    opening = await _render_reasoning(
        state=state,
        node="direct",
        phase="attune",
        cue=cue,
        tool_names=tool_names,
        style_tags=["direct", "summary"],
    )
    closing = await _render_reasoning(
        state=state,
        node="direct",
        phase="synthesize",
        cue=cue,
        tool_names=tool_names,
        style_tags=["direct", "summary"],
    )
    if closing.summary and closing.summary != opening.summary:
        return f"{opening.summary}\n\n{closing.summary}"
    return opening.summary


async def _build_direct_round_label(state: AgentState, tool_names: list[str], round_index: int) -> str:
    """Choose a compact label for a direct reasoning block."""
    cue = _infer_direct_reasoning_cue("", {}, tool_names)
    beat = await _render_reasoning(
        state=state,
        node="direct",
        phase="verify" if round_index > 0 else "ground",
        cue=cue,
        tool_names=tool_names,
    )
    return beat.label


async def _build_direct_tool_reflection(
    state: AgentState,
    tool_name: str,
    result: object,
) -> str:
    """Summarize what a direct tool result means for the ongoing answer."""
    reflection = await _render_reasoning(
        state=state,
        node="direct",
        phase="act",
        cue=_infer_direct_reasoning_cue(state.get("query", ""), state, [tool_name]),
        tool_names=[tool_name],
        result=result,
        next_action="Lồng kết quả vừa có vào câu trả lời đang hình thành.",
        style_tags=["direct", "tool_reflection"],
    )
    return reflection.summary


async def _build_direct_synthesis_summary(
    query: str,
    state: AgentState,
    tool_names: list[str] | None = None,
) -> str:
    """Summarize the final consolidation step for direct responses."""
    cue = _infer_direct_reasoning_cue(query, state, tool_names)
    beat = await _render_reasoning(
        state=state,
        node="direct",
        phase="synthesize",
        cue=cue,
        tool_names=tool_names,
        style_tags=["direct", "summary"],
    )
    return beat.summary


async def _build_code_studio_reasoning_summary(
    query: str,
    state: AgentState,
    tool_names: list[str] | None = None,
) -> str:
    """Build safe code-studio reasoning summary for UI display."""
    cue = _infer_code_studio_reasoning_cue(query, tool_names)
    opening = await _render_reasoning(
        state=state,
        node="code_studio_agent",
        phase="attune",
        cue=cue,
        tool_names=tool_names,
        style_tags=["code-studio", "summary"],
    )
    closing = await _render_reasoning(
        state=state,
        node="code_studio_agent",
        phase="synthesize",
        cue=cue,
        tool_names=tool_names,
        style_tags=["code-studio", "summary"],
    )
    if closing.summary and closing.summary.strip() and closing.summary != opening.summary:
        return closing.summary
    return opening.summary


def _normalize_reasoning_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _code_studio_delta_chunks(beat) -> list[str]:
    summary_norm = _normalize_reasoning_text(getattr(beat, "summary", ""))
    chunks: list[str] = []
    for chunk in getattr(beat, "delta_chunks", []) or []:
        if not chunk:
            continue
        chunk_norm = _normalize_reasoning_text(chunk)
        if summary_norm and (chunk_norm == summary_norm or chunk_norm in summary_norm or summary_norm in chunk_norm):
            continue
        if chunks and _normalize_reasoning_text(chunks[-1]) == chunk_norm:
            continue
        chunks.append(chunk)
    return chunks


async def _build_code_studio_tool_reflection(
    state: AgentState,
    tool_name: str,
    result: object,
) -> str:
    """Summarize what a code-studio tool result means for the current build."""
    reflection = await _render_reasoning(
        state=state,
        node="code_studio_agent",
        phase="act",
        cue=_infer_code_studio_reasoning_cue(state.get("query", ""), [tool_name]),
        tool_names=[tool_name],
        result=result,
        next_action="Lua ket qua moi vao dau ra ky thuat dang duoc che tac.",
        style_tags=["code-studio", "tool_reflection"],
    )
    return reflection.summary


async def _execute_code_studio_tool_rounds(
    llm_with_tools,
    llm_auto,
    messages: list,
    tools: list,
    push_event,
    runtime_context_base=None,
    max_rounds: int = 3,
    query: str = "",
    state: Optional[AgentState] = None,
):
    """Execute multi-round tool calling loop for the code studio capability."""
    from langchain_core.messages import AIMessage as _AM, ToolMessage as _TM

    tool_call_events: list[dict] = []
    state = state or {}

    llm_response = await llm_with_tools.ainvoke(messages)

    for _tool_round in range(max_rounds):
        if not (tools and hasattr(llm_response, "tool_calls") and llm_response.tool_calls):
            break

        _round_tool_names = [
            str(tc.get("name", "unknown"))
            for tc in llm_response.tool_calls
            if tc.get("name")
        ]
        _round_cue = _infer_code_studio_reasoning_cue(query, _round_tool_names)
        _round_phase = "verify" if _tool_round > 0 else "ground"
        _round_beat = await _render_reasoning(
            state=state,
            node="code_studio_agent",
            phase=_round_phase,
            cue=_round_cue,
            tool_names=_round_tool_names,
            next_action="Mo cong cu can thiet roi xac minh output co the dung that.",
            observations=[f"Sap goi {len(_round_tool_names)} cong cu trong vong nay."],
            style_tags=["code-studio", "tooling"],
        )
        await push_event({
            "type": "thinking_start",
            "content": _round_beat.label,
            "node": "code_studio_agent",
            "summary": _round_beat.summary,
            "details": {"phase": _round_beat.phase},
        })
        for _chunk in _code_studio_delta_chunks(_round_beat):
            await push_event({
                "type": "thinking_delta",
                "content": _chunk,
                "node": "code_studio_agent",
            })
        if _round_beat.action_text:
            await push_event({
                "type": "action_text",
                "content": _round_beat.action_text,
                "node": "code_studio_agent",
            })

        messages.append(llm_response)
        _terminal_failure_detected = False
        visual_session_ids: list[str] = []
        active_visual_session_ids = _collect_active_visual_session_ids(state)
        for tc in llm_response.tool_calls:
            _tc_id = tc.get("id", f"tc_{_tool_round}")
            _tc_name = tc.get("name", "unknown")
            await push_event({
                "type": "tool_call",
                "content": {"name": _tc_name, "args": tc.get("args", {}), "id": _tc_id},
                "node": "code_studio_agent",
            })
            tool_call_events.append({
                "type": "call",
                "name": _tc_name,
                "args": tc.get("args", {}),
                "id": _tc_id,
            })
            matched = get_tool_by_name(tools, str(_tc_name).strip())
            try:
                if matched:
                    result = await invoke_tool_with_runtime(
                        matched,
                        tc["args"],
                        tool_name=_tc_name,
                        runtime_context_base=runtime_context_base,
                        tool_call_id=_tc_id,
                        query_snippet=str(tc.get("args", {}).get("query", ""))[:100],
                        prefer_async=False,
                        run_sync_in_thread=True,
                    )
                else:
                    result = "Unknown tool"
            except Exception as _te:
                logger.warning("[CODE_STUDIO] Tool %s failed: %s", _tc_name, _te)
                result = "Tool unavailable"

            await push_event({
                "type": "tool_result",
                "content": {
                    "name": _tc_name,
                    "result": _summarize_tool_result_for_stream(_tc_name, result),
                    "id": _tc_id,
                },
                "node": "code_studio_agent",
            })
            _emitted_visual_session_ids, _disposed_visual_session_ids = await _maybe_emit_visual_event(
                push_event=push_event,
                tool_name=_tc_name,
                tool_call_id=_tc_id,
                result=result,
                node="code_studio_agent",
                tool_call_events=tool_call_events,
                previous_visual_session_ids=active_visual_session_ids,
            )
            if _emitted_visual_session_ids:
                visual_session_ids.extend(_emitted_visual_session_ids)
                active_visual_session_ids = list(dict.fromkeys(_emitted_visual_session_ids))
            elif _disposed_visual_session_ids:
                active_visual_session_ids = [
                    session_id
                    for session_id in active_visual_session_ids
                    if session_id not in set(_disposed_visual_session_ids)
                ]
            _reflection = await _build_code_studio_tool_reflection(state, _tc_name, result)
            if _reflection:
                await push_event({
                    "type": "thinking_delta",
                    "content": f"\n\n{_reflection}",
                    "node": "code_studio_agent",
                })
            tool_call_events.append({
                "type": "result",
                "name": _tc_name,
                "result": str(result),
                "id": _tc_id,
            })
            messages.append(_TM(content=str(result), tool_call_id=_tc_id))
            if _is_terminal_code_studio_tool_error(_tc_name, result):
                _terminal_failure_detected = True

        await _emit_visual_commit_events(
            push_event=push_event,
            node="code_studio_agent",
            visual_session_ids=visual_session_ids,
            tool_call_events=tool_call_events,
        )
        await push_event({
            "type": "thinking_end",
            "content": "",
            "node": "code_studio_agent",
        })
        if _terminal_failure_detected:
            llm_response = _AM(
                content=_build_code_studio_terminal_failure_response(query, tool_call_events)
            )
            break
        llm_response = await llm_auto.ainvoke(messages)
        if tools and hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
            _transition = await _render_reasoning(
                state=state,
                node="code_studio_agent",
                phase="act",
                cue=_round_cue,
                tool_names=_round_tool_names,
                next_action="Rut gon thanh mot buoc thuc hien tiep theo roi moi chot.",
                observations=["Da co them ket qua moi va dang can khau lai."],
                style_tags=["code-studio", "transition"],
            )
            await push_event({
                "type": "action_text",
                "content": _transition.action_text or _transition.summary,
                "node": "code_studio_agent",
            })

    _synthesis_cue = _infer_code_studio_reasoning_cue(
        query,
        [
            str(event.get("name", ""))
            for event in tool_call_events
            if event.get("type") == "call"
        ],
    )
    _synthesis_observations = _build_code_studio_synthesis_observations(tool_call_events)
    _synthesis_beat = await _render_reasoning(
        state=state,
        node="code_studio_agent",
        phase="synthesize",
        cue=_synthesis_cue,
        tool_names=[
            str(event.get("name", ""))
            for event in tool_call_events
            if event.get("type") == "call"
        ],
        next_action="Noi ro da tao xong san pham nao, no dung de lam gi, va nguoi dung co the mo artifact ay ngay luc nay.",
        observations=_synthesis_observations,
        style_tags=["code-studio", "synthesis"],
    )
    await push_event({
        "type": "thinking_start",
        "content": _synthesis_beat.label,
        "node": "code_studio_agent",
        "summary": _synthesis_beat.summary,
        "details": {"phase": _synthesis_beat.phase},
    })
    for _chunk in _code_studio_delta_chunks(_synthesis_beat):
        await push_event({
            "type": "thinking_delta",
            "content": _chunk,
            "node": "code_studio_agent",
        })
    await push_event({
        "type": "thinking_end",
        "content": "",
        "node": "code_studio_agent",
    })

    # Legacy widget fallback: only auto-inject for non-structured turns.
    llm_response = _inject_widget_blocks_from_tool_results(
        llm_response,
        tool_call_events,
        query=query,
        structured_visuals_enabled=getattr(settings, "enable_structured_visuals", False),
    )

    return llm_response, messages, tool_call_events


def _inject_widget_blocks_from_tool_results(
    llm_response,
    tool_call_events: list,
    *,
    query: str = "",
    structured_visuals_enabled: bool = False,
):
    """Inject legacy widget blocks only when the turn is not on the structured figure lane."""
    import re
    from langchain_core.messages import AIMessage as _AM

    raw_content = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
    # Gemini may return content as list of parts — flatten to string
    if isinstance(raw_content, list):
        response_text = "\n".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_content
        )
    else:
        response_text = str(raw_content)

    def _build_response(value: str):
        if hasattr(llm_response, "content"):
            return _AM(content=value)
        return value

    def _strip_widget_blocks(value: str) -> str:
        return re.sub(r"\n?```widget[ \t]*\n[\s\S]*?\n```\n?", "\n\n", value).strip()

    visual_decision = resolve_visual_intent(query) if query else None
    has_structured_visual_events = any(
        (
            event.get("type") in {"visual_open", "visual_patch", "visual_commit", "visual_dispose"}
            or event.get("name") == "tool_generate_visual"
        )
        for event in tool_call_events
    )

    if structured_visuals_enabled and has_structured_visual_events and "```widget" in response_text:
        cleaned = _strip_widget_blocks(response_text)
        return _build_response(cleaned) if cleaned != response_text else llm_response

    if (
        structured_visuals_enabled
        and visual_decision
        and visual_decision.force_tool
        and visual_decision.mode in {"template", "inline_html"}
    ):
        return llm_response

    # Already has widget block — no injection needed
    if "```widget" in response_text:
        return llm_response

    # Collect widget blocks from tool results
    widget_blocks = []
    for event in tool_call_events:
        if event.get("type") != "result":
            continue
        result_text = event.get("result", "")
        # Extract ```widget ... ``` blocks from tool output
        matches = re.findall(r"(```widget\n.+?```)", result_text, re.DOTALL)
        widget_blocks.extend(matches)

    if not widget_blocks:
        return llm_response

    # Inject widget blocks at the beginning of the response
    injected = "\n\n".join(widget_blocks) + "\n\n" + response_text
    return _build_response(injected)


def _should_surface_direct_thinking(thinking: str) -> bool:
    """Direct chat should not expose raw chain-of-thought in the user UI."""
    return False


def _get_phase_fallback(state: AgentState) -> str:
    """Sprint 203: Context-appropriate fallback based on conversation phase."""
    phase = state.get("context", {}).get("conversation_phase", "opening")
    _FALLBACKS = {
        "opening": "Mình là Wiii! Bạn muốn tìm hiểu gì hôm nay?",
        "engaged": "Hmm, mình gặp chút trục trặc khi xử lý. Bạn thử hỏi lại nhé?",
        "deep": "Xin lỗi, mình chưa xử lý được câu này. Bạn diễn đạt cách khác giúp mình nhé~",
        "closing": "Mình chưa hiểu rõ lắm. Bạn hỏi cụ thể hơn được không?",
    }
    return _FALLBACKS.get(phase, _FALLBACKS["engaged"])


async def direct_response_node(state: AgentState) -> AgentState:
    """
    Direct response node - conversational responses without RAG.

    CHỈ THỊ SỐ 30: Adds DIRECT_RESPONSE step and builds reasoning_trace.

    Handles:
    - Exact greeting matches -> canned response (fast path)
    - Everything else -> LLM-generated conversational response

    Sprint 154: Refactored — extracted 5 helper functions for testability.
    """
    query = state.get("query", "")

    # Sprint 140: Event bus for real-time tool/thinking streaming
    _event_queue = None
    _bus_id = state.get("_event_bus_id")
    if _bus_id:
        from app.engine.multi_agent.graph_streaming import _get_event_queue
        _event_queue = _get_event_queue(_bus_id)

    async def _push_event(event: dict):
        if _event_queue:
            try:
                _event_queue.put_nowait(event)
            except Exception as _qe:
                logger.debug("[DIRECT] Event queue push failed: %s", _qe)

    # CHỈ THỊ SỐ 30: Get inherited tracer from supervisor
    tracer = _get_or_create_tracer(state)
    tracer.start_step(StepNames.DIRECT_RESPONSE, "Tạo phản hồi trực tiếp")

    # Sprint 203: When natural conversation enabled, always use LLM (OpenClaw: runtime honors the soul)
    _use_natural = getattr(settings, "enable_natural_conversation", False) is True
    if not _use_natural:
        # LEGACY: exact-match canned greetings
        greetings = _get_domain_greetings(state.get("domain_id", settings.default_domain))
        query_lower = query.lower().strip()
        response = greetings.get(query_lower)
    else:
        query_lower = query.lower().strip()
        response = None  # Always LLM path — Wiii's identity is in system prompt

    # Resolve domain_name_vi early (needed for prompt and domain notice)
    domain_config = state.get("domain_config", {})
    domain_name_vi = domain_config.get("name_vi", "")
    if not domain_name_vi:
        domain_id = state.get("domain_id", settings.default_domain)
        domain_name_vi = {
            "maritime": "Hàng hải",
            "traffic_law": "Luật Giao thông",
        }.get(domain_id, domain_id)

    if response:
        # Exact greeting match — use canned response
        tracer.end_step(
            result=f"Phản hồi chào hỏi: {response[:50]}...",
            confidence=1.0,
            details={"response_type": "greeting", "query": query_lower}
        )
    else:
        # Not a greeting — generate LLM response
        try:
            from app.engine.multi_agent.agent_config import AgentConfigRegistry

            _ctx = state.get("context", {})
            thinking_effort = state.get("thinking_effort")
            llm = AgentConfigRegistry.get_llm("direct", effort_override=thinking_effort)

            # Sprint 203: Diversity params for response variation
            if llm and getattr(settings, "enable_natural_conversation", False) is True:
                _pp = getattr(settings, "llm_presence_penalty", 0.0)
                _fp = getattr(settings, "llm_frequency_penalty", 0.0)
                if _pp or _fp:
                    try:
                        llm = llm.bind(presence_penalty=_pp, frequency_penalty=_fp)
                    except Exception:
                        pass  # .bind() not supported by this provider — skip

            if llm:
                # Phase 1: Collect tools and determine forcing
                tools, force_tools = _collect_direct_tools(
                    query,
                    _ctx.get("user_role", "student"),
                )
                try:
                    from app.engine.skills.skill_recommender import select_runtime_tools

                    selected_tools = select_runtime_tools(
                        tools,
                        query=query,
                        intent=(state.get("routing_metadata") or {}).get("intent"),
                        user_role=_ctx.get("user_role", "student"),
                        max_tools=min(len(tools), 7),
                        must_include=_direct_required_tool_names(
                            query,
                            _ctx.get("user_role", "student"),
                        ),
                    )
                    if selected_tools:
                        tools = selected_tools
                        logger.info(
                            "[DIRECT] Runtime-selected tools: %s",
                            [getattr(tool, "name", getattr(tool, "__name__", "unknown")) for tool in tools],
                        )
                except Exception as _selection_err:
                    logger.debug("[DIRECT] Runtime tool selection skipped: %s", _selection_err)
                logger.warning("[DIRECT] tools=%d, force=%s, web=%s, dt=%s, query='%s'",
                            len(tools), force_tools,
                            _needs_web_search(query), _needs_datetime(query),
                            query[:60])

                # Phase 2: Bind tools to LLM
                llm_with_tools, llm_auto = _bind_direct_tools(llm, tools, force_tools)
                if force_tools:
                    logger.warning("[DIRECT] Forced tool_choice='any' (web=%s, datetime=%s)",
                                _needs_web_search(query), _needs_datetime(query))

                # Phase 3: Build messages
                messages = _build_direct_system_messages(state, query, domain_name_vi)
                runtime_context_base = build_tool_runtime_context(
                    event_bus_id=_bus_id,
                    request_id=_bus_id or state.get("session_id"),
                    session_id=state.get("session_id"),
                    organization_id=state.get("organization_id"),
                    user_id=state.get("user_id"),
                    user_role=_ctx.get("user_role", "student"),
                    node="direct",
                    source="agentic_loop",
                    metadata=_build_visual_tool_runtime_metadata(state, query),
                )

                # Phase 4: Multi-round tool execution
                llm_response, messages, _tc_events = await _execute_direct_tool_rounds(
                    llm_with_tools,
                    llm_auto,
                    messages,
                    tools,
                    _push_event,
                    runtime_context_base=runtime_context_base,
                    query=query,
                    state=state,
                )

                # Sprint 166: Store tool_call_events for preview extraction
                if _tc_events:
                    state["tool_call_events"] = _tc_events

                # Phase 5: Extract response
                response, thinking_content, tools_used = _extract_direct_response(llm_response, messages)

                _safe_direct_thinking = await _build_direct_reasoning_summary(
                    query,
                    state,
                    _direct_tool_names(tools_used),
                )
                if _safe_direct_thinking:
                    state["thinking_content"] = _safe_direct_thinking

                if _should_surface_direct_thinking(thinking_content):
                    state["thinking"] = thinking_content
                if tools_used:
                    state["tools_used"] = tools_used

                tracer.end_step(
                    result=f"Phản hồi LLM: {len(response)} chars",
                    confidence=0.85,
                    details={"response_type": "llm_generated",
                             "tools_bound": len(tools),
                             "force_tools": force_tools}
                )
            else:
                response = _get_phase_fallback(state) if getattr(settings, "enable_natural_conversation", False) is True else "Xin chào! Tôi có thể giúp gì cho bạn?"
                tracer.end_step(
                    result="Fallback (LLM unavailable)",
                    confidence=0.5,
                    details={"response_type": "fallback"}
                )
        except Exception as e:
            logger.warning("[DIRECT] LLM generation failed: %s", e)
            response = _get_phase_fallback(state) if getattr(settings, "enable_natural_conversation", False) is True else "Xin chào! Tôi có thể giúp gì cho bạn?"
            tracer.end_step(
                result="Fallback (LLM generation error)",
                confidence=0.5,
                details={"response_type": "fallback"}
            )

    if not state.get("thinking_content"):
        state["thinking_content"] = await _build_direct_reasoning_summary(
            query,
            state,
            _direct_tool_names(state.get("tools_used", [])),
        )

    state["final_response"] = response
    state["agent_outputs"] = {"direct": response}
    state["current_agent"] = "direct"

    # Sprint 80b: Keep notice only for legacy "general" fallback mode.
    # LLM-first DIRECT answers for off-topic/meta chat are valid behavior for Wiii
    # and should not be framed as out-of-domain failures.
    routing_meta = state.get("routing_metadata", {})
    intent = routing_meta.get("intent", "") if routing_meta else ""
    if intent == "general":
        # Sprint 214: Suppress notice when org has knowledge enabled — org KB may cover any topic
        from app.core.config import settings as _settings
        from app.core.org_context import get_current_org_id as _get_org_id
        _suppress = _settings.enable_org_knowledge and bool(_get_org_id())
        if not _suppress:
            state["domain_notice"] = (
                f"Nội dung này nằm ngoài chuyên môn {domain_name_vi}. "
                f"Để được hỗ trợ chính xác hơn, hãy hỏi về {domain_name_vi} nhé!"
            )

    logger.info("[DIRECT] Response prepared, tracer passed to synthesizer")

    return state


async def code_studio_node(state: AgentState) -> AgentState:
    """Capability subagent for Python, chart, HTML, and file-generation tasks."""
    query = state.get("query", "")

    _event_queue = None
    _bus_id = state.get("_event_bus_id")
    if _bus_id:
        from app.engine.multi_agent.graph_streaming import _get_event_queue
        _event_queue = _get_event_queue(_bus_id)

    async def _push_event(event: dict):
        if _event_queue:
            try:
                _event_queue.put_nowait(event)
            except Exception as _qe:
                logger.debug("[CODE_STUDIO] Event queue push failed: %s", _qe)

    tracer = _get_or_create_tracer(state)
    tracer.start_step(StepNames.DIRECT_RESPONSE, "Che tac dau ra ky thuat")

    domain_config = state.get("domain_config", {})
    domain_name_vi = domain_config.get("name_vi", "")
    if not domain_name_vi:
        domain_id = state.get("domain_id", settings.default_domain)
        domain_name_vi = {
            "maritime": "Hang hai",
            "traffic_law": "Luat Giao thong",
        }.get(domain_id, domain_id)

    try:
        from app.engine.multi_agent.agent_config import AgentConfigRegistry

        _ctx = state.get("context", {})
        thinking_effort = state.get("thinking_effort")
        llm = AgentConfigRegistry.get_llm("code_studio_agent", effort_override=thinking_effort)

        if llm and getattr(settings, "enable_natural_conversation", False) is True:
            _pp = getattr(settings, "llm_presence_penalty", 0.0)
            _fp = getattr(settings, "llm_frequency_penalty", 0.0)
            if _pp or _fp:
                try:
                    llm = llm.bind(presence_penalty=_pp, frequency_penalty=_fp)
                except Exception:
                    pass

        if llm:
            tools, force_tools = _collect_code_studio_tools(query, _ctx.get("user_role", "student"))
            try:
                from app.engine.skills.skill_recommender import select_runtime_tools

                selected_tools = select_runtime_tools(
                    tools,
                    query=query,
                    intent=(state.get("routing_metadata") or {}).get("intent"),
                    user_role=_ctx.get("user_role", "student"),
                    max_tools=min(len(tools), 8),
                    must_include=_code_studio_required_tool_names(
                        query,
                        _ctx.get("user_role", "student"),
                    ),
                )
                if selected_tools:
                    tools = selected_tools
                    logger.info(
                        "[CODE_STUDIO] Runtime-selected tools: %s",
                        [getattr(tool, "name", getattr(tool, "__name__", "unknown")) for tool in tools],
                    )
            except Exception as _selection_err:
                logger.debug("[CODE_STUDIO] Runtime tool selection skipped: %s", _selection_err)

            llm_with_tools, llm_auto = _bind_direct_tools(llm, tools, force_tools)
            messages = _build_direct_system_messages(
                state,
                query,
                domain_name_vi,
                role_name="code_studio_agent",
                tools_context_override=_build_code_studio_tools_context(
                    settings,
                    _ctx.get("user_role", "student"),
                    query,
                ),
            )
            runtime_context_base = build_tool_runtime_context(
                event_bus_id=_bus_id,
                request_id=_bus_id or state.get("session_id"),
                session_id=state.get("session_id"),
                organization_id=state.get("organization_id"),
                user_id=state.get("user_id"),
                user_role=_ctx.get("user_role", "student"),
                node="code_studio_agent",
                source="agentic_loop",
                metadata=_build_visual_tool_runtime_metadata(state, query),
            )

            llm_response, messages, _tc_events = await _execute_code_studio_tool_rounds(
                llm_with_tools,
                llm_auto,
                messages,
                tools,
                _push_event,
                runtime_context_base=runtime_context_base,
                query=query,
                state=state,
            )

            if _tc_events:
                state["tool_call_events"] = _tc_events

            response, thinking_content, tools_used = _extract_direct_response(llm_response, messages)
            response = _sanitize_code_studio_response(response, _tc_events)

            _safe_thinking = await _build_code_studio_reasoning_summary(
                query,
                state,
                _direct_tool_names(tools_used),
            )
            if _safe_thinking:
                state["thinking_content"] = _safe_thinking

            if tools_used:
                state["tools_used"] = tools_used

            tracer.end_step(
                result=f"Code studio response: {len(response)} chars",
                confidence=0.88,
                details={
                    "response_type": "capability_generated",
                    "tools_bound": len(tools),
                    "force_tools": force_tools,
                },
            )
        else:
            response = "Mình chưa khởi động được Code Studio lúc này. Bạn thử lại sau nhé."
            tracer.end_step(
                result="Fallback (code studio unavailable)",
                confidence=0.5,
                details={"response_type": "fallback"},
            )
    except Exception as e:
        logger.warning("[CODE_STUDIO] Generation failed: %s", e)
        response = "Mình gặp trục trặc khi mở Code Studio. Bạn thử lại giúp mình nhé."
        tracer.end_step(
            result="Fallback (code studio error)",
            confidence=0.5,
            details={"response_type": "fallback"},
        )

    if not state.get("thinking_content"):
        state["thinking_content"] = await _build_code_studio_reasoning_summary(
            query,
            state,
            _direct_tool_names(state.get("tools_used", [])),
        )

    state["final_response"] = response
    state["agent_outputs"] = {"code_studio_agent": response}
    state["current_agent"] = "code_studio_agent"

    logger.info("[CODE_STUDIO] Response prepared, tracer passed to synthesizer")

    return state


# =============================================================================
# Sprint 163 Phase 4: Parallel Dispatch + Subagent Adapters
# Sprint 164: Added per-worker event emission for UX visualization
# =============================================================================


def _emit_subagent_event(state: dict, event: dict) -> None:
    """Emit an SSE event from a subagent adapter via the event bus."""
    bus_id = state.get("_event_bus_id")
    if not bus_id:
        return
    try:
        from app.engine.multi_agent.graph_streaming import _get_event_queue
        queue = _get_event_queue(bus_id)
        if queue:
            queue.put_nowait(event)
    except Exception as _qe:
        logger.debug("[SUBAGENT_EVENT] Event emit failed: %s", _qe)


async def _run_rag_subagent(state: dict, **kwargs) -> "SubagentResult":
    """Adapter: run existing RAG agent and wrap output as SubagentResult."""
    from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus
    rag_opening = await _render_reasoning(
        state=state,
        node="rag_agent",
        phase="retrieve",
        cue="parallel_dispatch",
        next_action="Lục lại kho tri thức rồi gạn nguồn đỡ câu hỏi nhất.",
        style_tags=["rag", "parallel_dispatch"],
    )

    # Sprint 164: Emit thinking lifecycle events for desktop UX
    _emit_subagent_event(state, {
        "type": "thinking_start",
        "content": rag_opening.label,
        "node": "rag",
        "summary": rag_opening.summary,
        "details": {"phase": rag_opening.phase},
    })
    _emit_subagent_event(state, {
        "type": "thinking_delta",
        "content": rag_opening.summary,
        "node": "rag",
    })
    _emit_subagent_event(state, {
        "type": "status",
        "content": "Tìm kiếm trong kho tri thức...",
        "node": "rag",
    })

    try:
        rag_agent = get_rag_agent_node()
        result_state = await rag_agent.process(state)

        _emit_subagent_event(state, {
            "type": "status",
            "content": "Đánh giá tài liệu và tạo câu trả lời...",
            "node": "rag",
        })

        output = result_state.get("rag_output", "") or result_state.get("final_response", "")
        confidence = 0.0
        trace = result_state.get("reasoning_trace")
        if trace and hasattr(trace, "final_confidence"):
            confidence = trace.final_confidence or 0.0
        elif result_state.get("grader_score"):
            confidence = result_state["grader_score"] / 10.0
        else:
            confidence = 0.6 if output else 0.0

        # Emit thinking summary if available
        thinking = result_state.get("thinking")
        if thinking:
            _emit_subagent_event(state, {
                "type": "thinking_delta",
                "content": thinking[:500],
                "node": "rag",
            })

        _emit_subagent_event(state, {
            "type": "thinking_end",
            "node": "rag",
        })

        return SubagentResult(
            status=SubagentStatus.SUCCESS if output else SubagentStatus.PARTIAL,
            output=output,
            confidence=confidence,
            sources=result_state.get("sources", []),
            evidence_images=result_state.get("evidence_images", []),  # Sprint 189b
            thinking=thinking,
        )
    except Exception as e:
        logger.warning("[PARALLEL_DISPATCH] RAG subagent error: %s", e)
        _emit_subagent_event(state, {
            "type": "thinking_end",
            "node": "rag",
        })
        return SubagentResult(
            status=SubagentStatus.ERROR,
            error_message="RAG subagent processing error",
        )


async def _run_tutor_subagent(state: dict, **kwargs) -> "SubagentResult":
    """Adapter: run existing Tutor agent and wrap output as SubagentResult."""
    from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus
    tutor_opening = await _render_reasoning(
        state=state,
        node="tutor_agent",
        phase="attune",
        cue="parallel_dispatch",
        next_action="Bắt nhịp điều người dùng đang vướng rồi soạn lại đường giải thích.",
        style_tags=["tutor", "parallel_dispatch"],
    )

    # Sprint 164: Emit thinking lifecycle events for desktop UX
    _emit_subagent_event(state, {
        "type": "thinking_start",
        "content": tutor_opening.label,
        "node": "tutor",
        "summary": tutor_opening.summary,
        "details": {"phase": tutor_opening.phase},
    })
    _emit_subagent_event(state, {
        "type": "thinking_delta",
        "content": tutor_opening.summary,
        "node": "tutor",
    })
    _emit_subagent_event(state, {
        "type": "status",
        "content": "Đang chuẩn bị phần giải thích...",
        "node": "tutor",
    })

    try:
        tutor_agent = get_tutor_agent_node()
        result_state = await tutor_agent.process(state)

        _emit_subagent_event(state, {
            "type": "status",
            "content": "Đang viết lại lời giải...",
            "node": "tutor",
        })

        output = result_state.get("tutor_output", "") or result_state.get("final_response", "")
        confidence = 0.7 if output else 0.0

        # Emit thinking summary if available
        thinking = result_state.get("thinking")
        if thinking:
            _emit_subagent_event(state, {
                "type": "thinking_delta",
                "content": thinking[:500],
                "node": "tutor",
            })

        _emit_subagent_event(state, {
            "type": "thinking_end",
            "node": "tutor",
        })

        return SubagentResult(
            status=SubagentStatus.SUCCESS if output else SubagentStatus.PARTIAL,
            output=output,
            confidence=confidence,
            sources=result_state.get("sources", []),
            tools_used=result_state.get("tools_used", []),
            thinking=thinking,
        )
    except Exception as e:
        logger.warning("[PARALLEL_DISPATCH] Tutor subagent error: %s", e)
        _emit_subagent_event(state, {
            "type": "thinking_end",
            "node": "tutor",
        })
        return SubagentResult(
            status=SubagentStatus.ERROR,
            error_message="Tutor subagent processing error",
        )


async def _run_search_subagent(state: dict, **kwargs) -> "SubagentResult":
    """Adapter: run product search and wrap output as SubagentResult."""
    from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus
    search_opening = await _render_reasoning(
        state=state,
        node="product_search_agent",
        phase="retrieve",
        cue="parallel_dispatch",
        next_action="Mở nhiều nguồn giá song song rồi gạn lại mặt bằng đáng tin.",
        style_tags=["product_search", "parallel_dispatch"],
    )

    # Sprint 164: Emit thinking lifecycle events for desktop UX
    _emit_subagent_event(state, {
        "type": "thinking_start",
        "content": search_opening.label,
        "node": "search",
        "summary": search_opening.summary,
        "details": {"phase": search_opening.phase},
    })
    _emit_subagent_event(state, {
        "type": "thinking_delta",
        "content": search_opening.summary,
        "node": "search",
    })

    try:
        from app.engine.multi_agent.agents.product_search_node import get_product_search_agent_node
        agent = get_product_search_agent_node()
        result_state = await agent.process(state)
        output = result_state.get("final_response", "")
        confidence = 0.7 if output else 0.0

        _emit_subagent_event(state, {
            "type": "thinking_end",
            "node": "search",
        })

        return SubagentResult(
            status=SubagentStatus.SUCCESS if output else SubagentStatus.PARTIAL,
            output=output,
            confidence=confidence,
            tools_used=result_state.get("tools_used", []),
        )
    except Exception as e:
        logger.warning("[PARALLEL_DISPATCH] Search subagent error: %s", e)
        _emit_subagent_event(state, {
            "type": "thinking_end",
            "node": "search",
        })
        return SubagentResult(
            status=SubagentStatus.ERROR,
            error_message="Search subagent processing error",
        )


# Registry of subagent adapter functions
_SUBAGENT_ADAPTERS = {
    "rag": _run_rag_subagent,
    "tutor": _run_tutor_subagent,
    "search": _run_search_subagent,
}

# Subagent type mapping for report building
_SUBAGENT_TYPES = {
    "rag": "retrieval",
    "tutor": "teaching",
    "search": "product_search",
}


async def parallel_dispatch_node(state: AgentState) -> AgentState:
    """Dispatch query to multiple subagents in parallel, collect reports.

    Reads state["_parallel_targets"] for the list of agent names to dispatch.
    Wraps each result as a SubagentReport and stores in state["subagent_reports"].
    """
    from app.engine.multi_agent.subagents.config import SubagentConfig
    from app.engine.multi_agent.subagents.executor import execute_parallel_subagents
    from app.engine.multi_agent.subagents.report import build_report

    targets = state.get("_parallel_targets")
    if targets is None:
        targets = ["rag", "tutor"]

    logger.info("[PARALLEL_DISPATCH] Dispatching to: %s", targets)

    # Emit status event
    _bus_id = state.get("_event_bus_id")
    if _bus_id:
        try:
            from app.engine.multi_agent.graph_streaming import _get_event_queue
            queue = _get_event_queue(_bus_id)
            if queue:
                queue.put_nowait({
                    "type": "status",
                    "content": f"Triển khai song song: {', '.join(targets)}",
                    "node": "parallel_dispatch",
                })
        except Exception as _se:
            logger.debug("[PARALLEL_DISPATCH] Status event emit failed: %s", _se)

    # Build task list for parallel execution
    tasks = []
    timeout = 60
    try:
        from app.core.config import settings as _settings
        timeout = _settings.subagent_default_timeout
    except Exception as _cfg_err:
        logger.debug("[PARALLEL_DISPATCH] Could not read subagent_default_timeout: %s", _cfg_err)

    for name in targets:
        adapter = _SUBAGENT_ADAPTERS.get(name)
        if adapter is None:
            logger.warning("[PARALLEL_DISPATCH] Unknown target: %s, skipping", name)
            continue
        config = SubagentConfig(name=name, timeout_seconds=timeout)
        tasks.append((adapter, config, dict(state), {}))

    if not tasks:
        logger.warning("[PARALLEL_DISPATCH] No valid targets, skipping")
        state["subagent_reports"] = []
        return state

    # Execute all subagents in parallel
    max_concurrent = 5
    try:
        from app.core.config import settings as _settings
        max_concurrent = _settings.subagent_max_parallel
    except Exception as _cfg_err:
        logger.debug("[PARALLEL_DISPATCH] Could not read subagent_max_parallel: %s", _cfg_err)

    results = await execute_parallel_subagents(tasks, max_concurrent=max_concurrent)

    # Wrap results as reports
    reports = []
    for name, result in zip(targets, results):
        agent_type = _SUBAGENT_TYPES.get(name, "general")
        report = build_report(name, agent_type, result)
        reports.append(report.model_dump())

    state["subagent_reports"] = reports

    logger.info(
        "[PARALLEL_DISPATCH] Collected %d reports: %s",
        len(reports),
        [(r.get("agent_name"), r.get("verdict")) for r in reports],
    )

    # Propagate trace_id
    state["_trace_id"] = state.get("_trace_id")

    return state


# =============================================================================
# Routing Function
# =============================================================================

def route_decision(state: AgentState) -> str:
    """
    Determine next agent based on supervisor decision.

    Returns edge name for LangGraph routing.
    """
    next_agent = state.get("next_agent", "rag_agent")

    valid_routes = {
        "rag_agent", "tutor_agent", "memory_agent",
        "direct", "code_studio_agent", "product_search_agent", "parallel_dispatch",
        "colleague_agent",
    }

    if next_agent in valid_routes:
        return next_agent
    return "direct"


# =============================================================================
# P1 SOTA Early Exit: Skip Quality Check at High Confidence
# Saves ~7.8s when CRAG confidence is high
# =============================================================================

def should_skip_grader(state: AgentState) -> Literal["grader", "synthesizer"]:
    """
    Determine if quality check can be skipped based on confidence.

    SOTA 2025 Pattern: Self-RAG Early Exit
    - If CRAG pipeline returned high confidence, skip expensive grader LLM call
    - Saves ~7.8s per request
    - Threshold configurable via settings.quality_skip_threshold

    Args:
        state: Current agent state with potential CRAG trace

    Returns:
        "synthesizer" if skip, "grader" if quality check needed
    """
    threshold = settings.quality_skip_threshold

    # Check for CRAG trace with confidence
    reasoning_trace = state.get("reasoning_trace")

    if reasoning_trace and hasattr(reasoning_trace, 'final_confidence'):
        confidence = reasoning_trace.final_confidence
        if confidence >= threshold:
            logger.info(
                "[P1 EARLY EXIT] Skipping quality_check: confidence=%.2f >= %s",
                confidence, threshold,
            )
            return "synthesizer"

    # Also check state-level confidence from CRAG
    crag_confidence = state.get("crag_confidence", 0)
    if crag_confidence >= threshold:
        logger.info(
            "[P1 EARLY EXIT] Skipping quality_check: crag_confidence=%.2f >= %s",
            crag_confidence, threshold,
        )
        return "synthesizer"

    # Default: run quality check
    return "grader"


# =============================================================================
# Guardian Agent Node (SOTA 2026: Defense-in-depth Layer 2)
# =============================================================================

# Sprint 75: Guardian singleton — avoid re-instantiation overhead (~2s per turn)
_guardian_instance: Optional["GuardianAgent"] = None


def _get_guardian():
    """Get or create Guardian agent singleton (lazy init)."""
    global _guardian_instance
    if _guardian_instance is None:
        from app.engine.guardian_agent import GuardianAgent
        _guardian_instance = GuardianAgent()
    return _guardian_instance


async def guardian_node(state: AgentState) -> AgentState:
    """
    Guardian Agent node — input validation perimeter.

    Defense-in-depth Layer 2: Validates input before routing.
    Blocks inappropriate content, flags edge cases.
    Fail-open on errors: never block real users if Guardian LLM fails.

    Sprint 75: Uses module-level singleton to avoid ~2s _init_llm() overhead.
    """
    query = state.get("query", "")

    # Skip for very short messages (greetings, single words)
    if len(query.strip()) < 3:
        state["guardian_passed"] = True
        return state

    try:
        guardian = _get_guardian()
        domain_id = state.get("domain_id")
        decision = await guardian.validate_message(query, context="education", domain_id=domain_id)

        if decision.action == "BLOCK":
            logger.warning("[GUARDIAN] Blocked: %s", decision.reason)
            state["final_response"] = decision.reason or "Nội dung không phù hợp."
            state["guardian_passed"] = False
            return state

        if decision.action == "FLAG":
            logger.info("[GUARDIAN] Flagged: %s", decision.reason)

        state["guardian_passed"] = True
        return state

    except Exception as e:
        # Fail-open: don't block on Guardian errors
        logger.warning("[GUARDIAN] Validation error (allowing): %s", e)
        state["guardian_passed"] = True
        return state


def guardian_route(state: AgentState) -> Literal["supervisor", "synthesizer"]:
    """Route based on Guardian decision: pass to supervisor or block to synthesizer."""
    if state.get("guardian_passed", True):
        return "supervisor"
    return "synthesizer"


# =============================================================================
# Domain Plugin Helpers
# =============================================================================

def _build_domain_config(domain_id: str) -> dict:
    """
    Build domain config dict for injection into AgentState.

    Loads routing config from the DomainRegistry.
    Falls back to maritime defaults if domain not found.
    """
    try:
        from app.domains.registry import get_domain_registry
        registry = get_domain_registry()
        domain = registry.get(domain_id)
        if domain:
            config = domain.get_config()
            routing = domain.get_routing_config()
            return {
                "domain_name": config.name,
                "domain_id": config.id,
                "routing_keywords": config.routing_keywords,
                "rag_description": routing.get("rag_description", ""),
                "tutor_description": routing.get("tutor_description", ""),
            }
    except Exception as e:
        logger.debug("Domain config fallback: %s", e)

    # Fallback: generic defaults
    return {
        "domain_name": settings.app_name,
        "domain_id": settings.default_domain,
        "routing_keywords": [],
        "rag_description": "Tra cứu kiến thức, quy định, luật, thủ tục trong cơ sở dữ liệu",
        "tutor_description": "Giải thích, dạy học, quiz về kiến thức chuyên ngành",
    }


def _get_domain_greetings(domain_id: str) -> dict:
    """
    Get greeting responses from domain plugin.

    Falls back to maritime defaults if domain not found.
    """
    try:
        from app.domains.registry import get_domain_registry
        registry = get_domain_registry()
        domain = registry.get(domain_id)
        if domain:
            return domain.get_greetings()
    except Exception as e:
        logger.debug("Domain greetings fallback: %s", e)

    name = settings.app_name
    return {
        "xin chào": f"Xin chào! Tôi là {name}. Tôi có thể giúp gì cho bạn?",
        "hello": f"Hello! I'm {name}. How can I help you?",
        "hi": "Chào bạn! Bạn muốn hỏi về vấn đề gì?",
        "cảm ơn": "Không có gì! Nếu có thắc mắc gì khác, cứ hỏi nhé!",
        "thanks": "You're welcome! Let me know if you have more questions.",
    }


# =============================================================================
# Graph Builder
# =============================================================================

def build_multi_agent_graph(checkpointer=None):
    """
    Build LangGraph workflow for multi-agent system.

    Flow:
    1. Guardian → Content validation (SOTA 2026: defense-in-depth)
    2. Supervisor → Route decision
    3. [RAG | Tutor | Memory | Direct]
    4. Grader (optional)
    5. Synthesizer
    6. END

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence.
                      If None, graph runs without multi-turn persistence.

    Returns:
        Compiled LangGraph
    """
    logger.info("Building Multi-Agent Graph...")

    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("guardian", guardian_node)
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("rag_agent", rag_node)
    workflow.add_node("tutor_agent", tutor_node)
    workflow.add_node("memory_agent", memory_node)
    workflow.add_node("direct", direct_response_node)
    workflow.add_node("code_studio_agent", code_studio_node)
    workflow.add_node("grader", grader_node)
    workflow.add_node("synthesizer", synthesizer_node)
    # Sprint 215: Colleague agent (cross-soul consultation, feature-gated)
    if settings.enable_cross_soul_query and settings.enable_soul_bridge:
        workflow.add_node("colleague_agent", colleague_agent_node)
        logger.info("Colleague agent node added (cross-soul query enabled)")

    # Sprint 148/163: Product search agent (feature-gated at supervisor level)
    if settings.enable_product_search:
        if settings.enable_subagent_architecture:
            # Sprint 163: Use parallel subgraph (Send() map-reduce)
            from app.engine.multi_agent.subagents.search.graph import build_search_subgraph
            _search_subgraph = build_search_subgraph()
            workflow.add_node("product_search_agent", _search_subgraph)
            logger.info("Product search: using SUBGRAPH (parallel Send)")
        else:
            workflow.add_node("product_search_agent", product_search_node)

    # Sprint 163 Phase 4: Parallel dispatch + aggregator (feature-gated)
    if settings.enable_subagent_architecture:
        from app.engine.multi_agent.subagents.aggregator import (
            aggregator_node,
            aggregator_route,
        )
        workflow.add_node("parallel_dispatch", parallel_dispatch_node)
        workflow.add_node("aggregator", aggregator_node)
        logger.info("Phase 4: parallel_dispatch + aggregator nodes added")

    # Set entry point — Guardian validates before routing
    workflow.set_entry_point("guardian")

    # Guardian → Supervisor (allowed) or Synthesizer (blocked)
    workflow.add_conditional_edges(
        "guardian",
        guardian_route,
        {"supervisor": "supervisor", "synthesizer": "synthesizer"},
    )

    # Conditional routing from supervisor
    _routing_map = {
        "rag_agent": "rag_agent",
        "tutor_agent": "tutor_agent",
        "memory_agent": "memory_agent",
        "direct": "direct",
        "code_studio_agent": "code_studio_agent",
    }
    if settings.enable_product_search:
        _routing_map["product_search_agent"] = "product_search_agent"
    # Sprint 215: Colleague agent route
    if settings.enable_cross_soul_query and settings.enable_soul_bridge:
        _routing_map["colleague_agent"] = "colleague_agent"
    # Sprint 163 Phase 4: parallel dispatch route
    if settings.enable_subagent_architecture:
        _routing_map["parallel_dispatch"] = "parallel_dispatch"
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        _routing_map,
    )
    
    # All agents → Grader (with conditional skip)
    # P1 SOTA: Use conditional edges for tutor and rag - skip grader at high confidence
    workflow.add_conditional_edges(
        "rag_agent",
        should_skip_grader,
        {
            "grader": "grader",
            "synthesizer": "synthesizer"
        }
    )
    # Sprint 75: Tutor skips grader — pedagogical responses don't need
    # knowledge accuracy grading. ReAct loop self-corrects. Saves ~6s.
    workflow.add_edge("tutor_agent", "synthesizer")
    # Sprint 72: Memory agent skips grader — responses are conversational
    # acknowledgments, not knowledge retrieval. Grading is meaningless here.
    workflow.add_edge("memory_agent", "synthesizer")
    
    # Direct → Synthesizer (skip grader)
    workflow.add_edge("direct", "synthesizer")
    workflow.add_edge("code_studio_agent", "synthesizer")

    # Sprint 148: Product search → Synthesizer (skip grader — comparison data, not knowledge)
    if settings.enable_product_search:
        workflow.add_edge("product_search_agent", "synthesizer")

    # Sprint 215: Colleague → Synthesizer (skip grader — external consultation, not knowledge)
    if settings.enable_cross_soul_query and settings.enable_soul_bridge:
        workflow.add_edge("colleague_agent", "synthesizer")

    # Sprint 163 Phase 4: parallel_dispatch → aggregator → conditional
    if settings.enable_subagent_architecture:
        workflow.add_edge("parallel_dispatch", "aggregator")
        workflow.add_conditional_edges(
            "aggregator",
            aggregator_route,
            {"synthesizer": "synthesizer", "supervisor": "supervisor"},
        )
    
    # Grader → Synthesizer
    workflow.add_edge("grader", "synthesizer")
    
    # Synthesizer → END
    workflow.add_edge("synthesizer", END)
    
    # Compile with optional checkpointer (SOTA 2026: persistent state)
    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
        logger.info("Graph compiled WITH checkpointer (multi-turn persistence enabled)")
    else:
        logger.info("Graph compiled WITHOUT checkpointer")

    graph = workflow.compile(**compile_kwargs)

    logger.info("Multi-Agent Graph built successfully")

    return graph


# =============================================================================
# Singleton
# =============================================================================

_sync_graph = None


def get_multi_agent_graph():
    """Get or create Multi-Agent Graph singleton (sync, no checkpointer)."""
    global _sync_graph
    if _sync_graph is None:
        _sync_graph = build_multi_agent_graph()
    return _sync_graph


@asynccontextmanager
async def open_multi_agent_graph():
    """Build a request-scoped graph with its own checkpointer connection."""
    from app.engine.multi_agent.checkpointer import open_checkpointer

    async with open_checkpointer() as checkpointer:
        yield build_multi_agent_graph(checkpointer=checkpointer)


async def get_multi_agent_graph_async():
    """
    Backward-compatible async accessor.

    Prefer ``open_multi_agent_graph()`` for request handling so each request
    gets an isolated checkpointer connection.
    """
    return build_multi_agent_graph()


async def _generate_session_summary_bg(thread_id: str, user_id: str) -> None:
    """Background: generate session summary for cross-session preamble (Sprint 79)."""
    try:
        from app.services.session_summarizer import get_session_summarizer
        summarizer = get_session_summarizer()
        await summarizer.summarize_thread(thread_id, user_id)
    except Exception as e:
        logger.debug("Background session summary failed: %s", e)


def _inject_host_context(state: dict) -> str:
    """Graph-level host context injection (Sprint 222).

    Converts page_context (Sprint 221 legacy) or host_context (Sprint 222)
    into a formatted prompt block. Called ONCE -- stored in state['host_context_prompt']
    so ALL agents include it automatically.

    Priority: host_context (new) > page_context (legacy).
    Returns empty string if no context available or on any error.
    """
    ctx = state.get("context", {})
    if not isinstance(ctx, dict):
        return ""

    # Priority 1: New host_context schema (Sprint 222+)
    raw_host = ctx.get("host_context")
    if raw_host:
        try:
            from app.engine.context.host_context import HostContext
            from app.engine.context.adapters import get_host_adapter

            host_ctx = HostContext(**raw_host) if isinstance(raw_host, dict) else raw_host
            adapter = get_host_adapter(host_ctx.host_type)
            formatted = adapter.format_context_for_prompt(host_ctx)

            # Phase 6: Append skill prompt if enabled
            try:
                from app.core.config import get_settings
                _settings = get_settings()
                if getattr(_settings, "enable_host_skills", False):
                    from app.engine.context.skill_loader import get_skill_loader
                    page_type = host_ctx.page.get("type", "unknown") if isinstance(host_ctx.page, dict) else "unknown"
                    loader = get_skill_loader()
                    skills = loader.load_skills(host_ctx.host_type, page_type)
                    skill_prompt = loader.get_prompt_addition(skills)
                    if skill_prompt:
                        formatted = formatted + "\n\n" + skill_prompt
            except Exception as e:
                logger.warning("[GRAPH] Skill loading failed (non-fatal): %s", e)

            return formatted
        except Exception as e:
            logger.warning("[GRAPH] host_context format failed: %s", e)

    # Priority 2: Legacy page_context (Sprint 221 backward compat)
    page_ctx = ctx.get("page_context")
    if page_ctx:
        try:
            from app.engine.context.host_context import from_legacy_page_context
            from app.engine.context.adapters import get_host_adapter

            page_dict = page_ctx if isinstance(page_ctx, dict) else (
                page_ctx.model_dump(exclude_none=True) if hasattr(page_ctx, "model_dump") else dict(page_ctx)
            )
            host_ctx = from_legacy_page_context(
                page_dict,
                student_state=ctx.get("student_state"),
                available_actions=ctx.get("available_actions"),
            )
            adapter = get_host_adapter(host_ctx.host_type)
            formatted = adapter.format_context_for_prompt(host_ctx)

            # Phase 6: Append skill prompt if enabled (same as Priority 1)
            try:
                from app.core.config import get_settings
                _settings = get_settings()
                if getattr(_settings, "enable_host_skills", False):
                    from app.engine.context.skill_loader import get_skill_loader
                    page_type = host_ctx.page.get("type", "unknown") if isinstance(host_ctx.page, dict) else "unknown"
                    loader = get_skill_loader()
                    skills = loader.load_skills(host_ctx.host_type, page_type)
                    skill_prompt = loader.get_prompt_addition(skills)
                    if skill_prompt:
                        formatted = formatted + "\n\n" + skill_prompt
            except Exception as e:
                logger.warning("[GRAPH] Skill loading failed (non-fatal): %s", e)

            return formatted
        except Exception as e:
            logger.warning("[GRAPH] Legacy page_context format failed: %s", e)

    return ""


def _inject_visual_context(state: dict) -> str:
    """Format client-side inline visual context as prompt guidance for patchable visuals."""
    ctx = state.get("context", {})
    if not isinstance(ctx, dict):
        return ""

    raw_visual = ctx.get("visual_context")
    if not isinstance(raw_visual, dict) or not raw_visual:
        return ""

    last_session_id = str(raw_visual.get("last_visual_session_id") or "").strip()
    last_visual_type = str(raw_visual.get("last_visual_type") or "").strip()
    last_visual_title = str(raw_visual.get("last_visual_title") or "").strip()
    active_inline_visuals = raw_visual.get("active_inline_visuals")
    active_items = active_inline_visuals if isinstance(active_inline_visuals, list) else []

    lines = [
        "## Inline Visual Context",
        "- Neu user dang sua, lam ro, highlight, loc, hoac bien doi visual vua co trong chat, UU TIEN patch cung visual session thay vi tao visual moi.",
        "- Khi patch, goi tool_generate_visual voi visual_session_id cu va operation='patch'. Chi doi visual_type neu user yeu cau ro rang.",
        "- Chon renderer_kind phu hop: template cho visual giao duc chuan, inline_html cho custom editorial visual, app cho simulation/mini tool.",
        "- Sau khi goi tool_generate_visual, KHONG copy JSON vao answer. Viet narrative ngan + takeaway; frontend se tu dong cap nhat visual.",
    ]

    if last_session_id:
        lines.append(f"- Visual session gan nhat: {last_session_id}")
    if last_visual_type:
        lines.append(f"- Loai visual gan nhat: {last_visual_type}")
    if last_visual_title:
        lines.append(f"- Tieu de visual gan nhat: {last_visual_title}")

    if active_items:
        lines.append("- Visual dang co san trong thread:")
        for index, item in enumerate(active_items[:4], start=1):
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("visual_session_id") or item.get("session_id") or "").strip()
            visual_type = str(item.get("type") or "").strip()
            title = str(item.get("title") or "").strip()
            status = str(item.get("status") or "").strip()
            renderer_kind = str(item.get("renderer_kind") or "").strip()
            shell_variant = str(item.get("shell_variant") or "").strip()
            state_summary = str(item.get("state_summary") or "").strip()
            summary = " | ".join(
                part for part in (session_id, visual_type, title, renderer_kind, shell_variant, status, state_summary) if part
            )
            if summary:
                lines.append(f"  {index}. {summary}")

    return "\n".join(lines)


def _inject_widget_feedback_context(state: dict) -> str:
    """Format recent widget/app outcomes as prompt guidance for the next turn."""
    ctx = state.get("context", {})
    if not isinstance(ctx, dict):
        return ""

    raw_feedback = ctx.get("widget_feedback")
    if not isinstance(raw_feedback, dict) or not raw_feedback:
        return ""

    items = raw_feedback.get("recent_widget_feedback")
    recent_items = items if isinstance(items, list) else []
    last_kind = str(raw_feedback.get("last_widget_kind") or "").strip()
    last_summary = str(raw_feedback.get("last_widget_summary") or "").strip()

    if not recent_items and not (last_kind or last_summary):
        return ""

    lines = [
        "## Widget Feedback Context",
        "- User vua tuong tac voi widget/app trong chat. Neu phu hop, hay phan tich ket qua nay de ca nhan hoa cau tra loi tiep theo.",
        "- Uu tien nhan xet tien do, diem manh, diem can on lai, va goi y buoc tiep theo dua tren ket qua widget.",
        "- Neu ket qua cho thay user gap kho khan, co the de xuat giai thich lai, bai tap bo sung, hoac ghi nho bang tool_character_note khi that su huu ich.",
    ]

    if last_kind:
        lines.append(f"- Loai widget gan nhat: {last_kind}")
    if last_summary:
        lines.append(f"- Tom tat ket qua gan nhat: {last_summary}")

    if recent_items:
        lines.append("- Ket qua widget gan day:")
        for index, item in enumerate(recent_items[:5], start=1):
            if not isinstance(item, dict):
                continue
            widget_kind = str(item.get("widget_kind") or "").strip()
            summary = str(item.get("summary") or "").strip()
            status = str(item.get("status") or "").strip()
            title = str(item.get("title") or "").strip()
            score = item.get("score")
            correct_count = item.get("correct_count")
            total_count = item.get("total_count")

            metrics = []
            if isinstance(score, (int, float)):
                metrics.append(f"score={score}")
            if isinstance(correct_count, (int, float)) and isinstance(total_count, (int, float)):
                metrics.append(f"correct={correct_count}/{total_count}")

            details = " | ".join(
                part for part in (
                    widget_kind,
                    title,
                    status,
                    summary,
                    ", ".join(metrics) if metrics else "",
                ) if part
            )
            if details:
                lines.append(f"  {index}. {details}")

    return "\n".join(lines)


async def process_with_multi_agent(
    query: str,
    user_id: str,
    session_id: str = "",
    context: dict = None,
    domain_id: Optional[str] = None,
    thinking_effort: Optional[str] = None
) -> dict:
    """
    High-level function to process query with multi-agent system.

    Args:
        query: User query
        user_id: User identifier
        session_id: Session identifier
        context: Additional context
        domain_id: Domain plugin ID for domain-aware processing
        thinking_effort: Per-request thinking effort (low/medium/high/max)

    Returns:
        Dict with final_response, sources, trace info, etc.
    """
    domain_id = domain_id or settings.default_domain
    registry = get_agent_registry()

    # Start token tracking for this request (SOTA 2026)
    from app.core.token_tracker import start_tracking, get_tracker
    start_tracking(request_id=session_id or "")

    # Start request trace
    trace_id = registry.start_request_trace()
    logger.info("[MULTI_AGENT] Started trace: %s, domain=%s", trace_id, domain_id)

    # Load domain config for routing
    domain_config = _build_domain_config(domain_id)

    # Sprint 77: Convert LangChain messages to serializable dicts for AgentState
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
        "routing_metadata": None,  # Sprint 103: Initialize for API exposure
        "organization_id": (context or {}).get("organization_id"),  # Sprint 160
        **_build_turn_local_state_defaults(context),
    }

    # Sprint 222: Graph-level host context injection -- ALL agents get this
    _host_prompt = _inject_host_context(initial_state)
    if _host_prompt:
        initial_state["host_context_prompt"] = _host_prompt
    _visual_prompt = _inject_visual_context(initial_state)
    if _visual_prompt:
        initial_state["visual_context_prompt"] = _visual_prompt
    _widget_feedback_prompt = _inject_widget_feedback_context(initial_state)
    if _widget_feedback_prompt:
        initial_state["widget_feedback_prompt"] = _widget_feedback_prompt

    # Run graph with composite thread_id for per-user isolation (Sprint 16)
    # Sprint 170c: Include org_id for cross-org thread isolation
    invoke_config = {}
    if session_id and user_id:
        from app.core.thread_utils import build_thread_id
        _org_id = (context or {}).get("organization_id")
        thread_id = build_thread_id(user_id, session_id, org_id=_org_id)
        invoke_config = {"configurable": {"thread_id": thread_id}}
    elif session_id:
        invoke_config = {"configurable": {"thread_id": session_id}}

    # Sprint 144b: Attach LangSmith per-request callback for dashboard tracing
    from app.core.langsmith import get_langsmith_callback, is_langsmith_enabled
    if is_langsmith_enabled():
        ls_cb = get_langsmith_callback(user_id, session_id, domain_id)
        if ls_cb:
            invoke_config.setdefault("callbacks", []).append(ls_cb)

    # Sprint 85: Import event queue cleanup for sync path leak prevention
    from app.engine.multi_agent.graph_streaming import _cleanup_stale_queues

    # Sprint 85: Clean stale event queues before processing (sync path leak fix)
    _cleanup_stale_queues()

    # Sprint 153: try/finally to prevent _TRACERS memory leak on exceptions
    _trace_id_for_cleanup = initial_state.get("_trace_id")
    try:
        async with open_multi_agent_graph() as graph:
            result = await graph.ainvoke(initial_state, config=invoke_config)
        _trace_id_for_cleanup = result.get("_trace_id", _trace_id_for_cleanup)
    finally:
        # Sprint 139+153: Always clean up tracer from module-level storage
        _cleanup_tracer(_trace_id_for_cleanup)

    # Sprint 16: Upsert thread view for conversation index (non-blocking)
    if session_id and user_id:
        try:
            from app.repositories.thread_repository import get_thread_repository
            from app.core.thread_utils import build_thread_id as _build_tid
            _tid = _build_tid(user_id, session_id, org_id=(context or {}).get("organization_id"))
            _title = query[:60] + ("..." if len(query) > 60 else "")
            thread_data = get_thread_repository().upsert_thread(
                thread_id=_tid,
                user_id=user_id,
                domain_id=domain_id,
                title=_title,
            )

            # Sprint 79: Trigger background session summary at milestones
            if thread_data:
                count = thread_data.get("message_count", 0)
                if count in _SUMMARY_MILESTONES:
                    asyncio.create_task(_generate_session_summary_bg(_tid, user_id))
        except Exception as e:
            logger.warning("Thread upsert failed: %s", e)

    # End trace and get summary
    trace_summary = registry.end_request_trace(trace_id)
    logger.info("[MULTI_AGENT] Trace completed: %d spans, %.1fms",
                trace_summary.get('span_count', 0), trace_summary.get('total_duration_ms', 0))

    # Sprint 178: Persist LLM usage to admin analytics
    tracker = get_tracker()
    if tracker:
        try:
            _calls = getattr(tracker, "calls", None)
            if _calls:
                from app.services.llm_usage_logger import log_llm_usage_batch
                asyncio.ensure_future(log_llm_usage_batch(
                    request_id=session_id or "",
                    user_id=user_id or "",
                    session_id=session_id or "",
                    calls=_calls,
                    organization_id=(context or {}).get("organization_id"),
                ))
        except Exception as _usage_err:
            logger.debug("[MULTI_AGENT] LLM usage batch log failed: %s", _usage_err)

    return {
        "response": result.get("final_response", ""),
        "sources": result.get("sources", []),
        "tools_used": result.get("tools_used", []),  # SOTA: Track tool usage
        "grader_score": result.get("grader_score", 0),
        "agent_outputs": result.get("agent_outputs", {}),
        "current_agent": result.get("current_agent", ""),
        "next_agent": result.get("next_agent", ""),
        "error": result.get("error"),
        # CHỈ THỊ SỐ 28: SOTA Reasoning Trace for API transparency
        "reasoning_trace": result.get("reasoning_trace"),
        # CHỈ THỊ SỐ 29: Native thinking from Gemini (SOTA 2025)
        "thinking": result.get("thinking"),  # Priority: native Gemini thinking
        # CHỈ THỊ SỐ 28: Structured summary (fallback)
        "thinking_content": result.get("thinking_content"),
        # Sprint 80b: Domain notice for off-domain content
        "domain_notice": result.get("domain_notice"),
        # Sprint 103: Expose routing metadata (intent, confidence, reasoning) for API
        "routing_metadata": result.get("routing_metadata"),
        # Sprint 189b: Evidence images from RAG pipeline
        "evidence_images": result.get("evidence_images", []),
        # Trace info
        "trace_id": trace_id,
        "trace_summary": trace_summary,
        # SOTA 2026: Token usage accounting
        "token_usage": tracker.summary() if tracker else None,
    }


# =============================================================================
# V3 STREAMING: Extracted to graph_streaming.py
# Re-export for backward compatibility (lazy to avoid circular import)
# =============================================================================

def __getattr__(name):
    if name == "process_with_multi_agent_streaming":
        from app.engine.multi_agent.graph_streaming import process_with_multi_agent_streaming
        return process_with_multi_agent_streaming
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
