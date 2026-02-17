"""
MCP Server — Exposes Wiii tools via Model Context Protocol.

Sprint 56: Mounts on existing FastAPI app at /mcp endpoint.
Uses fastapi-mcp to auto-expose REST endpoints + custom tool wrappers.

Feature-gated: enable_mcp_server=False by default.
Transport: Streamable HTTP (MCP spec 2025-03-26).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def setup_mcp_server(app) -> Optional[object]:
    """
    Mount MCP server on the FastAPI application.

    Auto-exposes selected REST endpoints as MCP tools, allowing
    Claude Desktop, VS Code, Cursor, and other MCP clients to
    interact with Wiii's knowledge base and tools.

    Args:
        app: FastAPI application instance

    Returns:
        FastApiMCP instance if mounted, None otherwise.
    """
    from app.core.config import settings

    if not settings.enable_mcp_server:
        logger.debug("MCP Server disabled (enable_mcp_server=False)")
        return None

    try:
        from fastapi_mcp import FastApiMCP
    except ImportError:
        logger.warning(
            "fastapi-mcp not installed — MCP Server unavailable. "
            "Install with: pip install fastapi-mcp>=0.3.0"
        )
        return None

    try:
        mcp = FastApiMCP(
            app,
            name="Wiii MCP Server",
            description=(
                "Multi-Domain Agentic RAG Platform by The Wiii Lab. "
                "Provides knowledge search, memory management, and teaching tools."
            ),
            # Only expose chat and knowledge endpoints, not admin/health
            # Operation IDs must match FastAPI's auto-generated names
            include_operations=[
                "chat_completion_api_v1_chat_post",
                "chat_stream_v3_api_v1_chat_stream_v3_post",
                "get_user_insights_api_v1_insights__user_id__get",
                "get_user_memories_api_v1_memories__user_id__get",
                "get_statistics_api_v1_knowledge_stats_get",
            ],
            # Forward auth headers from MCP client to tool invocations
            headers=[
                "authorization",
                "X-API-Key",
                "X-User-ID",
                "X-Session-ID",
                "X-Role",
                "X-Organization-ID",
            ],
        )
        mcp.mount_http()
        logger.info("[OK] MCP Server mounted at /mcp (Streamable HTTP)")
        return mcp

    except Exception as e:
        logger.warning("MCP Server setup failed: %s", e)
        return None
