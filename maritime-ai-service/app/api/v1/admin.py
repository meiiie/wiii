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
from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel, Field

from app.api.deps import RequireAuth, RequireAdmin
from app.core.rate_limit import limiter
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
