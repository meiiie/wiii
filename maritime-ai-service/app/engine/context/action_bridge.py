"""Sprint 222b Phase 5: HostActionBridge — bidirectional host action management.

Validates AI tool calls against host-declared capabilities,
emits SSE events for frontend to forward via PostMessage,
and tracks pending action requests.
"""
import logging
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HostActionBridge:
    """Manages bidirectional action requests between AI agents and host app."""

    def __init__(self, capabilities_tools: list[dict[str, Any]]):
        self._tools: dict[str, dict[str, Any]] = {}
        for tool_def in capabilities_tools:
            name = tool_def.get("name", "")
            if name:
                self._tools[name] = tool_def
        self.pending_requests: dict[str, dict[str, Any]] = {}

    def validate_action(self, action: str, params: dict, user_role: str) -> bool:
        tool_def = self._tools.get(action)
        if not tool_def:
            return False
        roles = tool_def.get("roles")
        if roles is None:
            return True
        return user_role in roles

    def get_available_actions(self, user_role: str) -> list[dict[str, Any]]:
        result = []
        for tool_def in self._tools.values():
            roles = tool_def.get("roles")
            if roles is None or user_role in roles:
                result.append(tool_def)
        return result

    def get_action_definition(self, action: str) -> Optional[dict[str, Any]]:
        return self._tools.get(action)

    def emit_action_request(self, action: str, params: dict[str, Any],
                            event_bus_id: str) -> str:
        tool_def = self._tools.get(action) or {}
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        self.pending_requests[request_id] = {
            "action": action,
            "params": params,
            "event_bus_id": event_bus_id,
            "requires_confirmation": bool(tool_def.get("requires_confirmation")),
            "mutates_state": bool(tool_def.get("mutates_state")),
            "surface": tool_def.get("surface"),
        }
        logger.info("[ACTION_BRIDGE] Emitted action request %s: %s", request_id, action)
        return request_id

    def resolve_action(self, request_id: str, result: dict[str, Any]) -> Optional[dict[str, Any]]:
        req = self.pending_requests.pop(request_id, None)
        if req:
            logger.info("[ACTION_BRIDGE] Resolved action %s: %s → success=%s",
                        request_id, req["action"], result.get("success"))
        return req
