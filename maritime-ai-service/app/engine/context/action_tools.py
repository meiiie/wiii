"""Sprint 222b Phase 5: Dynamic LangChain tool generation from host capabilities.

Generates StructuredTool instances from host-declared action definitions.
Each tool calls HostActionBridge.emit_action_request() when invoked.
"""
import json
import logging
from typing import Any

from langchain_core.tools import StructuredTool

from app.engine.context.action_bridge import HostActionBridge

logger = logging.getLogger(__name__)


def generate_host_action_tools(
    capabilities_tools: list[dict[str, Any]],
    user_role: str,
    event_bus_id: str,
) -> list[StructuredTool]:
    """Generate LangChain tools from host-declared action definitions.

    Filters by user role. Only creates tools the user is allowed to execute.
    Tools call HostActionBridge.emit_action_request() when invoked.
    """
    bridge = HostActionBridge(capabilities_tools=capabilities_tools)
    available = bridge.get_available_actions(user_role)

    tools: list[StructuredTool] = []
    for action_def in available:
        action_name = action_def["name"]
        description = action_def.get("description", f"Execute {action_name} on host")

        def _make_tool_fn(name: str, br: HostActionBridge, bus_id: str):
            def tool_fn(**kwargs: Any) -> str:
                request_id = br.emit_action_request(name, kwargs, bus_id)
                return json.dumps({
                    "status": "action_requested",
                    "request_id": request_id,
                    "action": name,
                    "params": kwargs,
                }, ensure_ascii=False)
            return tool_fn

        tool = StructuredTool.from_function(
            func=_make_tool_fn(action_name, bridge, event_bus_id),
            name=f"host_action__{action_name}",
            description=f"[Host Action] {description}",
        )
        tools.append(tool)

    return tools
