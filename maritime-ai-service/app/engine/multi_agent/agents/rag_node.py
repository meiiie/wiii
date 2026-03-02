"""
RAG Agent Node - Knowledge Retrieval Specialist

Uses Corrective RAG for intelligent document retrieval and generation.

**Integrated with agents/ framework for config and tracing.**
"""

import asyncio
import logging
from typing import Optional

from app.engine.multi_agent.state import AgentState
from app.engine.agentic_rag.corrective_rag import get_corrective_rag
from app.engine.agents import RAG_AGENT_CONFIG, AgentConfig

logger = logging.getLogger(__name__)


class RAGAgentNode:
    """
    RAG Agent - Knowledge retrieval specialist.
    
    Uses Corrective RAG with self-correction loop.
    
    Implements agents/ framework integration:
    - config property from RAG_AGENT_CONFIG
    - agent_id from config
    """
    
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
            **state.get("context", {})
        }

        # Sprint 222: Thread graph-level host context into RAG pipeline
        _host_ctx = state.get("host_context_prompt", "")
        if _host_ctx:
            context["host_context_prompt"] = _host_ctx

        # Sprint 144: Progressive streaming via event bus
        bus_id = state.get("_event_bus_id")
        event_queue = None
        if bus_id:
            from app.engine.multi_agent.graph_streaming import _get_event_queue
            event_queue = _get_event_queue(bus_id)

        try:
            if event_queue:
                # STREAMING MODE: progressive events via process_streaming()
                result = await self._process_with_streaming(query, context, event_queue)
            else:
                # NON-STREAMING: single await as before
                result = await self._corrective_rag.process(query, context)

            if result is None:
                raise RuntimeError("process_streaming returned no result")

            # Update state
            state["rag_output"] = result.answer
            state["sources"] = result.sources
            state["evidence_images"] = getattr(result, "evidence_images", [])  # Sprint 189b
            state["agent_outputs"] = state.get("agent_outputs", {})
            state["agent_outputs"]["rag"] = result.answer
            state["current_agent"] = "rag_agent"

            # Add metadata
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
            state["evidence_images"] = []  # Sprint 189b: ensure clean state

        return state

    # Vietnamese labels for CRAG pipeline step names
    _STEP_LABELS = {
        "analysis": "Phân tích câu hỏi",
        "retrieval": "Kết quả tìm kiếm",
        "grading": "Đánh giá chất lượng",
        "rewrite": "Tinh chỉnh câu hỏi",
        "generation": "Tạo câu trả lời",
    }

    async def _process_with_streaming(
        self,
        query: str,
        context: dict,
        event_queue: asyncio.Queue,
    ):
        """Sprint 144: Forward CRAG streaming events to the event bus.

        Consumes process_streaming() async generator, forwards thinking/answer
        events to the bus queue for real-time frontend display, and returns
        the CorrectiveRAGResult from the final 'result' event.
        """
        result = None
        async for event in self._corrective_rag.process_streaming(query, context):
            etype = event.get("type", "")
            content = event.get("content", "")

            if etype == "status":
                # Pipeline status → status event for progress panel (not thinking block)
                event_queue.put_nowait({
                    "type": "status",
                    "content": content,
                    "node": "rag_agent",
                })
            elif etype == "thinking":
                # Deep reasoning → expandable thinking block with Vietnamese label
                step = event.get("step", "Phân tích")
                label = self._STEP_LABELS.get(step, step)
                event_queue.put_nowait({
                    "type": "thinking_start",
                    "content": label,
                    "node": "rag_agent",
                })
                event_queue.put_nowait({
                    "type": "thinking_delta",
                    "content": content,
                    "node": "rag_agent",
                })
                event_queue.put_nowait({
                    "type": "thinking_end",
                    "node": "rag_agent",
                })
            elif etype == "answer":
                # Answer token → answer_delta for interleaved display
                event_queue.put_nowait({
                    "type": "answer_delta",
                    "content": content,
                    "node": "rag_agent",
                })
            elif etype == "result":
                # Final CorrectiveRAGResult
                result = event.get("data")
            # sources, metadata, done, error — handled by graph_streaming post-node

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


# Singleton
_rag_node: Optional[RAGAgentNode] = None

def get_rag_agent_node(rag_agent=None) -> RAGAgentNode:
    """Get or create RAGAgentNode singleton."""
    global _rag_node
    if _rag_node is None:
        _rag_node = RAGAgentNode(rag_agent)
    return _rag_node
