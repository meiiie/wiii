"""
Sprint 193: MCP Tool Server — Expose individual tools via MCP.

Reads tools from ToolRegistry and UnifiedSkillIndex, converts each
to an MCP tool definition, and provides them to external MCP clients.

Unlike server.py (Sprint 56) which exposes REST endpoints,
this module exposes individual tool definitions for fine-grained
tool discovery and invocation.

Feature-gated: enable_mcp_tool_server=False (default)

Pattern:
  - Singleton: get_mcp_tool_server()
  - Thread-safe via threading.Lock
  - Lazy loading: tools loaded on first access
  - Backward compatible: disabled by default
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Module-level singleton
_server_instance: Optional["MCPToolServer"] = None
_server_lock = threading.Lock()


@dataclass
class MCPToolDefinition:
    """An MCP-compatible tool definition."""
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {},
    })
    source: str = ""  # "tool_registry", "domain_plugin", "living_agent", "mcp_external"
    category: str = ""
    roles: List[str] = field(default_factory=lambda: ["student", "teacher", "admin"])


def get_mcp_tool_server() -> "MCPToolServer":
    """Get or create the singleton MCPToolServer."""
    global _server_instance
    if _server_instance is None:
        with _server_lock:
            if _server_instance is None:
                _server_instance = MCPToolServer()
    return _server_instance


class MCPToolServer:
    """
    Exposes Wiii tools as MCP tool definitions.

    Reads from:
    1. ToolRegistry — LangChain tools with categories and descriptions
    2. UnifiedSkillIndex — cross-system skill discovery (when enabled)

    Output format follows MCP tool schema:
    {
        "name": "tool_search_shopee",
        "description": "Search products on Shopee Vietnam",
        "inputSchema": {"type": "object", "properties": {...}}
    }

    Usage:
        server = get_mcp_tool_server()
        tools = server.list_tools()
        # tools = [MCPToolDefinition(...), ...]
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._cache: List[MCPToolDefinition] = []
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_tools(
        self,
        user_role: str = "student",
        category: Optional[str] = None,
        include_external: bool = True,
    ) -> List[MCPToolDefinition]:
        """
        List all available tools as MCP definitions.

        Args:
            user_role: Filter by role access
            category: Filter by tool category (optional)
            include_external: Include MCP external tools (default True)

        Returns:
            List of MCPToolDefinition objects.
        """
        if not self._loaded:
            self.refresh()

        result = []
        for tool_def in self._cache:
            # Role filter
            if user_role and tool_def.roles and user_role not in tool_def.roles:
                continue

            # Category filter
            if category and tool_def.category != category:
                continue

            # External filter
            if not include_external and tool_def.source == "mcp_external":
                continue

            result.append(tool_def)

        return result

    def get_tool(self, name: str) -> Optional[MCPToolDefinition]:
        """Get a specific tool definition by name."""
        if not self._loaded:
            self.refresh()

        for tool_def in self._cache:
            if tool_def.name == name:
                return tool_def
        return None

    def refresh(self) -> int:
        """
        Reload tools from all sources.

        Returns:
            Number of tools loaded.
        """
        with self._lock:
            self._cache.clear()

            # Source 1: ToolRegistry
            count_registry = self._load_from_tool_registry()

            # Source 2: UnifiedSkillIndex (if enabled)
            count_index = self._load_from_unified_index()

            self._loaded = True
            total = len(self._cache)
            logger.info(
                "MCPToolServer refreshed: %d tools (registry=%d, index=%d)",
                total, count_registry, count_index,
            )
            return total

    def to_mcp_format(self) -> List[Dict[str, Any]]:
        """
        Export all tools in MCP JSON format.

        Returns:
            List of MCP tool definition dicts ready for JSON serialization.
        """
        if not self._loaded:
            self.refresh()

        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self._cache
        ]

    def count(self) -> int:
        """Get number of loaded tools."""
        if not self._loaded:
            self.refresh()
        return len(self._cache)

    def summary(self) -> Dict[str, Any]:
        """Get summary of loaded tools by source and category."""
        if not self._loaded:
            self.refresh()

        by_source: Dict[str, int] = {}
        by_category: Dict[str, int] = {}

        for t in self._cache:
            by_source[t.source] = by_source.get(t.source, 0) + 1
            if t.category:
                by_category[t.category] = by_category.get(t.category, 0) + 1

        return {
            "total": len(self._cache),
            "by_source": by_source,
            "by_category": by_category,
        }

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._cache.clear()
        self._loaded = False

    # ------------------------------------------------------------------
    # Source Loaders
    # ------------------------------------------------------------------

    def _load_from_tool_registry(self) -> int:
        """Load tools from ToolRegistry."""
        try:
            from app.engine.tools.registry import get_tool_registry
            registry = get_tool_registry()
            if not registry._initialized:
                return 0
        except ImportError:
            return 0

        count = 0
        existing_names = {t.name for t in self._cache}

        for name, info in registry._tools.items():
            if name in existing_names:
                continue

            # Extract input schema from LangChain tool if available
            input_schema = self._extract_tool_schema(info.tool)

            self._cache.append(MCPToolDefinition(
                name=name,
                description=info.description,
                input_schema=input_schema,
                source="tool_registry",
                category=info.category.value if info.category else "",
                roles=info.roles or ["student", "teacher", "admin"],
            ))
            count += 1

        return count

    def _load_from_unified_index(self) -> int:
        """Load additional tools from UnifiedSkillIndex (if enabled)."""
        try:
            from app.core.config import get_settings
            settings = get_settings()
            if not getattr(settings, "enable_unified_skill_index", False) is True:
                return 0
        except ImportError:
            return 0

        try:
            from app.engine.skills.unified_index import get_unified_skill_index
            index = get_unified_skill_index()
        except ImportError:
            return 0

        count = 0
        existing_names = {t.name for t in self._cache}

        for manifest in index.get_all():
            # Skip tools already loaded from registry (avoid duplicates)
            tool_name = manifest.tool_name or manifest.name
            if tool_name in existing_names:
                continue

            # Only include non-TOOL types (TOOL already loaded from registry)
            if manifest.skill_type.value == "tool":
                continue

            self._cache.append(MCPToolDefinition(
                name=manifest.id,  # Composite ID: "domain:maritime:colregs"
                description=manifest.description,
                input_schema={"type": "object", "properties": {}},
                source=manifest.skill_type.value,
                category=manifest.domain_id or "",
                roles=["student", "teacher", "admin"],
            ))
            existing_names.add(manifest.id)
            count += 1

        return count

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tool_schema(tool) -> Dict[str, Any]:
        """
        Extract JSON schema from a LangChain tool.

        LangChain StructuredTool stores schema in .args_schema (Pydantic model).
        Falls back to empty schema if not available.
        """
        default = {"type": "object", "properties": {}}

        try:
            # LangChain StructuredTool pattern
            args_schema = getattr(tool, "args_schema", None)
            if args_schema is not None:
                # Pydantic model → JSON schema
                if hasattr(args_schema, "model_json_schema"):
                    schema = args_schema.model_json_schema()
                elif hasattr(args_schema, "schema"):
                    schema = args_schema.schema()
                else:
                    return default

                # Ensure 'properties' key exists (MCP/OpenAI requirement)
                if "properties" not in schema:
                    schema["properties"] = {}
                if "type" not in schema:
                    schema["type"] = "object"
                return schema
        except Exception:
            pass

        return default
