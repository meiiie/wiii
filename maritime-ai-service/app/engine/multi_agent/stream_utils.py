"""
Stream Utilities for Multi-Agent Graph Streaming

SOTA Dec 2025: LangGraph 1.0 astream_events() pattern
Pattern: OpenAI Responses API + Claude Extended Thinking + Gemini astream

This module provides utilities to stream events from LangGraph execution,
transforming internal graph events into user-friendly SSE events.

**Feature: v3-full-graph-streaming**
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# =============================================================================
# EVENT TYPES (OpenAI Responses API pattern)
# =============================================================================

class StreamEventType:
    """Standard event types for SSE streaming."""
    STATUS = "status"           # Processing stage updates (typing indicator)
    THINKING = "thinking"       # AI reasoning steps (collapsible section)
    TOOL_CALL = "tool_call"     # Tool invocation (transparency)
    TOOL_RESULT = "tool_result" # Tool result summary
    ANSWER = "answer"           # Response tokens (streamed real-time)
    SOURCES = "sources"         # Citation list with image_url
    METADATA = "metadata"       # reasoning_trace, confidence, timing
    THINKING_DELTA = "thinking_delta"   # Incremental thinking token (real-time)
    THINKING_START = "thinking_start"  # Thinking block opened (lifecycle)
    THINKING_END = "thinking_end"      # Thinking block closed (lifecycle)
    DONE = "done"               # Stream complete
    ERROR = "error"             # Error occurred
    DOMAIN_NOTICE = "domain_notice"  # Gentle notice: content outside active domain


# =============================================================================
# NODE NAME MAPPINGS (User-friendly descriptions)
# =============================================================================

NODE_DESCRIPTIONS = {
    "supervisor": "🎯 Phân tích và định tuyến câu hỏi",
    "rag_agent": "📚 Tra cứu cơ sở tri thức",
    "tutor_agent": "👨‍🏫 Tạo bài giảng",
    "memory_agent": "🧠 Truy xuất bộ nhớ",
    "direct": "💬 Tạo phản hồi trực tiếp",
    "grader": "✅ Kiểm tra chất lượng",
    "synthesizer": "📝 Tổng hợp câu trả lời"
}

NODE_STEPS = {
    "supervisor": "routing",
    "rag_agent": "retrieval",
    "tutor_agent": "teaching",
    "memory_agent": "memory_lookup",
    "direct": "direct_response",
    "grader": "quality_check",
    "synthesizer": "synthesis"
}


# =============================================================================
# STREAM EVENT DATACLASS
# =============================================================================

@dataclass
class StreamEvent:
    """
    Unified stream event for SSE.
    
    Attributes:
        type: Event type (status, thinking, answer, etc.)
        content: Event content (string or dict)
        node: Source node name (optional)
        step: Reasoning step name (optional)
        confidence: Confidence score 0-1 (optional)
        details: Additional details (optional)
    """
    type: str
    content: Any
    node: Optional[str] = None
    step: Optional[str] = None
    confidence: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for SSE serialization."""
        result = {
            "type": self.type,
            "content": self.content
        }
        if self.node:
            result["node"] = self.node
        if self.step:
            result["step"] = self.step
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.details:
            result["details"] = self.details
        return result


# =============================================================================
# STREAM EVENT GENERATORS
# =============================================================================

async def create_status_event(
    message: str,
    node: Optional[str] = None
) -> StreamEvent:
    """Create a status event for progress indication."""
    return StreamEvent(
        type=StreamEventType.STATUS,
        content=message,
        node=node,
        step=NODE_STEPS.get(node) if node else None
    )


async def create_thinking_event(
    content: str,
    step: str,
    confidence: Optional[float] = None,
    details: Optional[Dict] = None
) -> StreamEvent:
    """Create a thinking event for reasoning transparency."""
    return StreamEvent(
        type=StreamEventType.THINKING,
        content=content,
        step=step,
        confidence=confidence,
        details=details
    )


async def create_answer_event(content: str) -> StreamEvent:
    """Create an answer token event."""
    return StreamEvent(
        type=StreamEventType.ANSWER,
        content=content
    )


async def create_sources_event(sources: List[Dict]) -> StreamEvent:
    """Create a sources event with citations."""
    return StreamEvent(
        type=StreamEventType.SOURCES,
        content=sources
    )


async def create_metadata_event(
    reasoning_trace: Optional[Dict] = None,
    processing_time: float = 0,
    confidence: float = 0,
    **kwargs
) -> StreamEvent:
    """Create a metadata event with full trace info."""
    content = {
        "reasoning_trace": reasoning_trace,
        "processing_time": processing_time,
        "confidence": confidence,
        "streaming_version": "v3",
        **kwargs
    }
    return StreamEvent(
        type=StreamEventType.METADATA,
        content=content
    )


async def create_done_event(total_time: float = 0) -> StreamEvent:
    """Create a done event signaling stream completion."""
    return StreamEvent(
        type=StreamEventType.DONE,
        content={"status": "complete", "total_time": round(total_time, 3)}
    )


async def create_error_event(message: str) -> StreamEvent:
    """Create an error event."""
    return StreamEvent(
        type=StreamEventType.ERROR,
        content={"message": message}
    )


async def create_thinking_start_event(
    label: str,
    node: str,
    block_id: Optional[str] = None,
) -> StreamEvent:
    """Create a thinking_start event to open a new thinking block."""
    return StreamEvent(
        type=StreamEventType.THINKING_START,
        content=label,
        node=node,
        details={"block_id": block_id} if block_id else None,
    )


async def create_thinking_end_event(
    node: str,
    duration_ms: Optional[int] = None,
    block_id: Optional[str] = None,
) -> StreamEvent:
    """Create a thinking_end event to close the current thinking block."""
    details: Optional[Dict[str, Any]] = None
    if duration_ms is not None or block_id is not None:
        details = {}
        if duration_ms is not None:
            details["duration_ms"] = duration_ms
        if block_id is not None:
            details["block_id"] = block_id
    return StreamEvent(
        type=StreamEventType.THINKING_END,
        content="",
        node=node,
        details=details,
    )


async def create_tool_call_event(
    tool_name: str,
    tool_args: Dict[str, Any],
    tool_call_id: str,
    node: Optional[str] = None,
) -> StreamEvent:
    """Create a tool call event for agentic loop transparency."""
    return StreamEvent(
        type=StreamEventType.TOOL_CALL,
        content={"name": tool_name, "args": tool_args, "id": tool_call_id},
        node=node,
        step="tool_execution",
    )


async def create_tool_result_event(
    tool_name: str,
    result_summary: str,
    tool_call_id: str,
    node: Optional[str] = None,
) -> StreamEvent:
    """Create a tool result event for agentic loop transparency."""
    return StreamEvent(
        type=StreamEventType.TOOL_RESULT,
        content={"name": tool_name, "result": result_summary, "id": tool_call_id},
        node=node,
        step="tool_execution",
    )


async def create_domain_notice_event(message: str) -> StreamEvent:
    """Create a domain_notice event — gentle UI indicator for off-domain content."""
    return StreamEvent(
        type=StreamEventType.DOMAIN_NOTICE,
        content=message,
    )


async def create_thinking_delta_event(
    content: str,
    node: Optional[str] = None,
) -> StreamEvent:
    """Create a thinking_delta event for incremental thinking token streaming."""
    return StreamEvent(
        type=StreamEventType.THINKING_DELTA,
        content=content,
        node=node,
    )


