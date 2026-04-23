"""
MCP Server — Exposes Wiii tools via Model Context Protocol.

Sprint 56: Mounts on existing FastAPI app at /mcp endpoint.
Uses fastapi-mcp to auto-expose REST endpoints + custom tool wrappers.

Feature-gated: enable_mcp_server=False by default.
Transport: Streamable HTTP (MCP spec 2025-03-26).
"""

import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)

# Target paths to expose as MCP tools. Routes don't have explicit operation_id,
# so we match by (path, method) instead.
_MCP_TARGET_PATHS: dict[str, set[str]] = {
    "/api/v1/chat":              {"POST"},
    "/api/v1/chat/stream/v3":    {"POST"},
    "/api/v1/insights/{user_id}":{"GET"},
    "/api/v1/memories/{user_id}":{"GET"},
    "/api/v1/knowledge/stats":   {"GET"},
}


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
        from fastapi_mcp import FastApiMCP  # noqa: F401
    except ImportError:
        logger.warning(
            "fastapi-mcp not installed — MCP Server unavailable. "
            "Install with: pip install fastapi-mcp>=0.3.0"
        )
        return None

    # fastapi-mcp v0.4.0 calls get_openapi(routes=ALL_ROUTES) in setup_server().
    # Routes with complex Annotated dependency types (RequireAuth) can trigger
    # Pydantic TypeAdapter errors. Workaround: pass only target routes via sub-app.
    try:
        mcp = _mount_mcp_safe(app)
        if mcp:
            return mcp
    except Exception as e:
        logger.warning("MCP Server mount failed: %s", e)

    return None


def _collect_target_routes(app):
    """Collect routes matching our target paths and methods."""
    safe_routes = []
    seen_paths: Set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path and methods and path in _MCP_TARGET_PATHS:
            route_methods = {m.upper() for m in methods}
            target_methods = _MCP_TARGET_PATHS[path]
            if route_methods & target_methods:
                safe_routes.append(route)
                seen_paths.add(path)
        elif hasattr(route, "routes"):  # APIRouter
            for sub_route in route.routes:
                sub_path = getattr(sub_route, "path", None)
                sub_methods = getattr(sub_route, "methods", None)
                if sub_path and sub_methods and sub_path in _MCP_TARGET_PATHS:
                    route_methods = {m.upper() for m in sub_methods}
                    target_methods = _MCP_TARGET_PATHS[sub_path]
                    if route_methods & target_methods:
                        safe_routes.append(sub_route)
                        seen_paths.add(sub_path)
    return safe_routes, seen_paths


def _mount_mcp_safe(app) -> Optional[object]:
    """Mount MCP using a filtered sub-app to avoid TypeAdapter errors.

    fastapi-mcp v0.4.0 calls get_openapi(routes=...) scanning ALL routes during
    __init__. Some routes have complex Annotated[ForwardRef('RequireAuth'), ...]
    types that cause Pydantic TypeAdapter failures. By creating a sub-app with
    only our target routes, get_openapi() only processes those 5 routes, avoiding
    the problematic ones.
    """
    from fastapi_mcp import FastApiMCP
    from fastapi import FastAPI

    safe_routes, seen_paths = _collect_target_routes(app)

    if not safe_routes:
        logger.warning("MCP Server: no matching routes found for MCP exposure")
        return None

    missing = set(_MCP_TARGET_PATHS.keys()) - seen_paths
    if missing:
        logger.debug("MCP Server: target paths not found: %s", missing)

    # Minimal sub-app — only target routes, so get_openapi() skips problematic ones.
    sub_app = FastAPI(title="Wiii MCP", version="1.0.0")
    for route in safe_routes:
        sub_app.routes.append(route)

    mcp = FastApiMCP(
        sub_app,
        name="Wiii MCP Server",
        description=(
            "Multi-Domain Agentic RAG Platform by The Wiii Lab. "
            "Provides knowledge search, memory management, and teaching tools."
        ),
        headers=[
            "authorization",
            "X-API-Key",
            "X-User-ID",
            "X-Session-ID",
            "X-Role",
            "X-Organization-ID",
        ],
    )
    # mount_http(router=app) registers the /mcp endpoint on the MAIN app,
    # not the sub-app. FastApiMCP uses the sub-app for route scanning but
    # we need the endpoint accessible on the main app.
    mcp.mount_http(router=app)
    logger.info(
        "[OK] MCP Server mounted at /mcp (Streamable HTTP, %d/%d operations)",
        len(safe_routes), len(_MCP_TARGET_PATHS),
    )
    return mcp
