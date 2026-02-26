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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
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
    # Startup
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("Environment: %s", settings.environment)
    logger.info("Debug mode: %s", settings.debug)

    # Initialize OpenTelemetry tracing (SOTA 2026)
    from app.core.observability import init_telemetry
    init_telemetry(service_name=settings.app_name.lower())

    # LangSmith tracing (Sprint 144b: LangChain/LangGraph observability)
    # Must be called BEFORE LLM Pool init so env vars are set when providers load
    if settings.enable_langsmith:
        from app.core.langsmith import configure_langsmith
        configure_langsmith(settings)

    # Validate database connections (warn only, don't crash)
    neo4j_repo = None
    try:
        from app.repositories.chat_history_repository import get_chat_history_repository
        chat_repo = get_chat_history_repository()
        if chat_repo.is_available():
            logger.info("[OK] PostgreSQL connection: Available")
        else:
            logger.warning("[WARN] PostgreSQL connection: Unavailable (service will continue)")
    except Exception as e:
        logger.warning("[WARN] PostgreSQL validation failed: %s (service will continue)", e)
    
    try:
        from app.repositories.neo4j_knowledge_repository import Neo4jKnowledgeRepository
        neo4j_repo = Neo4jKnowledgeRepository()
        if neo4j_repo.is_available():
            logger.info("[OK] Neo4j connection: Available")
        else:
            logger.warning("[WARN] Neo4j connection: Unavailable (service will continue)")
    except Exception as e:
        logger.warning("[WARN] Neo4j validation failed: %s (service will continue)", e)
    
    try:
        from app.repositories.semantic_memory_repository import get_semantic_memory_repository
        semantic_repo = get_semantic_memory_repository()
        if semantic_repo.is_available():
            logger.info("[OK] pgvector connection: Available")
        else:
            logger.warning("[WARN] pgvector connection: Unavailable (service will continue)")
    except Exception as e:
        logger.warning("[WARN] pgvector validation failed: %s (service will continue)", e)
    
    # Validate YAML persona files (CHỈ THỊ 16 - Humanization)
    try:
        from app.prompts.prompt_loader import get_prompt_loader
        get_prompt_loader()
        # This will log which files were found/loaded
        logger.info("[OK] PromptLoader initialized (persona YAML files checked)")
    except Exception as e:
        logger.warning("[WARN] PromptLoader initialization failed: %s (using defaults)", e)
    
    # =========================================================================
    # DOMAIN PLUGIN DISCOVERY (Universal Platform - Feb 2026)
    # =========================================================================
    try:
        from pathlib import Path
        from app.domains.loader import DomainLoader
        from app.domains.registry import get_domain_registry

        domains_dir = Path(__file__).parent / "domains"
        loader = DomainLoader(domains_dir)
        registry = get_domain_registry()

        discovered = loader.discover()
        for domain in discovered:
            domain_cfg = domain.get_config()
            if domain_cfg.id in settings.active_domains:
                registry.register(domain)
                logger.info("Domain plugin loaded: %s (%s)", domain_cfg.id, domain_cfg.name)
            else:
                logger.debug("Domain plugin skipped (not in active_domains): %s", domain_cfg.id)

        # Set default domain
        if settings.default_domain:
            registry.set_default(settings.default_domain)

        logger.info("Domain registry: %d active domain(s)", len(registry.list_all()))
    except Exception as e:
        logger.warning("Domain plugin discovery failed: %s (service will continue)", e)

    # =========================================================================
    # DATABASE MIGRATION (Auto-run Alembic on startup — SOTA 2026)
    # =========================================================================
    try:
        import os
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        alembic_ini_path = os.path.join(
            os.path.dirname(__file__), "..", "alembic.ini"
        )
        if os.path.exists(alembic_ini_path):
            alembic_cfg = AlembicConfig(alembic_ini_path)
            alembic_cfg.set_main_option(
                "script_location",
                os.path.join(os.path.dirname(__file__), "..", "alembic"),
            )
            alembic_command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations applied (Alembic upgrade head)")
        else:
            logger.info("alembic.ini not found — skipping migrations")
    except Exception as e:
        logger.warning("Database migration failed: %s (service will continue)", e)

    # =========================================================================
    # PRE-WARMING AI COMPONENTS (SOTA Memory Optimization - Dec 2025)
    # =========================================================================
    # Purpose: Initialize shared LLM Pool instead of individual components
    # Reference: MEMORY_OVERFLOW_SOTA_ANALYSIS.md
    # Impact: Reduces memory from ~600MB to ~120MB (3 shared LLM instances)
    # =========================================================================
    
    # 1. CRITICAL: Initialize LLM Singleton Pool FIRST (SOTA Pattern)
    #    This creates only 3 shared LLM instances (DEEP, MODERATE, LIGHT)
    #    All components will share these instances instead of creating their own
    try:
        from app.engine.llm_pool import LLMPool
        LLMPool.initialize()
        logger.info("[OK] LLM Singleton Pool initialized (3 shared instances, ~120MB)")
    except Exception as e:
        logger.warning("[WARN] LLM Pool initialization failed: %s", e)
    
    # 1a. Initialize Per-Agent Config Registry (Sprint 69)
    try:
        from app.engine.multi_agent.agent_config import AgentConfigRegistry
        AgentConfigRegistry.initialize(settings.agent_provider_configs)
        logger.info("[OK] AgentConfigRegistry initialized (per-node LLM config)")
    except Exception as e:
        logger.warning("[WARN] AgentConfigRegistry initialization failed: %s", e)

    # 1b. Initialize Unified LLM Client (Sprint 55: AsyncOpenAI SDK)
    if settings.enable_unified_client:
        try:
            from app.engine.llm_providers.unified_client import UnifiedLLMClient
            UnifiedLLMClient.initialize()
            logger.info("[OK] UnifiedLLMClient initialized (AsyncOpenAI SDK)")
        except Exception as e:
            logger.warning("[WARN] UnifiedLLMClient initialization failed: %s", e)

    # 1b. Validate embedding dimensions against config (SOTA 2026)
    try:
        from app.core.constants import EXPECTED_EMBEDDING_DIMENSIONS
        if settings.embedding_dimensions != EXPECTED_EMBEDDING_DIMENSIONS:
            logger.error(
                "Embedding dimension mismatch: config=%d, "
                "expected=%d. "
                "This may cause pgvector index errors.",
                settings.embedding_dimensions,
                EXPECTED_EMBEDDING_DIMENSIONS,
            )
        else:
            logger.info("Embedding dimension validated: %dd", settings.embedding_dimensions)
    except Exception as e:
        logger.warning("Embedding dimension validation skipped: %s", e)

    # 2. Pre-warm RAGAgent singleton (now uses shared LLM from pool)
    try:
        from app.engine.agentic_rag import get_rag_agent, is_rag_agent_initialized
        get_rag_agent()
        if is_rag_agent_initialized():
            logger.info("[OK] RAGAgent singleton pre-warmed (using shared LLM)")
    except Exception as e:
        logger.warning("[WARN] RAGAgent pre-warm failed: %s", e)
    
    # 3. Pre-warm CorrectiveRAG singleton (now uses shared LLMs from pool)
    try:
        from app.engine.agentic_rag import get_corrective_rag
        get_corrective_rag()
        logger.info("[OK] CorrectiveRAG pre-warmed (using shared LLMs)")
    except Exception as e:
        logger.warning("[WARN] CorrectiveRAG pre-warm failed: %s", e)
    
    # 4. Pre-warm Multi-Agent Graph WITH checkpointer (SOTA 2026)
    try:
        from app.engine.multi_agent.graph import get_multi_agent_graph_async
        await get_multi_agent_graph_async()
        logger.info("Multi-Agent Graph pre-warmed (with checkpointer)")
    except Exception as e:
        logger.warning("Multi-Agent Graph pre-warm failed: %s", e)

    # NOTE: ChatService pre-warming is REMOVED to save memory
    # The service will be initialized on first request instead
    # This eliminates ~10 additional LLM instance creations
    logger.info("ChatService will initialize on first request (memory optimized)")
    
    # Startup health verification (SOTA 2026: Fail-fast on broken init)
    try:
        from app.api.v1.health import check_api_health
        health = await check_api_health()
        logger.info("Startup health check: %s", health.status.value)
    except Exception as e:
        logger.warning("Startup health check skipped: %s", e)

    # MCP Client (Sprint 56: Connect to external MCP servers)
    if settings.enable_mcp_client:
        try:
            from app.mcp.client import MCPToolManager
            configs = MCPToolManager.parse_configs(settings.mcp_server_configs)
            await MCPToolManager.initialize(configs)
            logger.info("[OK] MCP Client initialized")
        except Exception as e:
            logger.warning("[WARN] MCP Client initialization failed: %s", e)

    # Scheduled Task Executor (Sprint 20: Proactive Agent Activation)
    _executor = None
    if settings.enable_scheduler:
        try:
            from app.services.scheduled_task_executor import get_scheduled_task_executor
            _executor = get_scheduled_task_executor()
            await _executor.start()
            logger.info(
                "Scheduled task executor started "
                "(poll every %ds)",
                settings.scheduler_poll_interval,
            )
        except Exception as e:
            logger.warning("Scheduled task executor startup failed: %s", e)

    # =========================================================================
    # LIVING AGENT HEARTBEAT (Sprint 170: Linh Hồn Sống)
    # Sprint 188: Load persisted emotion state before heartbeat starts
    # =========================================================================
    _heartbeat = None
    if settings.enable_living_agent:
        try:
            # Sprint 188: Restore emotion state from DB (survives restart)
            from app.engine.living_agent.emotion_engine import get_emotion_engine
            _emotion_engine = get_emotion_engine()
            loaded = await _emotion_engine.load_from_db_if_needed()
            if loaded:
                logger.info("[OK] Emotion state restored from DB: mood=%s", _emotion_engine.mood.value)
            else:
                logger.info("[OK] Emotion engine initialized with defaults")
        except Exception as e:
            logger.warning("[WARN] Emotion state restore failed: %s", e)

        try:
            from app.engine.living_agent.heartbeat import get_heartbeat_scheduler
            _heartbeat = get_heartbeat_scheduler()
            await _heartbeat.start()
            logger.info(
                "[OK] Living Agent heartbeat started "
                "(interval=%ds, active %d:00-%d:00 UTC+7)",
                settings.living_agent_heartbeat_interval,
                settings.living_agent_active_hours_start,
                settings.living_agent_active_hours_end,
            )
        except Exception as e:
            logger.warning("[WARN] Living Agent heartbeat startup failed: %s", e)

    # =========================================================================
    # LMS CONNECTOR BOOTSTRAP (Sprint 155: Cầu Nối)
    # =========================================================================
    if settings.enable_lms_integration:
        try:
            from app.integrations.lms.loader import bootstrap_lms_connectors
            lms_count = bootstrap_lms_connectors(settings)
            logger.info("[OK] LMS integration: %d connector(s) registered", lms_count)
        except Exception as e:
            logger.warning("[WARN] LMS connector bootstrap failed: %s", e)

    logger.info("[START] %s started successfully", settings.app_name)

    yield
    
    # Shutdown - Close Neo4j driver explicitly (Requirements: 2.1, 2.2)
    logger.info("Shutting down %s...", settings.app_name)
    
    if neo4j_repo is not None:
        try:
            neo4j_repo.close()
            logger.info("[OK] Neo4j driver closed successfully")
        except Exception as e:
            logger.error("[FAIL] Failed to close Neo4j driver: %s", e)
    
    # Stop scheduled task executor
    if _executor:
        try:
            await _executor.shutdown(timeout=10)
            logger.info("Scheduled task executor stopped")
        except Exception as e:
            logger.warning("Executor shutdown failed: %s", e)

    # Stop Living Agent heartbeat (Sprint 170)
    if _heartbeat:
        try:
            await _heartbeat.stop()
            logger.info("Living Agent heartbeat stopped")
        except Exception as e:
            logger.warning("Heartbeat shutdown failed: %s", e)

    # Sprint 188: Persist emotion state before shutdown
    if settings.enable_living_agent:
        try:
            from app.engine.living_agent.emotion_engine import get_emotion_engine
            await get_emotion_engine().save_state_to_db()
            logger.info("Emotion state persisted on shutdown")
        except Exception as e:
            logger.warning("Emotion persist on shutdown failed: %s", e)

    # Shut down MCP Client (Sprint 56)
    if settings.enable_mcp_client:
        try:
            from app.mcp.client import MCPToolManager
            await MCPToolManager.shutdown()
        except Exception as e:
            logger.warning("MCP Client shutdown failed: %s", e)

    # Close LangGraph checkpointer connection
    try:
        from app.engine.multi_agent.checkpointer import close_checkpointer
        await close_checkpointer()
        logger.info("Checkpointer connection closed")
    except Exception as e:
        logger.warning("Checkpointer close failed: %s", e)

    # Close Sources API asyncpg pool (Sprint 32: resource cleanup)
    try:
        from app.api.v1.sources import close_pool
        await close_pool()
    except Exception as e:
        logger.warning("Sources pool close failed: %s", e)

    # Close Dense/Sparse search asyncpg pools (audit fix: resource leak)
    try:
        from app.repositories.dense_search_repository import get_dense_search_repository
        await get_dense_search_repository().close()
        logger.info("Dense search pool closed")
    except Exception as e:
        logger.debug("Dense search pool close skipped: %s", e)
    try:
        from app.repositories.sparse_search_repository import get_sparse_search_repository
        await get_sparse_search_repository().close()
        logger.info("Sparse search pool closed")
    except Exception as e:
        logger.debug("Sparse search pool close skipped: %s", e)

    # Sprint 153: Close Playwright browser singleton (if initialized)
    try:
        from app.engine.search_platforms.adapters.browser_base import close_browser
        close_browser()
        logger.info("Playwright browser closed")
    except Exception as e:
        logger.debug("Browser close skipped: %s", e)

    # Close shared database engine
    try:
        from app.core.database import close_shared_engine
        close_shared_engine()
        logger.info("Shared database engine closed successfully")
    except Exception as e:
        logger.error("Failed to close shared database engine: %s", e)

    logger.info("[SHUTDOWN] %s shutdown complete", settings.app_name)


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

    
    # Configure CORS - Allow LMS Frontend origins
    # When allow_credentials=True, cannot use ["*"] for origins
    cors_origins = [
        "http://localhost:4200",      # Angular dev server
        "http://localhost:4300",      # Angular alternative port
        "http://localhost:3000",      # React/Next.js dev server
        "http://localhost:8080",      # Local test UI server
        "http://localhost:1420",      # Tauri/Vite dev server (wiii-desktop)
        "http://127.0.0.1:4200",
        "http://127.0.0.1:4300",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:1420",     # Tauri/Vite dev server
        "https://tauri.localhost",    # Tauri production webview
        "tauri://localhost",          # Tauri custom protocol
        # Production domain — configure via CORS_ORIGINS env var
        "https://*.vercel.app",       # Vercel deployments
        "https://*.netlify.app",      # Netlify deployments
    ]

    
    # Add any custom origins from settings
    if settings.cors_origins and settings.cors_origins != ["*"]:
        cors_origins.extend(settings.cors_origins)

    # Sprint 175: Support regex-based CORS for wildcard subdomains
    cors_kwargs: dict = dict(
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    if settings.cors_origin_regex:
        cors_kwargs["allow_origin_regex"] = settings.cors_origin_regex
        # Keep explicit origins as fallback for dev URLs
        cors_kwargs["allow_origins"] = cors_origins
    else:
        cors_kwargs["allow_origins"] = cors_origins

    app.add_middleware(CORSMiddleware, **cors_kwargs)

    # Sprint 157: Session middleware for OAuth CSRF state (must be before auth routes)
    # Sprint 194c (B5/B9): Validate secret key length for secure CSRF state
    if settings.enable_google_oauth:
        from starlette.middleware.sessions import SessionMiddleware
        if len(settings.session_secret_key) < 32:
            logger.warning(
                "SECURITY: SessionMiddleware secret_key is only %d chars — "
                "recommend at least 32 chars for secure OAuth CSRF state",
                len(settings.session_secret_key),
            )
        app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)

    # Middleware stack (Starlette executes in REVERSE of add order)
    # So: add RequestID first, OrgContext second → executes OrgContext first, then RequestID outermost
    from app.core.middleware import RequestIDMiddleware, OrgContextMiddleware
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(OrgContextMiddleware)  # Sprint 24: Multi-Tenant org context

    # Configure Rate Limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    
    # Register exception handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    from app.core.exceptions import WiiiException
    app.add_exception_handler(WiiiException, wiii_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    # Include API routers
    from app.api.v1 import router as api_v1_router
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    # MCP Server (Sprint 56: Mount after routers so endpoints are discoverable)
    if settings.enable_mcp_server:
        try:
            from app.mcp.server import setup_mcp_server
            setup_mcp_server(app)
        except Exception as e:
            logger.warning("MCP Server mount failed: %s", e)

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
    logger.exception(f"Unexpected error: {exc}")
    
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
