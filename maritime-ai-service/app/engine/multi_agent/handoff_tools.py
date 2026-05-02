"""Agent handoff tools — allow agents to transfer control mid-execution.

Pattern from OpenAI Agents SDK: handoffs appear as tools to the LLM.
When called, the orchestrator loop detects ``_handoff_target`` in state
and transfers control to the target agent.

Valid handoff targets match the registered node names in WiiiRunner.
"""

from __future__ import annotations

from app.engine.tools.native_tool import tool

_VALID_HANDOFF_TARGETS = frozenset({
    "rag_agent",
    "tutor_agent",
    "direct",
    "code_studio_agent",
    "product_search_agent",
    "memory_agent",
})

_HANDOFF_DESCRIPTION = (
    "Transfer the conversation to a different specialist agent. "
    "Use when the current query would be better handled by another agent. "
    "Available agents: rag_agent (knowledge retrieval), tutor_agent (teaching), "
    "memory_agent (user facts), direct (general Q&A), code_studio_agent (code/visuals), "
    "product_search_agent (shopping). Use sparingly — only when truly needed."
)


@tool("handoff_to_agent", description=_HANDOFF_DESCRIPTION)
async def handoff_to_agent(target_agent: str, reason: str = "") -> str:
    """Hand off conversation to a different specialist agent.

    Args:
        target_agent: Name of the target agent. Must be one of:
            rag_agent, tutor_agent, memory_agent, direct,
            code_studio_agent, product_search_agent.
        reason: Brief reason for the handoff (1-2 sentences).
    Returns:
        Confirmation string — the actual handoff executes after this tool returns.
    """
    if target_agent not in _VALID_HANDOFF_TARGETS:
        valid = ", ".join(sorted(_VALID_HANDOFF_TARGETS))
        return f"Invalid agent '{target_agent}'. Choose from: {valid}"
    return f"Handoff to {target_agent} acknowledged. Reason: {reason or 'not specified'}"


def is_handoff_tool_call(tool_name: str) -> bool:
    """Check if a tool call is a handoff request."""
    return tool_name == "handoff_to_agent"


def extract_handoff_target(tool_args: dict) -> str | None:
    """Extract and validate handoff target from tool call arguments."""
    target = tool_args.get("target_agent", "")
    if target in _VALID_HANDOFF_TARGETS:
        return target
    return None
