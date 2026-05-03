"""FastAPI app factory helpers for app.main."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler


logger = logging.getLogger(__name__)


def build_cors_kwargs() -> dict:
    """Build CORSMiddleware kwargs from settings."""

    cors_origins = [
        "http://localhost:4200",
        "http://localhost:4300",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:1420",
        "http://127.0.0.1:4200",
        "http://127.0.0.1:4300",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:1420",
        "https://tauri.localhost",
        "tauri://localhost",
    ]
    if settings.cors_origins and settings.cors_origins != ["*"]:
        cors_origins.extend(settings.cors_origins)

    cors_kwargs: dict = {
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-User-ID",
            "X-Role",
            "X-Session-ID",
            "X-Organization-ID",
            "X-Request-ID",
        ],
        "expose_headers": ["X-Request-ID", "Retry-After"],
    }
    if settings.cors_origin_regex:
        cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex
        cors_kwargs["allow_origins"] = cors_origins
    else:
        cors_kwargs["allow_origins"] = cors_origins
    return cors_kwargs


def configure_cors(app: FastAPI) -> None:
    app.add_middleware(CORSMiddleware, **build_cors_kwargs())


def configure_session_middleware(app: FastAPI, logger_: logging.Logger) -> None:
    if not settings.enable_google_oauth:
        return

    from starlette.middleware.sessions import SessionMiddleware

    if len(settings.session_secret_key) < 32:
        logger_.warning(
            "SECURITY: SessionMiddleware secret_key is only %d chars — "
            "recommend at least 32 chars for secure OAuth CSRF state",
            len(settings.session_secret_key),
        )
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)


def configure_core_middleware(app: FastAPI) -> None:
    from app.core.middleware import EmbedCSPMiddleware, OrgContextMiddleware, RequestIDMiddleware

    app.add_middleware(EmbedCSPMiddleware)
    app.add_middleware(OrgContextMiddleware)
    app.add_middleware(RequestIDMiddleware)


def configure_exception_handlers(
    app: FastAPI,
    *,
    request_validation_error,
    validation_exception_handler,
    wiii_exception_handler,
    general_exception_handler,
) -> None:
    from app.core.exceptions import WiiiException
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_exception_handler(request_validation_error, validation_exception_handler)
    app.add_exception_handler(WiiiException, wiii_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)


def include_api_router(app: FastAPI) -> None:
    from app.api.v1 import router as api_v1_router

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


def include_edge_endpoints(app: FastAPI) -> None:
    """Mount OpenAI/Anthropic-compat edge endpoints at root ``/v1``.

    Phase 10d of the runtime migration epic (#207). Gated by
    ``enable_native_runtime`` so the routes only register when the lane-
    first runtime is opt-in for that environment.
    """
    if not getattr(settings, "enable_native_runtime", False):
        return
    from app.api.edge_endpoints import router as edge_router

    app.include_router(edge_router)


def register_agent_card_route(app: FastAPI, logger_: logging.Logger) -> None:
    if not settings.enable_soul_bridge:
        return

    @app.get("/.well-known/agent.json", tags=["SoulBridge"])
    async def agent_card_endpoint():
        """Serve Wiii's agent card for soul discovery (A2A-inspired)."""
        try:
            from app.engine.soul_bridge.agent_card import build_agent_card

            soul_config = None
            emotional_state = None
            try:
                from app.engine.living_agent.soul_loader import get_soul

                soul_config = get_soul()
            except Exception:
                pass
            try:
                from app.engine.living_agent.emotion_engine import get_emotion_engine

                emotional_state = get_emotion_engine().to_dict()
            except Exception:
                pass
            base_url = f"http://localhost:{settings.port}"
            card = build_agent_card(soul_config, emotional_state, base_url)
            return card.to_dict()
        except Exception as exc:
            logger_.warning("Agent card generation failed: %s", exc)
            return {"error": "Agent card unavailable"}


def mount_mcp_server(app: FastAPI, logger_: logging.Logger) -> None:
    if not settings.enable_mcp_server:
        return
    try:
        from app.mcp.server import setup_mcp_server

        setup_mcp_server(app)
    except Exception as exc:
        logger_.warning("MCP Server mount failed: %s", exc)


def _resolve_static_dir(candidates: list[Path], marker: str) -> Path | None:
    return next((path for path in candidates if path.exists() and (path / marker).exists()), None)


def mount_frontend_assets(app: FastAPI, logger_: logging.Logger) -> None:
    try:
        from starlette.staticfiles import StaticFiles

        embed_candidates = [
            Path("/app-embed"),
            Path(__file__).parent.parent.parent / "wiii-desktop" / "dist-embed",
        ]
        embed_dir = _resolve_static_dir(embed_candidates, "embed.html")
        if embed_dir:
            app.mount("/embed", StaticFiles(directory=str(embed_dir), html=True), name="embed")
            logger_.info("[OK] Embed static files mounted at /embed from %s", embed_dir)
        else:
            logger_.debug(
                "Embed static files not found (build with: cd wiii-desktop && npm run build:embed)"
            )
    except Exception as exc:
        logger_.warning("Embed static mount failed: %s", exc)

    try:
        from starlette.staticfiles import StaticFiles

        web_candidates = [
            Path("/app-web"),
            Path(__file__).parent.parent.parent / "wiii-desktop" / "dist-web",
        ]
        web_dir = _resolve_static_dir(web_candidates, "index.html")
        if web_dir:
            app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web-spa")
            logger_.info("[OK] Web SPA mounted at / from %s", web_dir)
        else:
            logger_.debug("Web SPA not found (build with: cd wiii-desktop && npm run build:web)")
    except Exception as exc:
        logger_.warning("Web SPA mount failed: %s", exc)
