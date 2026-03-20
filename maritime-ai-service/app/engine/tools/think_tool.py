"""
Sprint 147: Think Tool — Dedicated scratchpad for structured mid-workflow reflection.

Inspired by Anthropic's "think" tool pattern (54% improvement on policy-heavy domains).
Instead of thinking inline, the model calls tool_think(thought) to reason explicitly
about complex decisions. The thought content is streamed as thinking_delta events
(visible in ThinkingBlock UI) rather than as a tool result card.

The tool itself is a no-op — it just records that reasoning occurred.
The real work happens in the agent node, which intercepts tool_think calls
and routes the thought content to the thinking display pipeline.

Phase2: Added persona_label field — short cute Wiii-voice label for the UI header.
LLM fills this as part of the structured tool call (works with Function Calling).
"""

import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool("tool_think")
def tool_think(thought: str, persona_label: str = "") -> str:
    """Use this tool to think step-by-step about complex problems.

    Record your reasoning, analyze evidence, consider alternatives, verify your
    understanding before answering. This is your private scratchpad — the user
    won't see the raw thought, but it helps you reason more carefully.

    Use this tool when:
    - Comparing multiple pieces of information
    - Checking if retrieved documents are sufficient
    - Planning your response structure
    - Verifying your understanding before answering

    Args:
        thought: Your reasoning, analysis, or reflection.
        persona_label: A SHORT cute label (<10 words) in Wiii's voice to show
            the user what Wiii is doing. Examples:
            "Hmm để Wiii xem nào~"
            "Ồ, Wiii tìm thấy rồi nè!"
            "Để Wiii kiểm tra lại~"
            "Wiii đang phân tích đây ≽^•⩊•^≼"

    Returns:
        Acknowledgment that the thought was recorded.
    """
    char_count = len(thought)
    label_info = f", label='{persona_label}'" if persona_label else ""
    logger.debug("[THINK_TOOL] Thought recorded: %d chars%s", char_count, label_info)
    return f"[Thought recorded: {char_count} chars]"
