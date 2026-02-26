"""
Wiii MCP (Model Context Protocol) Integration — Sprints 56, 193.

Provides:
- MCP Server: Exposes Wiii REST endpoints via MCP for Claude Desktop, VS Code, Cursor
- MCP Client: Connects to external MCP servers, loads tools into LangGraph
- Schema Adapter: Converts between MCP tool schemas and OpenAI function format
- MCP Tool Server (Sprint 193): Exposes individual tools as MCP tool definitions

Feature-gated:
  enable_mcp_server=False
  enable_mcp_client=False
  enable_mcp_tool_server=False
  mcp_auto_register_external=False
"""

from app.mcp.client import MCPServerConfig, MCPToolManager
from app.mcp.tool_server import (
    MCPToolDefinition,
    MCPToolServer,
    get_mcp_tool_server,
)

__all__ = [
    "MCPServerConfig",
    "MCPToolManager",
    # Sprint 193
    "MCPToolDefinition",
    "MCPToolServer",
    "get_mcp_tool_server",
]
