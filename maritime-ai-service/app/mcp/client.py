"""
MCP Client — Connects to external MCP servers and loads tools.

Sprint 56: Uses langchain-mcp-adapters for LangGraph-compatible tool loading.
Supports stdio, HTTP (Streamable HTTP), and SSE transports.

Feature-gated: enable_mcp_client=False by default.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for connecting to an external MCP server."""

    name: str
    transport: str = "stdio"  # "stdio" | "http" | "sse"
    url: Optional[str] = None  # For http/sse transport
    command: Optional[str] = None  # For stdio transport
    args: List[str] = field(default_factory=list)  # For stdio transport
    headers: Dict[str, str] = field(default_factory=dict)  # For http transport
    enabled: bool = True


class MCPToolManager:
    """
    Manages MCP client connections and tool loading.

    Connects to external MCP servers at startup, loads their tools,
    and makes them available as LangChain-compatible tools for use
    in LangGraph agent nodes.
    """

    _client: Optional[object] = None
    _tools: List = []
    _initialized: bool = False
    _configs: List[MCPServerConfig] = []

    @classmethod
    async def initialize(cls, configs: List[MCPServerConfig]) -> None:
        """
        Initialize MCP client connections.

        Args:
            configs: List of MCP server configurations to connect to.
        """
        if not configs:
            logger.info("No MCP server configs provided — skipping initialization")
            cls._initialized = True
            return

        enabled_configs = [c for c in configs if c.enabled]
        if not enabled_configs:
            logger.info("All MCP servers disabled — skipping initialization")
            cls._initialized = True
            return

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            logger.warning(
                "langchain-mcp-adapters not installed — MCP Client unavailable. "
                "Install with: pip install langchain-mcp-adapters>=0.1.0"
            )
            cls._initialized = True
            return

        server_dict = {}
        for config in enabled_configs:
            server_entry = {"transport": config.transport}

            if config.transport == "stdio":
                if not config.command:
                    logger.warning(
                        "MCP server '%s' missing command — skipped",
                        config.name,
                    )
                    continue
                server_entry["command"] = config.command
                server_entry["args"] = config.args

            elif config.transport in ("http", "sse"):
                if not config.url:
                    logger.warning(
                        "MCP server '%s' missing URL — skipped",
                        config.name,
                    )
                    continue
                server_entry["url"] = config.url
                if config.headers:
                    server_entry["headers"] = config.headers

            server_dict[config.name] = server_entry

        if not server_dict:
            logger.info("No valid MCP server configs — skipping")
            cls._initialized = True
            return

        try:
            cls._client = MultiServerMCPClient(server_dict)
            cls._tools = await cls._client.get_tools()
            cls._configs = enabled_configs
            cls._initialized = True
            logger.info(
                "[OK] MCP Client initialized: %d tools "
                "from %d server(s)",
                len(cls._tools), len(server_dict),
            )
        except Exception as e:
            logger.warning("MCP Client initialization failed: %s", e)
            cls._tools = []
            cls._initialized = True

    @classmethod
    def get_tools(cls) -> List:
        """Get all loaded MCP tools (LangChain-compatible)."""
        return cls._tools

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the MCP client has been initialized."""
        return cls._initialized

    @classmethod
    async def shutdown(cls) -> None:
        """Close MCP client connections."""
        if cls._client is not None:
            try:
                if hasattr(cls._client, "close"):
                    await cls._client.close()
                elif hasattr(cls._client, "__aexit__"):
                    await cls._client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("MCP Client shutdown error: %s", e)
            finally:
                cls._client = None
        cls._tools = []
        cls._initialized = False
        logger.info("MCP Client shut down")

    @classmethod
    def reset(cls) -> None:
        """Reset all state. Used in tests."""
        cls._client = None
        cls._tools = []
        cls._initialized = False
        cls._configs = []

    @classmethod
    def parse_configs(cls, json_str: str) -> List[MCPServerConfig]:
        """
        Parse MCP server configs from JSON string (settings.mcp_server_configs).

        Args:
            json_str: JSON array of server config objects.

        Returns:
            List of MCPServerConfig instances.
        """
        try:
            raw = json.loads(json_str)
            if not isinstance(raw, list):
                return []
            configs = []
            for item in raw:
                if isinstance(item, dict):
                    configs.append(MCPServerConfig(**item))
            return configs
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse MCP server configs: %s", e)
            return []
