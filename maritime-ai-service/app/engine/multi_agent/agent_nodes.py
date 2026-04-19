"""Agent node wrappers for LangGraph multi-agent graph.

Extracted from graph.py — thin delegation wrappers that call
external agent implementations (rag_node, tutor_node, etc.).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.core.config import settings
from app.engine.multi_agent.state import AgentState

from app.engine.multi_agent.supervisor import get_supervisor_agent
from app.engine.reasoning_tracer import StepNames
from app.engine.agents import get_agent_registry
from app.engine.multi_agent.visual_intent_resolver import (
    merge_thinking_effort,
    recommended_visual_thinking_effort,
)

logger = logging.getLogger(__name__)


def _get_graph_helpers():
    """Lazy import graph helpers to avoid circular deps."""
    from app.engine.multi_agent.graph_trace_store import _get_or_create_tracer
    from app.engine.multi_agent.code_studio_context import _get_active_code_studio_session
    return _get_or_create_tracer, _get_active_code_studio_session

async def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor node - routes to appropriate agent.

    CHỈ THỊ SỐ 30: Adds ROUTING step to reasoning trace.
    """
    registry = get_agent_registry()
    
    # CHỈ THỊ SỐ 30: Universal tracing - start routing step
    get_tracer, _ = _get_graph_helpers(); tracer = get_tracer(state)
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

        explicit_effort = state.get("thinking_effort")

        if explicit_effort:
            result_state["thinking_effort"] = explicit_effort

        # Sprint 147: Set thinking_effort from routing intent if not already set
        if not explicit_effort:
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
            _reasoning_policy = result_state.get("reasoning_policy")
            if isinstance(_reasoning_policy, dict):
                result_state["thinking_effort"] = merge_thinking_effort(
                    result_state.get("thinking_effort"),
                    _reasoning_policy.get("deliberation_level"),
                )

        if not explicit_effort:
            upgraded_effort = recommended_visual_thinking_effort(
                result_state.get("query", "") or state.get("query", ""),
                active_code_session=_get_graph_helpers()[1](result_state),
            )
            result_state["thinking_effort"] = merge_thinking_effort(
                result_state.get("thinking_effort"),
                upgraded_effort,
            )

        return result_state


async def rag_node(state: AgentState) -> AgentState:
    """RAG agent node - knowledge retrieval."""
    registry = get_agent_registry()
    with registry.tracer.span("rag_agent", "process"):
        from app.engine.multi_agent.agents.rag_node import get_rag_agent_node

        rag_agent = get_rag_agent_node()
        return await rag_agent.process(state)


async def tutor_node(state: AgentState) -> AgentState:
    """Tutor agent node - teaching."""
    registry = get_agent_registry()
    with registry.tracer.span("tutor_agent", "process"):
        from app.engine.multi_agent.agents.tutor_node import get_tutor_agent_node

        tutor_agent = get_tutor_agent_node()
        return await tutor_agent.process(state)


async def memory_node(state: AgentState) -> AgentState:
    """
    Memory agent node — Sprint 72: Retrieve-Extract-Respond.

    CHỈ THỊ SỐ 30: Adds MEMORY_LOOKUP step to reasoning trace.
    """
    registry = get_agent_registry()

    # CHỈ THỊ SỐ 30: Universal tracing
    get_tracer, _ = _get_graph_helpers(); tracer = get_tracer(state)
    tracer.start_step(StepNames.MEMORY_LOOKUP, "Truy xuất ngữ cảnh và bộ nhớ người dùng")

    with registry.tracer.span("memory_agent", "process"):
        from app.engine.multi_agent.agents.memory_agent import get_memory_agent_node

        # Sprint 72: Get LLM via AgentConfigRegistry for response generation
        from app.engine.multi_agent.agent_config import AgentConfigRegistry
        try:
            thinking_effort = state.get("thinking_effort")
            llm = AgentConfigRegistry.get_llm(
                "memory",
                effort_override=thinking_effort,
                provider_override=state.get("provider"),
                requested_model=state.get("model"),
            )
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
    get_tracer, _ = _get_graph_helpers(); tracer = get_tracer(state)
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
    get_tracer, _ = _get_graph_helpers(); tracer = get_tracer(state)
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


# Sprint 233: grader_node removed — CRAG pipeline provides confidence directly.
# grader_agent.py kept for reference but no longer wired into graph.


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
    get_tracer, _ = _get_graph_helpers(); tracer = get_tracer(state)
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

    # Tracer cleanup happens in process_with_multi_agent() after runner.run()
    # _trace_id in state is just a string key — safe for msgpack serialization

    return state
