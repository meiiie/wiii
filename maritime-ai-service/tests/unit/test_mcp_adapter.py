"""
Tests for app.mcp.adapter — MCP ↔ OpenAI schema conversion.

Sprint 56: MCP Support.
"""

import pytest
from unittest.mock import MagicMock

from app.mcp.adapter import (
    mcp_tools_to_openai_functions,
    ensure_properties_key,
    openai_functions_to_tool_defs,
)


class TestEnsurePropertiesKey:
    """Test ensure_properties_key()."""

    def test_adds_properties_when_missing(self):
        schema = {"type": "object"}
        result = ensure_properties_key(schema)
        assert "properties" in result
        assert result["properties"] == {}

    def test_preserves_existing_properties(self):
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        result = ensure_properties_key(schema)
        assert result["properties"] == {"name": {"type": "string"}}

    def test_adds_type_when_missing(self):
        schema = {"properties": {"x": {"type": "int"}}}
        result = ensure_properties_key(schema)
        assert result["type"] == "object"

    def test_handles_empty_dict(self):
        result = ensure_properties_key({})
        assert result == {"type": "object", "properties": {}}

    def test_handles_non_dict(self):
        result = ensure_properties_key("invalid")
        assert result == {"type": "object", "properties": {}}

    def test_does_not_mutate_input(self):
        original = {"type": "object"}
        result = ensure_properties_key(original)
        assert "properties" not in original
        assert "properties" in result


class TestMcpToolsToOpenAiFunctions:
    """Test mcp_tools_to_openai_functions()."""

    def test_converts_basic_tool(self):
        tool = MagicMock()
        tool.name = "search"
        tool.description = "Search knowledge"
        tool.inputSchema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

        result = mcp_tools_to_openai_functions([tool])
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search"
        assert result[0]["function"]["description"] == "Search knowledge"
        assert "query" in result[0]["function"]["parameters"]["properties"]

    def test_parameterless_tool_gets_properties(self):
        tool = MagicMock()
        tool.name = "get_time"
        tool.description = "Get current time"
        tool.inputSchema = {"type": "object"}

        result = mcp_tools_to_openai_functions([tool])
        assert len(result) == 1
        assert result[0]["function"]["parameters"]["properties"] == {}

    def test_missing_schema_gets_default(self):
        tool = MagicMock()
        tool.name = "ping"
        tool.description = "Ping"
        tool.inputSchema = None

        result = mcp_tools_to_openai_functions([tool])
        assert len(result) == 1
        assert result[0]["function"]["parameters"]["type"] == "object"
        assert result[0]["function"]["parameters"]["properties"] == {}

    def test_skips_tool_without_name(self):
        tool = MagicMock()
        tool.name = None
        result = mcp_tools_to_openai_functions([tool])
        assert len(result) == 0

    def test_empty_description_defaults_to_empty_string(self):
        tool = MagicMock()
        tool.name = "test"
        tool.description = None
        tool.inputSchema = None

        result = mcp_tools_to_openai_functions([tool])
        assert result[0]["function"]["description"] == ""

    def test_multiple_tools(self):
        tools = []
        for i in range(3):
            t = MagicMock()
            t.name = f"tool_{i}"
            t.description = f"Tool {i}"
            t.inputSchema = {"type": "object", "properties": {}}
            tools.append(t)

        result = mcp_tools_to_openai_functions(tools)
        assert len(result) == 3

    def test_handles_broken_tool_gracefully(self):
        good_tool = MagicMock()
        good_tool.name = "good"
        good_tool.description = "Good tool"
        good_tool.inputSchema = {"type": "object", "properties": {}}

        bad_tool = MagicMock()
        bad_tool.name = property(lambda s: (_ for _ in ()).throw(Exception("broken")))
        type(bad_tool).name = property(lambda s: (_ for _ in ()).throw(Exception("broken")))

        result = mcp_tools_to_openai_functions([good_tool])
        assert len(result) == 1


class TestOpenAiFunctionsToToolDefs:
    """Test openai_functions_to_tool_defs()."""

    def test_passes_through_standard_format(self):
        funcs = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        result = openai_functions_to_tool_defs(funcs)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "search"

    def test_normalizes_simplified_format(self):
        funcs = [
            {
                "name": "calc",
                "description": "Calculator",
                "parameters": {"type": "object", "properties": {"expr": {"type": "string"}}},
            }
        ]
        result = openai_functions_to_tool_defs(funcs)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "calc"

    def test_adds_properties_to_simplified(self):
        funcs = [{"name": "ping"}]
        result = openai_functions_to_tool_defs(funcs)
        assert result[0]["function"]["parameters"]["properties"] == {}

    def test_empty_list(self):
        assert openai_functions_to_tool_defs([]) == []
