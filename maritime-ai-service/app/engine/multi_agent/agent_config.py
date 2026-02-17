"""
Per-Agent Provider Configuration Registry — Sprint 69.

Each LangGraph node (tutor, supervisor, guardian, etc.) can have
its own provider/model/tier config. All default to Gemini now but
can be reconfigured per-node via settings.agent_provider_configs JSON.

Usage:
    config = AgentConfigRegistry.get_config("tutor_agent")
    llm = AgentConfigRegistry.get_llm("tutor_agent")
    llm = AgentConfigRegistry.get_llm("direct", effort_override="high")
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentNodeConfig:
    """Configuration for a single LangGraph node."""

    node_id: str
    provider: str = "google"        # "google" | "openai" | "ollama"
    model: Optional[str] = None     # None = use provider default for tier
    tier: str = "moderate"          # "deep" | "moderate" | "light"
    temperature: float = 0.5
    max_agentic_steps: int = 5
    enable_thinking: bool = True
    enable_agentic_loop: bool = False


# Default configs — all Gemini, easy to switch per-node later
_DEFAULT_CONFIGS: Dict[str, AgentNodeConfig] = {
    "tutor_agent": AgentNodeConfig(
        "tutor_agent", tier="moderate", enable_agentic_loop=True,
    ),
    "rag_agent": AgentNodeConfig("rag_agent", tier="moderate"),
    "supervisor": AgentNodeConfig(
        "supervisor", tier="light", temperature=0.3,
    ),
    "guardian": AgentNodeConfig(
        "guardian", tier="light", temperature=0.0,
    ),
    "grader": AgentNodeConfig("grader", tier="moderate"),
    "memory": AgentNodeConfig("memory", tier="light", temperature=0.5),
    "direct": AgentNodeConfig("direct", tier="light"),
    "synthesizer": AgentNodeConfig("synthesizer", tier="moderate"),
}


class AgentConfigRegistry:
    """Singleton registry for per-node LLM configuration."""

    _configs: Dict[str, AgentNodeConfig] = {}
    _initialized: bool = False

    @classmethod
    def initialize(cls, overrides_json: str = "{}") -> None:
        """Initialize with defaults + optional JSON overrides."""
        cls._configs = {k: AgentNodeConfig(
            node_id=v.node_id,
            provider=v.provider,
            model=v.model,
            tier=v.tier,
            temperature=v.temperature,
            max_agentic_steps=v.max_agentic_steps,
            enable_thinking=v.enable_thinking,
            enable_agentic_loop=v.enable_agentic_loop,
        ) for k, v in _DEFAULT_CONFIGS.items()}

        # Apply JSON overrides
        try:
            overrides = json.loads(overrides_json) if overrides_json else {}
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "[AGENT_CONFIG] Invalid JSON overrides, using defaults"
            )
            overrides = {}

        for node_id, node_overrides in overrides.items():
            if not isinstance(node_overrides, dict):
                continue
            if node_id in cls._configs:
                config = cls._configs[node_id]
            else:
                config = AgentNodeConfig(node_id)
                cls._configs[node_id] = config

            for key, value in node_overrides.items():
                if hasattr(config, key) and key != "node_id":
                    setattr(config, key, value)

        cls._initialized = True
        logger.info(
            "[AGENT_CONFIG] Initialized %d node configs", len(cls._configs),
        )

    @classmethod
    def get_config(cls, node_id: str) -> AgentNodeConfig:
        """Get config for a node, falling back to defaults."""
        if not cls._initialized:
            cls.initialize()
        return cls._configs.get(node_id, AgentNodeConfig(node_id))

    @classmethod
    def get_llm(cls, node_id: str, effort_override: Optional[str] = None):
        """
        Get a LangChain LLM for the given node based on its config.

        If effort_override is provided, uses get_llm_for_effort() instead
        (Sprint 66 per-request thinking effort).
        """
        from app.engine.llm_pool import (
            get_llm_deep, get_llm_moderate, get_llm_light,
        )

        config = cls.get_config(node_id)

        if effort_override:
            from app.engine.llm_pool import get_llm_for_effort
            from app.engine.llm_factory import ThinkingTier
            tier_default_map = {
                "deep": ThinkingTier.DEEP,
                "moderate": ThinkingTier.MODERATE,
                "light": ThinkingTier.LIGHT,
            }
            default_tier = tier_default_map.get(
                config.tier, ThinkingTier.MODERATE,
            )
            return get_llm_for_effort(effort_override, default_tier=default_tier)

        tier_map = {
            "deep": get_llm_deep,
            "moderate": get_llm_moderate,
            "light": get_llm_light,
        }
        get_llm_fn = tier_map.get(config.tier, get_llm_moderate)
        return get_llm_fn()

    @classmethod
    def reset(cls) -> None:
        """Reset registry (for testing)."""
        cls._configs = {}
        cls._initialized = False
