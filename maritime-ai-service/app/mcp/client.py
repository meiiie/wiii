"""MCP Client — connects to external MCP servers using the raw ``mcp`` SDK.

Phase 9c (runtime migration epic #207): replaced ``langchain_mcp_adapters``
with the official ``mcp`` Python SDK. The wrapper exposes a small native
``MCPTool`` shape (``name``, ``description``, ``parameters``, ``ainvoke``)
so the downstream consumers (``ToolRegistry`` + ``WiiiChatModel.bind_tools``)
do not need to learn the LangChain ``BaseTool`` interface.

Sprint 56 introduced the manager; Sprint 193 added the
``register_discovered_tools()`` bridge into ``ToolRegistry``.
"""

from __future__ import annotations

import contextlib
import json
import logging
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional

from app.mcp.policy import infer_external_tool_registration

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


class MCPTool:
    """Lightweight wrapper around an MCP tool definition.

    Exposes the duck-typed surface required by ``ToolRegistry.register`` and
    ``WiiiChatModel.bind_tools``:

    - ``name`` / ``description`` — string metadata
    - ``parameters`` — JSON schema dict (OpenAI tool format)
    - ``ainvoke(arguments)`` — async dispatcher that calls back through the
      live ``ClientSession``
    """

    __slots__ = ("name", "description", "parameters", "_session", "_server_name")

    def __init__(
        self,
        *,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        session: Any,
        server_name: str,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self._session = session
        self._server_name = server_name

    async def ainvoke(self, arguments: Optional[Dict[str, Any]] = None) -> str:
        """Call the underlying MCP tool. Returns the textual result."""
        result = await self._session.call_tool(self.name, arguments or {})
        # MCP `call_tool` returns CallToolResult with `.content` as a list of
        # content blocks (TextContent / ImageContent / EmbeddedResource). Most
        # downstream consumers expect a plain string; flatten text blocks.
        text_parts: list[str] = []
        for block in getattr(result, "content", None) or []:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                text_parts.append(block_text)
        return "\n".join(text_parts)


class MCPToolManager:
    """Manages MCP client connections and discovered tools.

    Uses ``contextlib.AsyncExitStack`` to keep transport context managers
    open across the manager's lifetime; ``shutdown()`` unwinds them.
    """

    _exit_stack: Optional[contextlib.AsyncExitStack] = None
    _sessions: Dict[str, Any] = {}
    _tools: List[MCPTool] = []
    _initialized: bool = False
    _configs: List[MCPServerConfig] = []

    @classmethod
    async def initialize(cls, configs: List[MCPServerConfig]) -> None:
        """Connect to each enabled MCP server and load its tools."""
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
            from mcp import ClientSession  # type: ignore[import-not-found]
            from mcp.client.stdio import StdioServerParameters, stdio_client  # type: ignore[import-not-found]
            from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]
        except ImportError as exc:
            logger.warning(
                "mcp SDK not installed — MCP Client unavailable (%s). "
                "Install with: pip install mcp~=1.27.0",
                exc,
            )
            cls._initialized = True
            return

        try:
            from mcp.client.sse import sse_client  # type: ignore[import-not-found]
        except ImportError:
            sse_client = None  # SSE transport optional
            logger.debug("mcp SDK SSE transport unavailable — http/stdio still work")

        exit_stack = contextlib.AsyncExitStack()
        await exit_stack.__aenter__()

        sessions: Dict[str, Any] = {}
        tools: List[MCPTool] = []

        for config in enabled_configs:
            try:
                if config.transport == "stdio":
                    if not config.command:
                        logger.warning(
                            "MCP server '%s' missing command — skipped",
                            config.name,
                        )
                        continue
                    params = StdioServerParameters(
                        command=config.command,
                        args=config.args or [],
                    )
                    transport = await exit_stack.enter_async_context(
                        stdio_client(params)
                    )
                    read, write = transport[0], transport[1]
                elif config.transport == "http":
                    if not config.url:
                        logger.warning(
                            "MCP server '%s' missing URL — skipped",
                            config.name,
                        )
                        continue
                    transport = await exit_stack.enter_async_context(
                        streamablehttp_client(
                            config.url,
                            headers=config.headers or {},
                        )
                    )
                    read, write = transport[0], transport[1]
                elif config.transport == "sse":
                    if not config.url:
                        logger.warning(
                            "MCP server '%s' missing URL — skipped",
                            config.name,
                        )
                        continue
                    if sse_client is None:
                        logger.warning(
                            "MCP server '%s' uses SSE transport but mcp SDK has no sse_client — skipped",
                            config.name,
                        )
                        continue
                    transport = await exit_stack.enter_async_context(
                        sse_client(
                            config.url,
                            headers=config.headers or {},
                        )
                    )
                    read, write = transport[0], transport[1]
                else:
                    logger.warning(
                        "MCP server '%s' unknown transport '%s' — skipped",
                        config.name,
                        config.transport,
                    )
                    continue

                session = await exit_stack.enter_async_context(
                    ClientSession(read, write)
                )
                await session.initialize()
                sessions[config.name] = session

                listing = await session.list_tools()
                for tool_def in getattr(listing, "tools", None) or []:
                    tools.append(
                        MCPTool(
                            name=getattr(tool_def, "name", ""),
                            description=getattr(tool_def, "description", "") or "",
                            parameters=(
                                getattr(tool_def, "inputSchema", None)
                                or getattr(tool_def, "input_schema", None)
                                or {}
                            ),
                            session=session,
                            server_name=config.name,
                        )
                    )

            except Exception as exc:
                logger.warning(
                    "MCP server '%s' connection failed: %s",
                    config.name,
                    exc,
                )

        if not sessions:
            await exit_stack.aclose()
            logger.info("No MCP server connected — initialization complete with 0 tools")
            cls._initialized = True
            return

        cls._exit_stack = exit_stack
        cls._sessions = sessions
        cls._tools = tools
        cls._configs = enabled_configs
        cls._initialized = True
        logger.info(
            "[OK] MCP Client initialized: %d tool(s) across %d server(s)",
            len(tools),
            len(sessions),
        )

    @classmethod
    def get_tools(cls) -> List[MCPTool]:
        """Get all loaded MCP tools."""
        return cls._tools

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the MCP client has been initialized."""
        return cls._initialized

    @classmethod
    async def shutdown(cls) -> None:
        """Close MCP client connections."""
        if cls._exit_stack is not None:
            try:
                await cls._exit_stack.aclose()
            except Exception as exc:
                logger.warning("MCP Client shutdown error: %s", exc)
            finally:
                cls._exit_stack = None
        cls._sessions = {}
        cls._tools = []
        cls._initialized = False
        logger.info("MCP Client shut down")

    @classmethod
    def reset(cls) -> None:
        """Reset all state. Used in tests."""
        cls._exit_stack = None
        cls._sessions = {}
        cls._tools = []
        cls._initialized = False
        cls._configs = []

    @classmethod
    def register_discovered_tools(cls) -> int:
        """Bridge discovered external MCP tools into ``ToolRegistry``."""
        if not cls._initialized or not cls._tools:
            return 0

        try:
            from app.core.config import get_settings

            settings = get_settings()
            if not getattr(settings, "mcp_auto_register_external", False) is True:
                return 0
        except ImportError:
            return 0

        try:
            from app.engine.tools.registry import get_tool_registry

            registry = get_tool_registry()
        except ImportError:
            logger.warning(
                "ToolRegistry not available — cannot register MCP tools"
            )
            return 0

        count = 0
        for tool in cls._tools:
            try:
                name = getattr(tool, "name", None)
                if not name:
                    continue

                category, access, roles = infer_external_tool_registration(name)

                if registry.get_info(name) is not None:
                    logger.debug(
                        "MCP tool '%s' already in registry — skipped",
                        name,
                    )
                    continue

                registry.register(
                    tool=tool,
                    category=category,
                    access=access,
                    description=getattr(tool, "description", "") or "",
                    roles=roles,
                )
                count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to register MCP tool '%s': %s",
                    getattr(tool, "name", "?"),
                    exc,
                )

        if count:
            logger.info("[OK] Registered %d MCP tools into ToolRegistry", count)
        return count

    @classmethod
    def parse_configs(cls, json_str: str) -> List[MCPServerConfig]:
        """Parse MCP server configs from JSON string (settings.mcp_server_configs)."""
        try:
            raw = json.loads(json_str)
            if not isinstance(raw, list):
                return []
            configs = []
            allowed_fields = {f.name for f in fields(MCPServerConfig)}
            for item in raw:
                if isinstance(item, dict):
                    filtered = {
                        key: value
                        for key, value in item.items()
                        if key in allowed_fields
                    }
                    configs.append(MCPServerConfig(**filtered))
            return configs
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse MCP server configs: %s", exc)
            return []

    @classmethod
    def resolve_configs(cls, settings) -> List[MCPServerConfig]:
        """Build the effective MCP config set from settings and runtime helpers."""
        configs = cls.parse_configs(settings.mcp_server_configs)

        try:
            from app.engine.context.browser_agent import get_browser_mcp_config

            browser_config = get_browser_mcp_config(settings)
            if browser_config is not None:
                configs = cls.merge_configs(
                    configs,
                    [MCPServerConfig(**browser_config)],
                )
        except Exception as exc:
            logger.warning("Failed to resolve browser MCP config: %s", exc)

        return configs

    @staticmethod
    def merge_configs(
        primary: List[MCPServerConfig],
        secondary: List[MCPServerConfig],
    ) -> List[MCPServerConfig]:
        """Merge two config lists, preserving the first occurrence by name."""
        merged: List[MCPServerConfig] = []
        seen: set[str] = set()

        for config in [*primary, *secondary]:
            if config.name in seen:
                logger.debug(
                    "Skipping duplicate MCP server config '%s'",
                    config.name,
                )
                continue
            merged.append(config)
            seen.add(config.name)

        return merged
