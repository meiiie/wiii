"""HostAdapter ABC — per-host-type context interpreter.

Sprint 222: Universal Context Engine.
Each host type (LMS, ecommerce, CRM, etc.) gets its own adapter
that knows how to format HostContext into an AI-prompt-ready block.
"""
from abc import ABC, abstractmethod

from app.engine.context.host_context import HostContext


class HostAdapter(ABC):
    """Base class for host-specific context adapters."""

    host_type: str = "abstract"

    @abstractmethod
    def format_context_for_prompt(self, ctx: HostContext) -> str:
        """Format host context as XML-tagged block for system prompt injection."""

    def get_page_skill_ids(self, ctx: HostContext) -> list[str]:
        """Return skill IDs relevant to the current page (for tool selection)."""
        return []

    def validate_action(self, action: str, params: dict, user_role: str) -> bool:
        """Check whether a host action is allowed for the given user role."""
        return True
