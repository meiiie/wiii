"""
RAG Tools - Knowledge Retrieval Tools for Wiii

Category: RAG (Knowledge Retrieval)
Access: READ (safe, no mutations)
"""

import contextvars
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from langchain_core.tools import tool

from app.engine.tools.registry import (
    ToolCategory, ToolAccess, get_tool_registry
)

logger = logging.getLogger(__name__)


# =============================================================================
# ASYNC-SAFE STATE (contextvars for per-request isolation)
# =============================================================================

@dataclass
class RAGToolState:
    """Per-request state for RAG tools. Isolated between concurrent requests."""
    sources: List[Dict[str, str]] = field(default_factory=list)
    native_thinking: Optional[str] = None
    reasoning_trace: Optional[Any] = None
    confidence: float = 0.0
    is_complete: bool = False


# ContextVar: each async request gets its own RAGToolState
_rag_tool_state: contextvars.ContextVar[RAGToolState] = contextvars.ContextVar(
    '_rag_tool_state', default=None
)

# RAG agent is a singleton (shared across requests) - this is safe as module-level
_rag_agent = None


def _get_state() -> RAGToolState:
    """Get or create per-request RAG tool state."""
    state = _rag_tool_state.get(None)
    if state is None:
        state = RAGToolState()
        _rag_tool_state.set(state)
    return state


def init_rag_tools(rag_agent):
    """Initialize RAG tools with the RAG agent (singleton, safe)."""
    global _rag_agent
    _rag_agent = rag_agent
    logger.info("RAG tools initialized")


def get_last_retrieved_sources() -> List[Dict[str, str]]:
    """Get the last retrieved sources for API response (per-request)."""
    return _get_state().sources


def get_last_native_thinking() -> Optional[str]:
    """
    Get the last native thinking from RAG for SOTA reasoning transparency.
    Per-request isolated via contextvars.
    """
    return _get_state().native_thinking


def get_last_reasoning_trace():
    """
    Get the last reasoning_trace from RAG for SOTA trace merge.
    Per-request isolated via contextvars.
    """
    return _get_state().reasoning_trace


def get_last_confidence() -> tuple[float, bool]:
    """
    Get the last confidence score and completion flag from RAG.
    Per-request isolated via contextvars.
    """
    state = _get_state()
    return state.confidence, state.is_complete


def clear_retrieved_sources():
    """Reset per-request state for a new request."""
    _rag_tool_state.set(RAGToolState())


# =============================================================================
# RAG TOOLS
# =============================================================================

@tool(description="""
Tra cứu kiến thức từ cơ sở dữ liệu chuyên ngành.
CHỈ gọi khi user hỏi về kiến thức chuyên môn cần tra cứu.
""")
async def tool_knowledge_search(query: str) -> str:
    """Search domain knowledge base.

    Uses CorrectiveRAG for full 8-step trace with per-request state isolation.
    Generic name for multi-domain support. Alias: tool_maritime_search.
    """
    # Import CorrectiveRAG for SOTA trace generation
    from app.engine.agentic_rag.corrective_rag import get_corrective_rag

    if not _rag_agent:
        return "Lỗi: RAG Agent không khả dụng. Không thể tra cứu kiến thức."

    # Get per-request state (async-safe via contextvars)
    state = _get_state()

    try:
        logger.info("[TOOL] Knowledge Search (CRAG): %s", query)

        crag = get_corrective_rag(_rag_agent)
        crag_result = await crag.process(query, context={})

        result = crag_result.answer

        # Normalize confidence from 0-100 (CRAG internal) to 0-1 (config thresholds)
        from app.core.config import settings
        state.confidence = crag_result.confidence / 100.0
        state.is_complete = state.confidence >= settings.rag_confidence_high
        logger.info("[TOOL] Confidence: %.2f, is_complete: %s (threshold=%s)", state.confidence, state.is_complete, settings.rag_confidence_high)

        # Store CRAG trace for propagation (per-request)
        state.reasoning_trace = crag_result.reasoning_trace
        if state.reasoning_trace:
            logger.info("[TOOL] CRAG trace captured: %d steps", state.reasoning_trace.total_steps)

        # Capture native thinking (per-request)
        state.native_thinking = crag_result.thinking
        if state.native_thinking:
            logger.info("[TOOL] Native thinking captured: %d chars", len(state.native_thinking))

        # Store sources for API response (per-request)
        if crag_result.sources:
            state.sources = [
                {
                    "node_id": src.get("node_id", ""),
                    "title": src.get("title", ""),
                    "content": src.get("content", "")[:500] if src.get("content") else "",
                    "image_url": src.get("image_url"),
                    "page_number": src.get("page_number"),
                    "document_id": src.get("document_id"),
                    "bounding_boxes": src.get("bounding_boxes")
                }
                for src in crag_result.sources[:5]
            ]
            for i, src in enumerate(state.sources[:2]):
                logger.info("[TOOL] Source %d: page=%s, doc=%s, bbox=%s", i+1, src.get('page_number'), src.get('document_id'), bool(src.get('bounding_boxes')))
            logger.info("[TOOL] Saved %d sources for API response", len(state.sources))

            sources_text = [f"- {src.get('title', 'Unknown')}" for src in crag_result.sources[:3]]
            result += "\n\n**Nguồn tham khảo:**\n" + "\n".join(sources_text)
        else:
            state.sources = []

        confidence_signal = f"\n\n<!-- CONFIDENCE: {state.confidence:.2f} | IS_COMPLETE: {state.is_complete} -->"
        return result + confidence_signal

    except Exception as e:
        logger.error("Knowledge search error: %s", e)
        # Reset state on error
        _rag_tool_state.set(RAGToolState())
        return f"Lỗi khi tra cứu: {str(e)}"


# =============================================================================
# REGISTER TOOLS
# =============================================================================

def register_rag_tools():
    """Register all RAG tools with the registry."""
    registry = get_tool_registry()

    registry.register(
        tool=tool_knowledge_search,
        category=ToolCategory.RAG,
        access=ToolAccess.READ,
        description="Search domain knowledge base"
    )

    logger.info("RAG tools registered")


# Backward compatibility alias
tool_maritime_search = tool_knowledge_search


# Auto-register on import
register_rag_tools()
