"""
Wiii MCP (Model Context Protocol) Integration — Sprint 56.

Provides:
- MCP Server: Exposes Wiii tools via MCP for Claude Desktop, VS Code, Cursor
- MCP Client: Connects to external MCP servers, loads tools into LangGraph
- Schema Adapter: Converts between MCP tool schemas and OpenAI function format

Feature-gated: enable_mcp_server / enable_mcp_client (default: False)
"""
