"""Agent-as-Tool pattern — wrap any agent as a callable LangChain tool.

Inspired by OpenAI Agents SDK `agent.as_tool()` pattern:
- Agent becomes a tool with description (LLM decides when to call)
- Agent runs in isolation with only the query (no conversation history)
- Result returned as string (truncated to avoid context bloat)
- Fail-graceful: errors return fallback message, calling agent still functions

SOTA 2026: The LLM reads tool descriptions and decides when to delegate.
No separate routing step needed — composition happens at tool-call level.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.engine.tools.native_tool import tool

logger = logging.getLogger(__name__)


@dataclass
class AgentToolConfig:
    """Configuration for wrapping an agent as a callable tool."""

    name: str
    description: str
    agent_fn: Callable  # async (query: str) -> str
    fallback: str = "Không truy xuất được lúc này."
    max_chars: int = 3000


def create_agent_tool(config: AgentToolConfig) -> Any:
    """Wrap an agent as a LangChain @tool that the LLM can call.

    The calling agent sees this as a regular tool with a description.
    The LLM decides when to call it based on the description text.
    The wrapped agent runs in isolation with only the query string.
    """

    @tool(description=config.description)
    async def _agent_tool(query: str) -> str:
        """Delegates query to a specialized agent and returns the result."""
        try:
            result = await config.agent_fn(query)
            text = str(result or "").strip()
            if not text:
                return config.fallback
            if len(text) > config.max_chars:
                return text[: config.max_chars] + "..."
            return text
        except Exception as exc:
            logger.warning("[AGENT_TOOL] %s failed: %s", config.name, exc)
            return config.fallback

    _agent_tool.name = config.name
    return _agent_tool


# ---------------------------------------------------------------------------
# Pre-built: RAG Knowledge Delegation
# ---------------------------------------------------------------------------


async def _rag_agent_fn(query: str) -> str:
    """Call RAG agent directly for knowledge retrieval.

    Creates a minimal state with only the query (no conversation history).
    The RAG agent runs its full CorrectiveRAG pipeline internally.
    """
    from app.engine.multi_agent.agents.rag_node import get_rag_agent_node

    agent = get_rag_agent_node()

    minimal_state = {
        "query": query,
        "context": {},
        "messages": [],
    }

    try:
        from app.core.org_context import get_current_org_id

        org_id = get_current_org_id()
        if org_id:
            minimal_state["context"]["organization_id"] = org_id
    except Exception:
        pass

    result_state = await agent.process(minimal_state)
    return str(result_state.get("rag_output", ""))


RAG_KNOWLEDGE_TOOL = create_agent_tool(
    AgentToolConfig(
        name="tool_rag_knowledge",
        description=(
            "Tra cứu kiến thức chuyên ngành từ cơ sở dữ liệu nội bộ. "
            "Dùng khi cần thông tin chuyên sâu về quy định, luật, thủ tục "
            "(COLREGs, SOLAS, MARPOL, luật giao thông, v.v.) "
            "mà kiến thức chung không đủ trả lời. "
            "Input: câu hỏi cần tra cứu. Output: kết quả tra cứu."
        ),
        agent_fn=_rag_agent_fn,
        fallback="Không truy xuất được kiến thức nội bộ lúc này.",
    )
)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_agent_tools() -> None:
    """Register all agent-as-tool tools with the ToolRegistry."""
    try:
        from app.engine.tools.registry import ToolCategory, ToolAccess, get_tool_registry

        registry = get_tool_registry()

        registry.register(
            tool=RAG_KNOWLEDGE_TOOL,
            category=ToolCategory.RAG,
            access=ToolAccess.READ,
            description="Delegate to RAG knowledge agent for domain-specific retrieval",
        )

        logger.info("[AGENT_TOOLS] Registered %d agent tools", 1)
    except Exception as exc:
        logger.warning("[AGENT_TOOLS] Registration failed: %s", exc)


def get_agent_tools() -> list:
    """Return all agent-as-tool functions for binding."""
    return [RAG_KNOWLEDGE_TOOL]
