"""
RAG Agent Node - Knowledge Retrieval Specialist

Uses Corrective RAG for intelligent document retrieval and generation.

**Integrated with agents/ framework for config and tracing.**
"""

import asyncio
import logging
from typing import Optional

from app.engine.agents import AgentConfig, RAG_AGENT_CONFIG
from app.engine.agentic_rag.corrective_rag import get_corrective_rag
from app.engine.multi_agent.state import AgentState
from app.engine.reasoning import ReasoningRenderRequest, get_reasoning_narrator

logger = logging.getLogger(__name__)


class RAGAgentNode:
    """
    RAG Agent - Knowledge retrieval specialist.

    Uses Corrective RAG with self-correction loop.

    Implements agents/ framework integration:
    - config property from RAG_AGENT_CONFIG
    - agent_id from config
    """

    _STEP_BEATS = {
        "analysis": ("clarify", "analysis"),
        "retrieval": ("retrieve", "retrieval"),
        "grading": ("verify", "grading"),
        "rewrite": ("retrieve", "rewrite"),
        "generation": ("synthesis", "generation"),
    }

    def __init__(self, rag_agent=None):
        """
        Initialize RAG Agent Node.

        Args:
            rag_agent: Optional base RAG agent for retrieval
        """
        self._corrective_rag = get_corrective_rag(rag_agent)
        self._config = RAG_AGENT_CONFIG
        logger.info("RAGAgentNode initialized with config: %s", self._config.id)

    async def process(self, state: AgentState) -> AgentState:
        """
        Process state through RAG pipeline.

        Sprint 144: When streaming via event bus, uses process_streaming()
        for progressive real-time events. Otherwise uses process() as before.

        Args:
            state: Current agent state

        Returns:
            Updated state with RAG output
        """
        query = state.get("query", "")
        context = {
            "user_id": state.get("user_id"),
            "session_id": state.get("session_id"),
            **state.get("context", {}),
        }

        _skill_ctx = state.get("skill_context")
        if _skill_ctx:
            context["skill_context"] = _skill_ctx

        _capability_ctx = state.get("capability_context")
        if _capability_ctx:
            context["capability_context"] = _capability_ctx

        _host_ctx = state.get("host_context_prompt", "")
        if _host_ctx:
            context["host_context_prompt"] = _host_ctx

        bus_id = state.get("_event_bus_id")
        event_queue = None
        if bus_id:
            from app.engine.multi_agent.graph_streaming import _get_event_queue

            event_queue = _get_event_queue(bus_id)

        try:
            if event_queue:
                result = await self._process_with_streaming(query, context, event_queue)
            else:
                result = await self._corrective_rag.process(query, context)

            if result is None:
                raise RuntimeError("process_streaming returned no result")

            state["rag_output"] = result.answer
            state["sources"] = result.sources
            state["evidence_images"] = getattr(result, "evidence_images", [])
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["rag"] = result.answer
            state["current_agent"] = "rag_agent"

            if result.grading_result:
                state["grader_score"] = result.grading_result.avg_score

            if result.reasoning_trace:
                state["reasoning_trace"] = result.reasoning_trace

            if result.thinking_content:
                state["thinking_content"] = result.thinking_content

            if result.thinking:
                state["thinking"] = result.thinking

            logger.info("[RAG_AGENT] Processed query with confidence=%.0f%%", result.confidence)

        except Exception as e:
            logger.error("[RAG_AGENT] Error: %s", e)
            state["rag_output"] = "Xin lỗi, đã xảy ra lỗi khi tra cứu. Vui lòng thử lại."
            state["error"] = "rag_error"
            state["evidence_images"] = []

        return state

    async def _process_with_streaming(
        self,
        query: str,
        context: dict,
        event_queue: asyncio.Queue,
    ):
        """Forward CRAG streaming events to the event bus."""

        result = None
        async for event in self._corrective_rag.process_streaming(query, context):
            etype = event.get("type", "")
            content = event.get("content", "")

            if etype == "status":
                event_queue.put_nowait({
                    "type": "status",
                    "content": content,
                    "node": "rag_agent",
                })
            elif etype == "thinking":
                step = str(event.get("step", "analysis"))
                phase, cue = self._STEP_BEATS.get(step, ("clarify", "general"))
                beat = await get_reasoning_narrator().render(
                    ReasoningRenderRequest(
                        node="rag_agent",
                        phase=phase,
                        cue=cue,
                        user_goal=query,
                        conversation_context=str(context.get("conversation_summary", "")),
                        capability_context=str(context.get("capability_context", "")),
                        next_action="Tiếp tục kéo các đoạn tài liệu đáng tin nhất lên trước.",
                        observations=[str(content or "")],
                        user_id=str(context.get("user_id", "__global__")),
                        organization_id=context.get("organization_id"),
                        personality_mode=context.get("personality_mode"),
                        mood_hint=context.get("mood_hint"),
                        visibility_mode="rich",
                        style_tags=["rag", step],
                    )
                )
                event_queue.put_nowait({
                    "type": "thinking_start",
                    "content": beat.label,
                    "node": "rag_agent",
                    "summary": beat.summary,
                    "details": {"phase": beat.phase, "rag_step": step},
                })
                event_queue.put_nowait({
                    "type": "thinking_delta",
                    "content": content or beat.summary,
                    "node": "rag_agent",
                })
                event_queue.put_nowait({
                    "type": "thinking_end",
                    "node": "rag_agent",
                })
            elif etype == "answer":
                event_queue.put_nowait({
                    "type": "answer_delta",
                    "content": content,
                    "node": "rag_agent",
                })
            elif etype == "result":
                result = event.get("data")

        return result

    @property
    def config(self) -> AgentConfig:
        """Get agent configuration."""
        return self._config

    @property
    def agent_id(self) -> str:
        """Get unique agent identifier."""
        return self._config.id

    def is_available(self) -> bool:
        """Check if RAG is available."""
        return self._corrective_rag.is_available()


_rag_node: Optional[RAGAgentNode] = None


def get_rag_agent_node(rag_agent=None) -> RAGAgentNode:
    """Get or create RAGAgentNode singleton."""
    global _rag_node
    if _rag_node is None:
        _rag_node = RAGAgentNode(rag_agent)
    return _rag_node
