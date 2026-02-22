"""
Multi-Agent Graph - Phase 8.4

LangGraph workflow for multi-agent orchestration.

Pattern: Supervisor with specialized worker agents

**Integrated with agents/ framework for registry and tracing.**

**CHỈ THỊ SỐ 30: Universal ReasoningTrace for ALL paths**
"""

import logging
import re
from typing import Dict, Optional, Literal


from langgraph.graph import StateGraph, END

from app.core.config import settings
from app.engine.multi_agent.state import AgentState
from app.engine.multi_agent.supervisor import get_supervisor_agent
from app.engine.multi_agent.agents.rag_node import get_rag_agent_node
from app.engine.multi_agent.agents.tutor_node import get_tutor_agent_node
from app.engine.multi_agent.agents.memory_agent import get_memory_agent_node
from app.engine.multi_agent.agents.grader_agent import get_grader_agent_node

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
    import uuid
    tracer = get_reasoning_tracer()
    trace_id = str(uuid.uuid4())
    _TRACERS[trace_id] = tracer
    state["_trace_id"] = trace_id
    return tracer


def _cleanup_tracer(trace_id: Optional[str]) -> None:
    """Remove tracer from module-level storage after graph completes."""
    if trace_id and trace_id in _TRACERS:
        del _TRACERS[trace_id]


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


def _needs_news_search(query: str) -> bool:
    """Detect if query needs news search (Sprint 102)."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _NEWS_INTENT_KEYWORDS)


def _needs_legal_search(query: str) -> bool:
    """Detect if query needs legal search (Sprint 102)."""
    normalized = _normalize_for_intent(query)
    return any(kw in normalized for kw in _LEGAL_INTENT_KEYWORDS)


def _build_direct_tools_context(settings_obj, domain_name_vi: str) -> str:
    """Build tools context string for direct node from settings + knowledge limits.

    Sprint 100: Extracted from direct_response_node f-string soup.
    Produces the same content as Sprint 97b-99 tool hints + knowledge limits.
    """
    tool_hints = []
    if settings_obj.enable_character_tools:
        tool_hints.append(
            "- tool_character_note: Ghi chú khi user chia sẻ thông tin cá nhân MỚI."
        )
    tool_hints.append(
        "- tool_current_datetime: Lấy ngày giờ hiện tại (UTC+7). "
        "BẮT BUỘC gọi khi user hỏi 'hôm nay ngày mấy', 'bây giờ mấy giờ', hoặc bất kỳ câu hỏi về thời gian hiện tại."
    )
    tool_hints.append(
        "- tool_web_search: Tìm kiếm TỔNG HỢP trên web. "
        "Dùng khi câu hỏi KHÔNG thuộc tin tức, pháp luật, hay hàng hải. "
        "VD: thời tiết, giá vàng, thông tin chung."
    )
    # Sprint 102: Specialized search tools
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
    if settings_obj.enable_code_execution:
        tool_hints.append(
            "- tool_execute_python: Chạy code Python trong sandbox. "
            "Dùng khi user yêu cầu tính toán, viết code, hoặc xử lý dữ liệu."
        )

    parts = []
    parts.append("## CÔNG CỤ CÓ SẴN:\n" + "\n".join(tool_hints))
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


def _collect_direct_tools(query: str):
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
    except Exception:
        pass

    try:
        if settings.enable_code_execution:
            from app.engine.tools.code_execution_tools import get_code_execution_tools
            _direct_tools.extend(get_code_execution_tools())
    except Exception:
        pass

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
    except Exception:
        pass

    force_tools = bool(_direct_tools) and (
        _needs_web_search(query) or _needs_datetime(query)
        or _needs_news_search(query) or _needs_legal_search(query)
    )
    return _direct_tools, force_tools


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


def _build_direct_system_messages(state: AgentState, query: str, domain_name_vi: str):
    """Build system prompt and message list for direct response.

    Sprint 154: Extracted from direct_response_node.

    Returns:
        list: LangChain messages [SystemMessage, ...history, HumanMessage]
    """
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.prompts.prompt_loader import get_prompt_loader

    ctx = state.get("context", {})
    loader = get_prompt_loader()
    tools_ctx = _build_direct_tools_context(settings, domain_name_vi)
    system_prompt = loader.build_system_prompt(
        role="direct_agent",
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
    )

    messages = [SystemMessage(content=system_prompt)]
    lc_messages = ctx.get("langchain_messages", [])
    if lc_messages:
        messages.extend(lc_messages[-10:])
    messages.append(HumanMessage(content=query))
    return messages


async def _execute_direct_tool_rounds(
    llm_with_tools, llm_auto, messages: list, tools: list, push_event,
    max_rounds: int = 3,
):
    """Execute multi-round tool calling loop for direct response.

    Sprint 154: Extracted from direct_response_node.
    Gemini often calls tools sequentially (datetime → web_search → answer).

    Returns:
        tuple: (AIMessage, messages, tool_call_events) — final response, messages, and
               structured tool events for downstream preview emission (Sprint 166).
    """
    import asyncio
    from langchain_core.messages import ToolMessage as _TM

    tool_call_events: list[dict] = []

    llm_response = await llm_with_tools.ainvoke(messages)
    _tc = getattr(llm_response, 'tool_calls', [])
    logger.warning("[DIRECT] LLM response: tool_calls=%d, content_len=%d",
                   len(_tc) if _tc else 0, len(str(llm_response.content)))

    for _tool_round in range(max_rounds):
        if not (tools and hasattr(llm_response, 'tool_calls') and llm_response.tool_calls):
            break
        messages.append(llm_response)
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
            matched = next((t for t in tools if t.name == _tc_name), None)
            try:
                result = await asyncio.to_thread(matched.invoke, tc["args"]) if matched else "Unknown tool"
            except Exception as _te:
                logger.warning("[DIRECT] Tool %s failed: %s", _tc_name, _te)
                result = "Tool unavailable"
            await push_event({
                "type": "tool_result",
                "content": {"name": _tc_name, "result": str(result)[:500], "id": _tc_id},
                "node": "direct",
            })
            # Sprint 166: Store full result for preview extraction
            tool_call_events.append({
                "type": "result", "name": _tc_name,
                "result": str(result), "id": _tc_id,
            })
            messages.append(_TM(content=str(result), tool_call_id=_tc_id))
        llm_response = await llm_auto.ainvoke(messages)

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
            except Exception:
                pass

    # CHỈ THỊ SỐ 30: Get inherited tracer from supervisor
    tracer = _get_or_create_tracer(state)
    tracer.start_step(StepNames.DIRECT_RESPONSE, "Tạo phản hồi trực tiếp")

    # Load greetings from domain plugin (falls back to defaults)
    greetings = _get_domain_greetings(state.get("domain_id", settings.default_domain))

    query_lower = query.lower().strip()
    response = greetings.get(query_lower)

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

            thinking_effort = state.get("thinking_effort")
            llm = AgentConfigRegistry.get_llm("direct", effort_override=thinking_effort)
            if llm:
                # Phase 1: Collect tools and determine forcing
                tools, force_tools = _collect_direct_tools(query)
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

                # Phase 4: Multi-round tool execution
                llm_response, messages, _tc_events = await _execute_direct_tool_rounds(
                    llm_with_tools, llm_auto, messages, tools, _push_event,
                )

                # Sprint 166: Store tool_call_events for preview extraction
                if _tc_events:
                    state["tool_call_events"] = _tc_events

                # Phase 5: Extract response
                response, thinking_content, tools_used = _extract_direct_response(llm_response, messages)

                if thinking_content:
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
                response = "Xin chào! Tôi có thể giúp gì cho bạn?"
                tracer.end_step(
                    result="Fallback (LLM unavailable)",
                    confidence=0.5,
                    details={"response_type": "fallback"}
                )
        except Exception as e:
            logger.warning("[DIRECT] LLM generation failed: %s", e)
            response = "Xin chào! Tôi có thể giúp gì cho bạn?"
            tracer.end_step(
                result=f"Fallback (error): {str(e)[:50]}",
                confidence=0.5,
                details={"response_type": "fallback", "error": str(e)[:100]}
            )

    state["final_response"] = response
    state["agent_outputs"] = {"direct": response}
    state["current_agent"] = "direct"

    # Sprint 80b: Set domain notice if supervisor detected off-topic/general intent
    routing_meta = state.get("routing_metadata", {})
    intent = routing_meta.get("intent", "") if routing_meta else ""
    if intent in ("off_topic", "general", "greeting"):
        state["domain_notice"] = (
            f"Nội dung này nằm ngoài chuyên môn {domain_name_vi}. "
            f"Để được hỗ trợ chính xác hơn, hãy hỏi về {domain_name_vi} nhé!"
        )

    logger.info("[DIRECT] Response prepared, tracer passed to synthesizer")

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
    except Exception:
        pass


async def _run_rag_subagent(state: dict, **kwargs) -> "SubagentResult":
    """Adapter: run existing RAG agent and wrap output as SubagentResult."""
    from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus

    # Sprint 164: Emit thinking lifecycle events for desktop UX
    _emit_subagent_event(state, {
        "type": "thinking_start",
        "content": "Tra cứu tri thức",
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
            error_message=str(e),
        )


async def _run_tutor_subagent(state: dict, **kwargs) -> "SubagentResult":
    """Adapter: run existing Tutor agent and wrap output as SubagentResult."""
    from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus

    # Sprint 164: Emit thinking lifecycle events for desktop UX
    _emit_subagent_event(state, {
        "type": "thinking_start",
        "content": "Soạn bài giảng",
        "node": "tutor",
    })
    _emit_subagent_event(state, {
        "type": "status",
        "content": "Phân tích câu hỏi và chuẩn bị nội dung...",
        "node": "tutor",
    })

    try:
        tutor_agent = get_tutor_agent_node()
        result_state = await tutor_agent.process(state)

        _emit_subagent_event(state, {
            "type": "status",
            "content": "Soạn nội dung giảng dạy...",
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
            error_message=str(e),
        )


async def _run_search_subagent(state: dict, **kwargs) -> "SubagentResult":
    """Adapter: run product search and wrap output as SubagentResult."""
    from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus

    # Sprint 164: Emit thinking lifecycle events for desktop UX
    _emit_subagent_event(state, {
        "type": "thinking_start",
        "content": "Tìm kiếm sản phẩm",
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
            error_message=str(e),
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
        except Exception:
            pass

    # Build task list for parallel execution
    tasks = []
    timeout = 60
    try:
        from app.core.config import settings as _settings
        timeout = _settings.subagent_default_timeout
    except Exception:
        pass

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
    except Exception:
        pass

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
        "direct", "product_search_agent", "parallel_dispatch",
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
    workflow.add_node("grader", grader_node)
    workflow.add_node("synthesizer", synthesizer_node)
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
    }
    if settings.enable_product_search:
        _routing_map["product_search_agent"] = "product_search_agent"
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

    # Sprint 148: Product search → Synthesizer (skip grader — comparison data, not knowledge)
    if settings.enable_product_search:
        workflow.add_edge("product_search_agent", "synthesizer")

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

_graph = None


def get_multi_agent_graph():
    """Get or create Multi-Agent Graph singleton (sync, no checkpointer)."""
    global _graph
    if _graph is None:
        _graph = build_multi_agent_graph()
    return _graph


async def get_multi_agent_graph_async():
    """
    Get or create Multi-Agent Graph singleton with checkpointer.

    SOTA 2026: Async initialization enables PostgreSQL-backed
    LangGraph checkpointing for multi-turn conversation persistence.
    """
    global _graph
    if _graph is None:
        from app.engine.multi_agent.checkpointer import get_checkpointer
        checkpointer = await get_checkpointer()
        _graph = build_multi_agent_graph(checkpointer=checkpointer)
    return _graph


async def _generate_session_summary_bg(thread_id: str, user_id: str) -> None:
    """Background: generate session summary for cross-session preamble (Sprint 79)."""
    try:
        from app.services.session_summarizer import get_session_summarizer
        summarizer = get_session_summarizer()
        await summarizer.summarize_thread(thread_id, user_id)
    except Exception as e:
        logger.debug("Background session summary failed: %s", e)


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
    graph = await get_multi_agent_graph_async()
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
    }
    
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
                    import asyncio
                    asyncio.create_task(_generate_session_summary_bg(_tid, user_id))
        except Exception as e:
            logger.warning("Thread upsert failed: %s", e)

    # End trace and get summary
    trace_summary = registry.end_request_trace(trace_id)
    logger.info("[MULTI_AGENT] Trace completed: %d spans, %.1fms",
                trace_summary.get('span_count', 0), trace_summary.get('total_duration_ms', 0))

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
        # Trace info
        "trace_id": trace_id,
        "trace_summary": trace_summary,
        # SOTA 2026: Token usage accounting
        "token_usage": get_tracker().summary() if get_tracker() else None,
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


