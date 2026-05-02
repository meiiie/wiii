"""
Sprint 148: Progress Report Tool — Multi-Phase Thinking Chain.

Inspired by Claude's multi-phase thinking pattern where the model
produces 3+ thinking blocks per response with intermediate narratives.

The LLM calls tool_report_progress to:
1. Close the current thinking block (thinking_end)
2. Emit bold narrative text (action_text)
3. Open a new thinking block (thinking_start) with a new label

The tool itself returns a simple acknowledgment — the real work
happens in tutor_node._react_loop, which intercepts the call
and routes the phase transition events to the streaming pipeline.
"""

import logging
from app.engine.tools.native_tool import tool

logger = logging.getLogger(__name__)


@tool("tool_report_progress")
def tool_report_progress(message: str, phase_label: str = "") -> str:
    """Report progress to the user and start a new analysis phase.

    Call this tool when you've completed one phase of analysis and want to
    communicate your progress before starting the next phase.

    Examples:
    - After searching documents: message="Đã tìm được 3 tài liệu liên quan", phase_label="Phân tích chi tiết"
    - After initial analysis: message="Phân tích xong câu hỏi", phase_label="Tìm kiếm tài liệu"

    Args:
        message: Progress message shown to the user (Vietnamese, 1-2 sentences)
        phase_label: Label for the next thinking phase (e.g., "Tìm kiếm tài liệu")

    Returns:
        Acknowledgment string.
    """
    next_phase = phase_label or "continuing"
    logger.debug("[PROGRESS_TOOL] Phase transition: '%s' -> '%s'", message, next_phase)
    return f"[Progress reported. Next phase: {next_phase}]"
