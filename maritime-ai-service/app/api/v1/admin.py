"""
Admin API Router - Document & Domain Management for LMS Admins

Phase 6: Admin Document API + Domain Plugin Management
Enables LMS admins to:
- Upload and ingest documents into knowledge base
- Check ingestion status
- List all documents
- Delete documents
- List and inspect domain plugins
- View domain skills and routing config

Pattern: LangChain Enterprise Best Practices
"""

import logging
import os
import tempfile
from typing import Optional
from uuid import uuid4
from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field

from app.api.deps import RequireAuth, RequireAdmin
from app.core.config import settings
from app.core.rate_limit import limiter
from app.engine.model_catalog import GOOGLE_DEFAULT_MODEL, get_chat_model_metadata
from app.engine.llm_provider_registry import is_supported_provider
from app.engine.llm_runtime_profiles import (
    get_runtime_provider_preset,
    is_known_default_provider_chain,
    should_apply_openrouter_defaults,
)
from app.services.multimodal_ingestion_service import get_ingestion_service
from app.repositories.user_graph_repository import get_user_graph_repository
from app.domains.registry import get_domain_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

# =============================================================================
# Schemas
# =============================================================================

class DocumentUploadResponse(BaseModel):
    """Response after document upload."""
    job_id: str = Field(..., description="Ingestion job ID for status tracking")
    document_id: str = Field(..., description="Document identifier")
    status: str = Field(..., description="pending | processing | completed | failed")
    message: str = Field(..., description="Status message")


class DocumentStatus(BaseModel):
    """Document ingestion status."""
    job_id: str
    document_id: str
    status: str  # pending | processing | completed | failed
    progress_percent: float = 0.0
    total_pages: int = 0
    processed_pages: int = 0
    error: Optional[str] = None


class DocumentInfo(BaseModel):
    """Document information."""
    document_id: str
    title: str
    total_pages: int
    total_chunks: int
    created_at: str
    status: str


class ModelCatalogEntry(BaseModel):
    provider: str
    model_name: str
    display_name: str
    status: str  # "current", "legacy", "available", "preset"
    released_on: Optional[str] = None
    is_default: bool = False


class ModelCatalogResponse(BaseModel):
    providers: dict[str, list[ModelCatalogEntry]]
    embedding_models: list[ModelCatalogEntry] = []
    ollama_discovered: bool = False
    timestamp: str


class LlmRuntimeConfigResponse(BaseModel):
    provider: str
    use_multi_agent: bool
    google_model: str
    openai_base_url: Optional[str] = None
    openai_model: str
    openai_model_advanced: str
    openrouter_model_fallbacks: list[str] = Field(default_factory=list)
    openrouter_provider_order: list[str] = Field(default_factory=list)
    openrouter_allowed_providers: list[str] = Field(default_factory=list)
    openrouter_ignored_providers: list[str] = Field(default_factory=list)
    openrouter_allow_fallbacks: Optional[bool] = None
    openrouter_require_parameters: Optional[bool] = None
    openrouter_data_collection: Optional[str] = None
    openrouter_zdr: Optional[bool] = None
    openrouter_provider_sort: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: str
    ollama_keep_alive: Optional[str] = None
    google_api_key_configured: bool
    openai_api_key_configured: bool
    ollama_api_key_configured: bool
    enable_llm_failover: bool
    llm_failover_chain: list[str]
    active_provider: Optional[str] = None
    providers_registered: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LlmRuntimeConfigUpdate(BaseModel):
    provider: Optional[str] = Field(
        default=None,
        description="google | openai | openrouter | ollama",
    )
    use_multi_agent: Optional[bool] = None
    google_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key",
    )
    clear_google_api_key: bool = False
    google_model: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI/OpenRouter API key",
    )
    clear_openai_api_key: bool = False
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    openai_model_advanced: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    openrouter_model_fallbacks: Optional[list[str]] = None
    openrouter_provider_order: Optional[list[str]] = None
    openrouter_allowed_providers: Optional[list[str]] = None
    openrouter_ignored_providers: Optional[list[str]] = None
    openrouter_allow_fallbacks: Optional[bool] = None
    openrouter_require_parameters: Optional[bool] = None
    openrouter_data_collection: Optional[str] = None
    openrouter_zdr: Optional[bool] = None
    openrouter_provider_sort: Optional[str] = None
    ollama_api_key: Optional[str] = Field(
        default=None,
        description="Ollama Cloud API key",
    )
    clear_ollama_api_key: bool = False
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    ollama_keep_alive: Optional[str] = None
    enable_llm_failover: Optional[bool] = None
    llm_failover_chain: Optional[list[str]] = None


def _can_manage_llm_runtime(auth) -> bool:
    if auth.role == "admin":
        return True
    return (
        settings.environment != "production"
        and auth.auth_method == "api_key"
    )


def _normalize_provider_name(provider: Optional[str]) -> Optional[str]:
    if provider is None:
        return None
    normalized = provider.strip().lower()
    if not is_supported_provider(normalized):
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported provider: {provider}",
        )
    return normalized


def _normalize_chain(chain: Optional[list[str]]) -> Optional[list[str]]:
    if chain is None:
        return None
    normalized: list[str] = []
    for item in chain:
        provider = _normalize_provider_name(item)
        if provider and provider not in normalized:
            normalized.append(provider)
    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="llm_failover_chain cannot be empty",
        )
    return normalized


def _normalize_string_list(values: Optional[list[str]]) -> Optional[list[str]]:
    if values is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        value = item.strip()
        if not value or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _normalize_optional_choice(
    value: Optional[str],
    *,
    allowed: set[str],
    field_name: str,
) -> Optional[str]:
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be one of {sorted(allowed)}",
        )
    return normalized


def _serialize_llm_runtime(warnings: list[str] | None = None) -> LlmRuntimeConfigResponse:
    from app.engine.llm_pool import LLMPool

    stats = LLMPool.get_stats()
    provider = settings.llm_provider
    keep_alive = getattr(settings, "ollama_keep_alive", None)
    if not isinstance(keep_alive, str):
        keep_alive = None
    else:
        keep_alive = keep_alive.strip() or None
    google_model = settings.google_model or GOOGLE_DEFAULT_MODEL
    google_metadata = get_chat_model_metadata(google_model)
    if google_metadata and google_metadata.status == "legacy":
        logger.warning("Serializing legacy Google model in admin runtime config: %s", google_model)

    return LlmRuntimeConfigResponse(
        provider=provider,
        use_multi_agent=getattr(settings, "use_multi_agent", True),
        google_model=google_model,
        openai_base_url=settings.openai_base_url,
        openai_model=settings.openai_model,
        openai_model_advanced=settings.openai_model_advanced,
        openrouter_model_fallbacks=list(getattr(settings, "openrouter_model_fallbacks", [])),
        openrouter_provider_order=list(getattr(settings, "openrouter_provider_order", [])),
        openrouter_allowed_providers=list(getattr(settings, "openrouter_allowed_providers", [])),
        openrouter_ignored_providers=list(getattr(settings, "openrouter_ignored_providers", [])),
        openrouter_allow_fallbacks=getattr(settings, "openrouter_allow_fallbacks", None),
        openrouter_require_parameters=getattr(settings, "openrouter_require_parameters", None),
        openrouter_data_collection=getattr(settings, "openrouter_data_collection", None),
        openrouter_zdr=getattr(settings, "openrouter_zdr", None),
        openrouter_provider_sort=getattr(settings, "openrouter_provider_sort", None),
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
        ollama_keep_alive=keep_alive,
        google_api_key_configured=bool(settings.google_api_key),
        openai_api_key_configured=bool(settings.openai_api_key),
        ollama_api_key_configured=bool(getattr(settings, "ollama_api_key", None)),
        enable_llm_failover=settings.enable_llm_failover,
        llm_failover_chain=list(getattr(settings, "llm_failover_chain", [])),
        active_provider=stats.get("active_provider"),
        providers_registered=list(stats.get("providers_registered", [])),
        warnings=warnings or [],
    )


# =============================================================================
# In-memory job tracking (replace with DB in production)
# =============================================================================

_ingestion_jobs: dict = {}  # job_id -> DocumentStatus
_MAX_TRACKED_JOBS = 100  # Prevent unbounded memory growth


def _cleanup_old_jobs():
    """Remove oldest completed/failed jobs when limit exceeded."""
    if len(_ingestion_jobs) <= _MAX_TRACKED_JOBS:
        return
    completed = [
        jid for jid, j in _ingestion_jobs.items()
        if j.get("status") in ("completed", "failed")
    ]
    # Remove oldest completed jobs first
    for jid in completed[:len(_ingestion_jobs) - _MAX_TRACKED_JOBS]:
        del _ingestion_jobs[jid]


@router.get("/llm-runtime", response_model=LlmRuntimeConfigResponse)
async def get_llm_runtime_config(auth: RequireAuth):
    if not _can_manage_llm_runtime(auth):
        raise HTTPException(
            status_code=403,
            detail="Admin or local developer access required.",
        )
    return _serialize_llm_runtime()


@router.get("/model-catalog", response_model=ModelCatalogResponse)
async def get_model_catalog(auth: RequireAuth):
    """Return available models from all providers (static + Ollama discovery)."""
    if not _can_manage_llm_runtime(auth):
        raise HTTPException(status_code=403, detail="Admin or local developer access required.")

    from app.engine.model_catalog import (
        ModelCatalogService, GOOGLE_DEFAULT_MODEL, DEFAULT_EMBEDDING_MODEL,
        EMBEDDING_MODELS,
    )

    catalog = await ModelCatalogService.get_full_catalog(
        ollama_base_url=settings.ollama_base_url if settings.ollama_base_url else None,
    )

    # Convert to response format
    providers_out: dict[str, list[ModelCatalogEntry]] = {}
    for provider, models in catalog["providers"].items():
        entries = []
        for model_name, meta in models.items():
            is_default = False
            if provider == "google" and model_name == settings.google_model:
                is_default = True
            elif provider == "ollama" and model_name == settings.ollama_model:
                is_default = True
            entries.append(ModelCatalogEntry(
                provider=meta.provider,
                model_name=meta.model_name,
                display_name=meta.display_name,
                status=meta.status,
                released_on=meta.released_on,
                is_default=is_default,
            ))
        # Sort: current/available first, then preset, then legacy
        status_order = {"current": 0, "available": 1, "preset": 2, "legacy": 3}
        entries.sort(key=lambda e: (status_order.get(e.status, 9), e.model_name))
        providers_out[provider] = entries

    # Embedding models
    embedding_entries = []
    for model_name, meta in catalog.get("embedding_models", {}).items():
        embedding_entries.append(ModelCatalogEntry(
            provider="google",
            model_name=meta.model_name,
            display_name=meta.display_name,
            status=meta.status,
            released_on=meta.released_on,
            is_default=(model_name == settings.embedding_model),
        ))

    return ModelCatalogResponse(
        providers=providers_out,
        embedding_models=embedding_entries,
        ollama_discovered=catalog.get("ollama_discovered", False),
        timestamp=catalog["timestamp"],
    )


@router.patch("/llm-runtime", response_model=LlmRuntimeConfigResponse)
async def update_llm_runtime_config(
    body: LlmRuntimeConfigUpdate,
    auth: RequireAuth,
):
    if not _can_manage_llm_runtime(auth):
        raise HTTPException(
            status_code=403,
            detail="Admin or local developer access required.",
        )

    provider = (
        _normalize_provider_name(body.provider)
        if body.provider is not None
        else None
    )
    chain = _normalize_chain(body.llm_failover_chain)
    openrouter_model_fallbacks = _normalize_string_list(body.openrouter_model_fallbacks)
    openrouter_provider_order = _normalize_string_list(body.openrouter_provider_order)
    openrouter_allowed_providers = _normalize_string_list(body.openrouter_allowed_providers)
    openrouter_ignored_providers = _normalize_string_list(body.openrouter_ignored_providers)
    openrouter_data_collection = _normalize_optional_choice(
        body.openrouter_data_collection,
        allowed={"allow", "deny"},
        field_name="openrouter_data_collection",
    )
    openrouter_provider_sort = _normalize_optional_choice(
        body.openrouter_provider_sort,
        allowed={"price", "latency", "throughput"},
        field_name="openrouter_provider_sort",
    )

    if provider is not None:
        settings.llm_provider = provider
        preset = get_runtime_provider_preset(provider)
        if provider == "google":
            if body.google_model is None and not settings.google_model:
                settings.google_model = preset.google_model or settings.google_model
        if provider == "openrouter":
            if not body.openai_base_url and not settings.openai_base_url:
                settings.openai_base_url = preset.openai_base_url
            if (
                body.openai_model is None
                and should_apply_openrouter_defaults(settings.openai_model)
            ):
                settings.openai_model = preset.openai_model or settings.openai_model
            if (
                body.openai_model_advanced is None
                and should_apply_openrouter_defaults(settings.openai_model_advanced)
            ):
                settings.openai_model_advanced = (
                    preset.openai_model_advanced or settings.openai_model_advanced
                )
        if provider == "ollama":
            if not body.ollama_base_url and not settings.ollama_base_url:
                settings.ollama_base_url = preset.ollama_base_url
            if body.ollama_model is None and not settings.ollama_model:
                settings.ollama_model = preset.ollama_model or settings.ollama_model
            if body.ollama_keep_alive is None and not getattr(settings, "ollama_keep_alive", None):
                settings.ollama_keep_alive = preset.ollama_keep_alive
        if chain is None and is_known_default_provider_chain(
            getattr(settings, "llm_failover_chain", None)
        ):
            settings.llm_failover_chain = list(preset.failover_chain)

    if body.use_multi_agent is not None:
        settings.use_multi_agent = body.use_multi_agent

    if body.google_api_key is not None:
        settings.google_api_key = body.google_api_key.strip() or None
    elif body.clear_google_api_key:
        settings.google_api_key = None

    if body.google_model is not None:
        settings.google_model = body.google_model.strip()

    if body.openai_api_key is not None:
        settings.openai_api_key = body.openai_api_key.strip() or None
    elif body.clear_openai_api_key:
        settings.openai_api_key = None

    if body.ollama_api_key is not None:
        settings.ollama_api_key = body.ollama_api_key.strip() or None
    elif body.clear_ollama_api_key:
        settings.ollama_api_key = None

    if body.openai_base_url is not None:
        settings.openai_base_url = body.openai_base_url.strip() or None
    if body.openai_model is not None:
        settings.openai_model = body.openai_model.strip()
    if body.openai_model_advanced is not None:
        settings.openai_model_advanced = body.openai_model_advanced.strip()
    if openrouter_model_fallbacks is not None:
        settings.openrouter_model_fallbacks = openrouter_model_fallbacks
    if openrouter_provider_order is not None:
        settings.openrouter_provider_order = openrouter_provider_order
    if openrouter_allowed_providers is not None:
        settings.openrouter_allowed_providers = openrouter_allowed_providers
    if openrouter_ignored_providers is not None:
        settings.openrouter_ignored_providers = openrouter_ignored_providers
    if body.openrouter_allow_fallbacks is not None:
        settings.openrouter_allow_fallbacks = body.openrouter_allow_fallbacks
    if body.openrouter_require_parameters is not None:
        settings.openrouter_require_parameters = body.openrouter_require_parameters
    if body.openrouter_data_collection is not None:
        settings.openrouter_data_collection = openrouter_data_collection
    if body.openrouter_zdr is not None:
        settings.openrouter_zdr = body.openrouter_zdr
    if body.openrouter_provider_sort is not None:
        settings.openrouter_provider_sort = openrouter_provider_sort
    if body.ollama_base_url is not None:
        settings.ollama_base_url = body.ollama_base_url.strip() or None
    if body.ollama_model is not None:
        settings.ollama_model = body.ollama_model.strip()
    if body.ollama_keep_alive is not None:
        settings.ollama_keep_alive = body.ollama_keep_alive.strip() or None
    if body.enable_llm_failover is not None:
        settings.enable_llm_failover = body.enable_llm_failover
    if chain is not None:
        settings.llm_failover_chain = chain
    settings.refresh_nested_views()

    from app.engine.llm_pool import LLMPool
    from app.services.chat_service import reset_chat_service

    LLMPool.reset()
    reset_chat_service()
    logger.info(
        "[ADMIN] Updated LLM runtime config: provider=%s "
        "multi_agent=%s failover=%s chain=%s base_url=%s",
        settings.llm_provider,
        getattr(settings, "use_multi_agent", True),
        settings.enable_llm_failover,
        settings.llm_failover_chain,
        settings.openai_base_url,
    )

    # Catalog-driven validation (warnings only, never reject)
    warnings = []
    from app.engine.model_catalog import is_known_model, is_legacy_google_model
    if body.google_model is not None:
        gm = body.google_model.strip()
        if is_legacy_google_model(gm):
            warnings.append(f"google_model '{gm}' is legacy. Consider a current model.")
        elif not is_known_model("google", gm):
            warnings.append(f"google_model '{gm}' is not in the known catalog.")
    if body.ollama_model is not None:
        om = body.ollama_model.strip()
        if not is_known_model("ollama", om):
            warnings.append(f"ollama_model '{om}' is not in the known catalog.")
    if body.openai_model is not None:
        oam = body.openai_model.strip()
        if not is_known_model("openrouter", oam):
            warnings.append(f"openai_model '{oam}' is not in the known catalog.")

    return _serialize_llm_runtime(warnings=warnings)


# =============================================================================
# Background Ingestion Task
# =============================================================================

async def _run_ingestion_background(
    job_id: str,
    document_id: str,
    pdf_path: str,
    create_neo4j_module: bool = True
):
    """
    Background task for document ingestion.
    
    Steps:
    1. Update job status to "processing"
    2. Run multimodal ingestion
    3. Create Module node in Neo4j (if enabled)
    4. Update job status to "completed" or "failed"
    """
    try:
        _ingestion_jobs[job_id]["status"] = "processing"
        
        # Run ingestion
        ingestion_service = get_ingestion_service()
        result = await ingestion_service.ingest_pdf(
            pdf_path=pdf_path,
            document_id=document_id,
            resume=True
        )
        
        # Update progress
        _ingestion_jobs[job_id]["total_pages"] = result.total_pages
        _ingestion_jobs[job_id]["processed_pages"] = result.successful_pages
        _ingestion_jobs[job_id]["progress_percent"] = result.success_rate
        
        # Create Module node in Neo4j (Phase 4 + 6 integration)
        if create_neo4j_module:
            user_graph = get_user_graph_repository()
            if user_graph.is_available():
                user_graph.ensure_module_node(
                    module_id=document_id,
                    title=document_id.replace("_", " ").title()
                )
                logger.info("[ADMIN] Created Module node in Neo4j: %s", document_id)
        
        _ingestion_jobs[job_id]["status"] = "completed"
        logger.info("[ADMIN] Ingestion completed for %s: %.0f%% success", document_id, result.success_rate * 100)
        _cleanup_old_jobs()

    except Exception as e:
        _ingestion_jobs[job_id]["status"] = "failed"
        _ingestion_jobs[job_id]["error"] = "Ingestion processing failed"
        logger.error("[ADMIN] Ingestion failed for %s: %s", document_id, e)
        _cleanup_old_jobs()


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/documents", response_model=DocumentUploadResponse)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    auth: RequireAdmin,  # LMS Integration: Admin only
    file: UploadFile = File(..., description="PDF file to ingest"),
    document_id: Optional[str] = Form(None, description="Document ID (auto-generated if not provided)"),
    create_module_node: bool = Form(True, description="Create Module node in Neo4j")
):
    """
    Upload and ingest a document into knowledge base.
    
    This endpoint:
    1. Saves the uploaded PDF
    2. Starts background ingestion
    3. Returns job_id for status tracking
    4. Optionally creates Module node in Neo4j
    
    Use GET /admin/documents/{job_id} to check progress.
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Generate IDs
    job_id = str(uuid4())
    doc_id = document_id or file.filename.replace(".pdf", "").replace(" ", "_").lower()
    
    # Save file temporarily
    temp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(temp_dir, f"{doc_id}.pdf")
    
    try:
        content = await file.read()
        with open(pdf_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error("Failed to save uploaded file: %s", e)
        # Clean up temp file on save failure
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        raise HTTPException(status_code=500, detail="Failed to save file")
    
    # Initialize job status
    _ingestion_jobs[job_id] = {
        "job_id": job_id,
        "document_id": doc_id,
        "status": "pending",
        "progress_percent": 0.0,
        "total_pages": 0,
        "processed_pages": 0,
        "error": None
    }
    
    # Start background ingestion
    background_tasks.add_task(
        _run_ingestion_background,
        job_id=job_id,
        document_id=doc_id,
        pdf_path=pdf_path,
        create_neo4j_module=create_module_node
    )
    
    logger.info("[ADMIN] Document upload started: %s (job_id: %s)", doc_id, job_id)
    
    return DocumentUploadResponse(
        job_id=job_id,
        document_id=doc_id,
        status="pending",
        message=f"Ingestion started. Use GET /admin/documents/{job_id} to check status."
    )


@router.get("/documents/{job_id}", response_model=DocumentStatus)
@limiter.limit("60/minute")
async def get_document_status(request: Request, job_id: str, auth: RequireAdmin):  # LMS Integration
    """
    Check ingestion job status.
    
    Returns progress information for a document ingestion job.
    """
    if job_id not in _ingestion_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    job = _ingestion_jobs[job_id]
    return DocumentStatus(**job)


@router.get("/documents", response_model=list)
@limiter.limit("60/minute")
async def list_documents(request: Request, auth: RequireAdmin):  # LMS Integration
    """
    List all documents in knowledge base.
    
    Returns list of documents with their metadata.
    """
    from app.core.database import get_shared_session_factory
    from sqlalchemy import text
    
    try:
        session_factory = get_shared_session_factory()
        with session_factory() as session:
            result = session.execute(text("""
                SELECT 
                    document_id,
                    COUNT(*) as total_chunks,
                    MIN(created_at) as created_at
                FROM knowledge_embeddings
                GROUP BY document_id
                ORDER BY document_id
            """))
            
            documents = []
            for row in result.fetchall():
                documents.append({
                    "document_id": row[0],
                    "total_chunks": row[1],
                    "created_at": str(row[2]) if row[2] else None
                })
            
            return documents
            
    except Exception as e:
        logger.error("[ADMIN] Failed to list documents: %s", e)
        return []


@router.delete("/documents/{document_id}")
@limiter.limit("10/minute")
async def delete_document(request: Request, document_id: str, auth: RequireAdmin):  # LMS Integration: Admin only
    """
    Delete a document from knowledge base.
    
    Removes all chunks and embeddings for the specified document.
    Also removes Module node from Neo4j if exists.
    """
    from app.core.database import get_shared_session_factory
    from sqlalchemy import text
    
    try:
        # Delete from Neon
        session_factory = get_shared_session_factory()
        with session_factory() as session:
            result = session.execute(
                text("DELETE FROM knowledge_embeddings WHERE document_id = :doc_id"),
                {"doc_id": document_id}
            )
            deleted_count = result.rowcount
            session.commit()
        
        # Delete Module node from Neo4j
        user_graph = get_user_graph_repository()
        if user_graph.is_available():
            # Note: This would need a delete method in user_graph_repository
            logger.info("[ADMIN] Module node deletion not implemented yet for %s", document_id)
        
        logger.info("[ADMIN] Deleted %d chunks for document %s", deleted_count, document_id)
        
        return {
            "status": "success",
            "document_id": document_id,
            "deleted_chunks": deleted_count
        }
        
    except Exception as e:
        logger.error("[ADMIN] Failed to delete document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete document")


# =============================================================================
# Domain Management Schemas
# =============================================================================

class DomainSummary(BaseModel):
    """Domain plugin summary for list endpoint."""
    id: str
    name: str
    name_vi: str
    version: str
    description: str
    skill_count: int
    keyword_count: int


class DomainDetail(BaseModel):
    """Full domain plugin detail."""
    id: str
    name: str
    name_vi: str
    version: str
    description: str
    routing_keywords: list[str]
    mandatory_search_triggers: list[str]
    rag_agent_description: str
    tutor_agent_description: str
    skills: list[dict]
    has_prompts: bool
    has_hyde_templates: bool


class SkillDetail(BaseModel):
    """Skill manifest detail."""
    id: str
    name: str
    description: str
    domain_id: str
    version: str
    triggers: list[str]
    content_length: int


# =============================================================================
# Domain Management Endpoints
# =============================================================================

@router.get("/domains", response_model=list[DomainSummary])
@limiter.limit("60/minute")
async def list_domains(request: Request, auth: RequireAuth):
    """
    List all registered domain plugins.

    Returns summary of each active domain with skill count and status.
    """
    registry = get_domain_registry()
    all_domains = registry.list_all()

    result = []
    for domain_id, plugin in all_domains.items():
        cfg = plugin.get_config()
        skills = plugin.get_skills()
        result.append(DomainSummary(
            id=cfg.id,
            name=cfg.name,
            name_vi=cfg.name_vi,
            version=cfg.version,
            description=cfg.description,
            skill_count=len(skills),
            keyword_count=len(cfg.routing_keywords),
        ))

    return result


@router.get("/domains/{domain_id}", response_model=DomainDetail)
@limiter.limit("60/minute")
async def get_domain(request: Request, domain_id: str, auth: RequireAuth):
    """
    Get detailed information about a specific domain plugin.

    Returns config, keywords, triggers, skills, and feature flags.
    """
    registry = get_domain_registry()
    plugin = registry.get(domain_id)

    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    cfg = plugin.get_config()
    skills = plugin.get_skills()
    hyde = plugin.get_hyde_templates()
    prompts_dir = plugin.get_prompts_dir()

    return DomainDetail(
        id=cfg.id,
        name=cfg.name,
        name_vi=cfg.name_vi,
        version=cfg.version,
        description=cfg.description,
        routing_keywords=cfg.routing_keywords,
        mandatory_search_triggers=cfg.mandatory_search_triggers,
        rag_agent_description=cfg.rag_agent_description,
        tutor_agent_description=cfg.tutor_agent_description,
        skills=[
            {"id": s.id, "name": s.name, "description": s.description}
            for s in skills
        ],
        has_prompts=prompts_dir.exists() if prompts_dir else False,
        has_hyde_templates=len(hyde) > 0,
    )


@router.get("/domains/{domain_id}/skills", response_model=list[SkillDetail])
@limiter.limit("60/minute")
async def list_domain_skills(request: Request, domain_id: str, auth: RequireAuth):
    """
    List all skills for a specific domain.

    Returns skill manifests with trigger keywords and content size.
    """
    registry = get_domain_registry()
    plugin = registry.get(domain_id)

    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found")

    skills = plugin.get_skills()
    result = []
    for s in skills:
        content = plugin.activate_skill(s.id)
        result.append(SkillDetail(
            id=s.id,
            name=s.name,
            description=s.description,
            domain_id=s.domain_id,
            version=s.version,
            triggers=s.triggers,
            content_length=len(content) if content else 0,
        ))

    return result
