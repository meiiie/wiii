"""
Wiii - FastAPI Application Entry Point
by The Wiii Lab

Clean Architecture + Agentic RAG + Long-term Memory + Domain Plugins
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.main_app_factory_support import (
    configure_core_middleware,
    configure_cors,
    configure_exception_handlers,
    configure_session_middleware,
    include_api_router,
    mount_frontend_assets,
    mount_mcp_server,
    register_agent_card_route,
)
from app.main_runtime_support import shutdown_application, startup_application
from app.models.schemas import ErrorResponse, ErrorDetail

# Configure structured logging (JSON in production, console in dev)
setup_logging(
    json_output=settings.environment == "production",
    log_level=settings.log_level,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    
    Production Readiness Spec:
    - Startup: Validate connections, log warnings if unavailable (don't crash)
    - Shutdown: Close Neo4j driver explicitly
    
    Requirements: 2.1, 2.2, 3.1, 3.2, 3.3
    """
    resources = await startup_application(logger)
    print(f"[START] {settings.app_name} started successfully", flush=True)
    try:
        yield
    finally:
        await shutdown_application(resources, logger)


def create_application() -> FastAPI:
    """
    Application factory pattern.
    Creates and configures the FastAPI application.
    """
    app = FastAPI(
        title=settings.app_name,
        description="Wiii by The Wiii Lab - Multi-Domain Agentic RAG Platform with Long-term Memory",
        version=settings.app_version,
        docs_url="/docs",  # Always enable for LMS team integration
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    configure_cors(app)
    configure_session_middleware(app, logger)
    configure_core_middleware(app)
    configure_exception_handlers(
        app,
        request_validation_error=RequestValidationError,
        validation_exception_handler=validation_exception_handler,
        wiii_exception_handler=wiii_exception_handler,
        general_exception_handler=general_exception_handler,
    )
    include_api_router(app)
    register_agent_card_route(app, logger)
    mount_mcp_server(app, logger)
    mount_frontend_assets(app, logger)

    return app


# =============================================================================
# Exception Handlers
# =============================================================================

async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.
    Returns HTTP 400 with detailed error information.
    Requirements: 1.2
    """
    errors = []
    for error in exc.errors():
        errors.append(
            ErrorDetail(
                field=".".join(str(loc) for loc in error["loc"]),
                message=error["msg"],
                code=error["type"],
            )
        )
    
    response = ErrorResponse(
        error="validation_error",
        message="Request validation failed",
        details=errors,
        request_id=getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID"),
    )
    
    logger.warning("Validation error: %s", response.model_dump_json())
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(mode="json"),
    )


async def wiii_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle typed Wiii platform exceptions with structured error responses."""
    from app.core.exceptions import WiiiException
    wiii_exc = exc if isinstance(exc, WiiiException) else None
    if wiii_exc is None:
        return await general_exception_handler(request, exc)

    logger.warning("[%s] %s", wiii_exc.error_code, wiii_exc.message)

    response = ErrorResponse(
        error=wiii_exc.error_code,
        message=wiii_exc.message,
        request_id=getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID"),
    )
    return JSONResponse(
        status_code=wiii_exc.http_status,
        content=response.model_dump(mode="json"),
    )


async def general_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Handle unexpected exceptions.
    Returns HTTP 500 with error details while maintaining service availability.
    Requirements: 1.4
    """
    logger.exception("Unexpected error: %s", exc)
    
    response = ErrorResponse(
        error="internal_error",
        message="An unexpected error occurred" if not settings.debug else str(exc),
        request_id=getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID"),
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(mode="json"),
    )


# Create application instance
app = create_application()


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - service information"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "docs": f"{settings.api_v1_prefix}/docs" if settings.debug else "disabled",
    }


@app.get("/health", tags=["Health"])
async def health_check_simple():
    """
    Simple health check endpoint for LMS/DevOps.
    
    Spec: CHỈ THỊ KỸ THUẬT SỐ 03
    URL: GET /health
    Response: {"status": "ok", "database": "connected"}
    """
    # Check database connection
    db_status = "connected"
    try:
        from app.repositories.chat_history_repository import get_chat_history_repository
        chat_history = get_chat_history_repository()
        if not chat_history.is_available():
            db_status = "disconnected"
    except Exception as e:
        logger.debug("DB health check failed: %s", e)
        db_status = "disconnected"
    
    return {
        "status": "ok",
        "database": db_status
    }
