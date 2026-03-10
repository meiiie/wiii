"""Admin-only browser tools backed by the privileged sandbox."""

from __future__ import annotations

from langchain_core.tools import tool

from app.engine.tools.runtime_context import (
    emit_tool_bus_event,
    get_current_tool_runtime_context,
)
from app.sandbox.browser_service import (
    BrowserAutomationRequest,
    get_browser_sandbox_service,
)


@tool
def tool_browser_snapshot_url(url: str) -> str:
    """
    Visit a public URL in the browser sandbox and capture a screenshot summary.

    Args:
        url: Public http/https URL to visit.

    Returns:
        Human-readable summary of the browser session.
    """
    service = get_browser_sandbox_service()
    runtime = get_current_tool_runtime_context()
    request_metadata = dict(runtime.metadata or {}) if runtime else {}
    if runtime and runtime.tool_call_id:
        request_metadata.setdefault("tool_call_id", runtime.tool_call_id)
    result = service.execute_sync(
        BrowserAutomationRequest(
            url=url,
            tool_name="tool_browser_snapshot_url",
            source=runtime.source if runtime else "tool_registry",
            capture_screenshot=True,
            node=runtime.node if runtime else None,
            organization_id=runtime.organization_id if runtime else None,
            user_id=runtime.user_id if runtime else None,
            session_id=runtime.session_id if runtime else None,
            request_id=runtime.request_id if runtime else None,
            metadata=request_metadata,
        )
    )
    emit_tool_bus_event(service.build_screenshot_bus_event(result, node=runtime.node if runtime else None))
    emit_tool_bus_event(
        service.build_artifact_bus_event(
            result,
            node=runtime.node if runtime else None,
        )
    )
    return service.build_tool_summary(result)


def get_browser_sandbox_tools() -> list:
    """Return all internal browser sandbox tools."""
    return [tool_browser_snapshot_url]
