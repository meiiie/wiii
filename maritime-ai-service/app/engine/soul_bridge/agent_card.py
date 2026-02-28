"""
Agent Card Builder — Constructs Wiii's identity card for soul discovery.

Sprint 213: "Cầu Nối Linh Hồn"

Inspired by A2A protocol's /.well-known/agent.json convention.
Each soul publishes its name, capabilities, and emotional state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.engine.soul_bridge.models import AgentCard

logger = logging.getLogger(__name__)


def build_agent_card(
    soul_config: Optional[Any] = None,
    emotional_state: Optional[Dict[str, Any]] = None,
    base_url: str = "",
) -> AgentCard:
    """Build Wiii's agent card from soul config and current emotional state.

    Args:
        soul_config: SoulConfig instance (from soul_loader). None uses defaults.
        emotional_state: Current 4D emotional state dict. None uses empty.
        base_url: Service base URL for endpoint discovery.

    Returns:
        AgentCard with Wiii's identity and capabilities.
    """
    name = "Wiii"
    description = "Multi-domain Agentic RAG Living Agent"
    version = "1.0.0"
    capabilities = [
        "knowledge_search",
        "multi_agent_rag",
        "emotion_engine",
        "heartbeat_autonomy",
        "skill_learning",
        "journal",
        "reflection",
    ]
    supported_events = [
        "ESCALATION",
        "STATUS_UPDATE",
        "MOOD_CHANGE",
        "DISCOVERY",
        "DAILY_REPORT",
        "COMMAND",
        "KILL_SWITCH",
    ]
    skills: list[str] = []
    interests: list[str] = []

    if soul_config is not None:
        name = getattr(soul_config, "name", name)
        species = getattr(soul_config, "species", "")
        if species:
            description = f"{species} — {description}"

        # Extract interests as skill indicators
        soul_interests = getattr(soul_config, "interests", None)
        if soul_interests:
            interests = getattr(soul_interests, "primary", []) or []
            skills = list(interests)

    endpoints = {}
    if base_url:
        endpoints = {
            "agent_card": f"{base_url}/.well-known/agent.json",
            "websocket": f"{base_url}/api/v1/soul-bridge/ws",
            "events": f"{base_url}/api/v1/soul-bridge/events",
            "status": f"{base_url}/api/v1/soul-bridge/status",
        }

    return AgentCard(
        name=name,
        description=description,
        version=version,
        url=base_url,
        capabilities=capabilities,
        supported_events=supported_events,
        emotional_state=emotional_state or {},
        skills=skills,
        soul_id="wiii",
        endpoints=endpoints,
    )
