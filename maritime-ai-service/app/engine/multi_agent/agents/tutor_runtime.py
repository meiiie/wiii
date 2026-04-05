"""Runtime helpers for tutor node initialization."""

import logging

from app.engine.multi_agent.agent_config import AgentConfigRegistry


def initialize_tutor_llm(*, tools: list, logger: logging.Logger):
    """Initialize the tutor LLM and bind the current toolset."""
    try:
        llm = AgentConfigRegistry.get_llm("tutor_agent")
        llm_with_tools = llm.bind_tools(tools)
        logger.info("[TUTOR_AGENT] LLM bound with %d tools (via AgentConfigRegistry)", len(tools))
        return llm, llm_with_tools
    except Exception as exc:
        logger.error("Failed to initialize Tutor LLM: %s", exc)
        return None, None
