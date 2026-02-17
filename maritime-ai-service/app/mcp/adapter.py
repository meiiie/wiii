"""
MCP ↔ OpenAI Schema Adapter — Converts between tool formats.

Sprint 56: Bridges MCP tool schemas to OpenAI function calling format
used by the UnifiedLLMClient (Sprint 55) and agentic loop (Sprint 57).

Key constraint: OpenAI REQUIRES "properties" key in function parameters,
even for parameterless tools. MCP tools may omit this.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def mcp_tools_to_openai_functions(mcp_tools: list) -> List[Dict[str, Any]]:
    """
    Convert MCP tools to OpenAI function calling format.

    Args:
        mcp_tools: List of MCP tool objects (with .name, .description, .inputSchema)

    Returns:
        List of OpenAI-compatible tool definitions.
    """
    result = []
    for tool in mcp_tools:
        try:
            name = getattr(tool, "name", None)
            if not name:
                continue

            description = getattr(tool, "description", "") or ""
            schema = getattr(tool, "inputSchema", None) or {
                "type": "object",
                "properties": {},
            }

            schema = ensure_properties_key(schema)

            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": schema,
                    },
                }
            )
        except Exception as e:
            logger.warning("Failed to convert MCP tool: %s", e)
            continue

    return result


def ensure_properties_key(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure schema has 'properties' key (OpenAI requirement).

    OpenAI function calling requires parameters.properties to exist,
    even if the tool takes no arguments. MCP tools may omit this.

    Args:
        schema: JSON Schema dict from MCP tool

    Returns:
        Schema dict with guaranteed 'properties' key.
    """
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    result = dict(schema)
    if "properties" not in result:
        result["properties"] = {}

    if "type" not in result:
        result["type"] = "object"

    return result


def openai_functions_to_tool_defs(
    functions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Normalize OpenAI function definitions for consistent processing.

    Accepts both formats:
    - {"type": "function", "function": {...}} (OpenAI standard)
    - {"name": "...", "description": "...", "parameters": {...}} (simplified)

    Returns:
        List of normalized {"type": "function", "function": {...}} dicts.
    """
    result = []
    for func_def in functions:
        if "function" in func_def:
            result.append(func_def)
        elif "name" in func_def:
            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": func_def["name"],
                        "description": func_def.get("description", ""),
                        "parameters": ensure_properties_key(
                            func_def.get("parameters", {})
                        ),
                    },
                }
            )
    return result
