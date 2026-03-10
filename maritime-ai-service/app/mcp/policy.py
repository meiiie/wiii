"""Policy helpers for MCP tool exposure and external MCP registrations."""

from __future__ import annotations

from typing import Any, Optional

from app.engine.context.browser_agent import EXPECTED_BROWSER_TOOLS
from app.engine.tools.registry import ToolAccess, ToolCategory
from app.sandbox.catalog import SandboxWorkloadProfile, get_sandbox_workload_catalog


def is_browser_tool_name(name: str) -> bool:
    """Detect Playwright/browser-style MCP tools."""
    return bool(name) and (
        name in EXPECTED_BROWSER_TOOLS or name.startswith("browser_")
    )


def get_sandbox_tool_profile(name: str) -> Optional[SandboxWorkloadProfile]:
    """Resolve manifest-backed sandbox profiles bound to a tool name."""
    if not name:
        return None
    try:
        return get_sandbox_workload_catalog().find_by_tool_name(name)
    except Exception:
        return None


def infer_external_tool_registration(name: str) -> tuple[ToolCategory, ToolAccess, list[str]]:
    """
    Classify external MCP tools before bridging them into ToolRegistry.

    Browser automation is privileged and should not be treated as a generic
    read-only tool when discovered through an external MCP server.
    """
    if is_browser_tool_name(name):
        return ToolCategory.MCP, ToolAccess.WRITE, ["admin"]

    return ToolCategory.MCP, ToolAccess.READ, ["student", "teacher", "admin"]


def build_mcp_annotations(
    *,
    name: str,
    category: str,
    access: str,
    source: str,
) -> dict[str, Any]:
    """Build standard MCP tool annotations from Wiii policy metadata."""
    read_only = access != ToolAccess.WRITE.value
    destructive = access == ToolAccess.WRITE.value
    open_world = (
        is_browser_tool_name(name)
        or source == "mcp_external"
        or category in {ToolCategory.MCP.value, ToolCategory.PRODUCT_SEARCH.value}
        or name in {"tool_web_search", "tool_search_news", "tool_search_legal"}
    )
    return {
        "readOnlyHint": read_only,
        "destructiveHint": destructive,
        "openWorldHint": open_world,
    }


def build_wiii_tool_meta(
    *,
    name: str,
    category: str,
    access: str,
    source: str,
    roles: list[str],
) -> dict[str, Any]:
    """Attach Wiii-specific policy metadata alongside MCP-standard annotations."""
    risk_level = "low"
    approval_required = False
    approval_scope = ""
    sandbox_workload = ""
    profile = get_sandbox_tool_profile(name)

    if is_browser_tool_name(name):
        risk_level = "high"
        approval_required = True
        approval_scope = "browser_automation"
        sandbox_workload = "browser"
    elif profile is not None:
        risk_level = "high"
        approval_required = True
        approval_scope = profile.approval_scope
        sandbox_workload = profile.workload_kind.value
    elif category == ToolCategory.EXECUTION.value:
        risk_level = "high"
        approval_required = True
        approval_scope = "privileged_execution"
        sandbox_workload = "python"
    elif category == ToolCategory.FILESYSTEM.value:
        risk_level = "high"
        approval_required = True
        approval_scope = "filesystem_write"
    elif category == ToolCategory.SKILL_MANAGEMENT.value:
        risk_level = "high"
        approval_required = True
        approval_scope = "self_modification"
    elif access == ToolAccess.WRITE.value:
        risk_level = "medium"
        approval_required = True
        approval_scope = "mutation"
    elif source == "mcp_external":
        risk_level = "medium"
    elif category == ToolCategory.MCP.value:
        risk_level = "medium"

    meta = {
        "wiii": {
            "riskLevel": risk_level,
            "approvalRequired": approval_required,
            "approvalScope": approval_scope,
            "executionBackend": infer_execution_backend(
                name=name,
                category=category,
            ),
            "sandboxWorkload": sandbox_workload,
            "source": source,
            "roles": roles,
        }
    }
    return meta


def infer_execution_backend(*, name: str, category: str) -> str:
    """Resolve the current execution backend for policy/audit metadata."""
    try:
        from app.core.config import get_settings

        settings = get_settings()
    except Exception:
        settings = None
    profile = get_sandbox_tool_profile(name)

    if is_browser_tool_name(name):
        if (
            settings
            and getattr(settings, "enable_privileged_sandbox", False)
            and getattr(settings, "sandbox_provider", "disabled") == "opensandbox"
            and getattr(settings, "sandbox_allow_browser_workloads", False)
        ):
            return "opensandbox"
        return "playwright_mcp"

    if profile is not None:
        if (
            settings
            and getattr(settings, "enable_privileged_sandbox", False)
            and getattr(settings, "sandbox_provider", "disabled") == "opensandbox"
        ):
            return "opensandbox"
        if profile.execution_backend:
            return profile.execution_backend

    if category == ToolCategory.EXECUTION.value:
        if (
            settings
            and getattr(settings, "enable_privileged_sandbox", False)
            and getattr(settings, "sandbox_provider", "disabled") == "opensandbox"
        ):
            return "opensandbox"
        return "local_subprocess"

    if category == ToolCategory.FILESYSTEM.value:
        return "host_filesystem"

    return ""


def parse_access_value(access: Any) -> str:
    """Normalize ToolAccess enum/string values into the MCP-facing string form."""
    if isinstance(access, ToolAccess):
        return access.value
    if isinstance(access, str):
        return access
    return ToolAccess.READ.value


def maybe_build_policy_bundle(
    *,
    name: str,
    category: str,
    access: Optional[Any],
    source: str,
    roles: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convenience bundle for MCPToolServer export."""
    access_value = parse_access_value(access)
    return (
        build_mcp_annotations(
            name=name,
            category=category,
            access=access_value,
            source=source,
        ),
        build_wiii_tool_meta(
            name=name,
            category=category,
            access=access_value,
            source=source,
            roles=roles,
        ),
    )
