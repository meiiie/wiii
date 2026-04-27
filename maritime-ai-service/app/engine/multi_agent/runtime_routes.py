"""Route helpers used directly by the WiiiRunner runtime."""

from __future__ import annotations

from typing import Literal

from app.engine.multi_agent.guardian_runtime import guardian_route_impl
from app.engine.multi_agent.state import AgentState


def guardian_route(state: AgentState) -> Literal["supervisor", "synthesizer"]:
    """Route after guardian validation without depending on the legacy graph shell."""
    return guardian_route_impl(state)


__all__ = ["guardian_route"]
