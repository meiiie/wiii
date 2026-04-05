"""Support helpers for admin ingestion routes."""

from __future__ import annotations


def cleanup_old_jobs_impl(*, ingestion_jobs: dict, max_tracked_jobs: int) -> None:
    """Remove oldest terminal jobs once the in-memory cap is exceeded."""
    if len(ingestion_jobs) <= max_tracked_jobs:
        return

    completed = [
        job_id
        for job_id, job in ingestion_jobs.items()
        if job.get("status") in ("completed", "failed")
    ]
    for job_id in completed[: len(ingestion_jobs) - max_tracked_jobs]:
        del ingestion_jobs[job_id]


async def run_ingestion_background_impl(
    *,
    job_id: str,
    document_id: str,
    pdf_path: str,
    create_neo4j_module: bool,
    ingestion_jobs: dict,
    cleanup_old_jobs,
    get_ingestion_service_fn,
    get_user_graph_repository_fn,
    logger_obj,
) -> None:
    """Execute the PDF ingestion workflow and update in-memory job state."""
    try:
        ingestion_jobs[job_id]["status"] = "processing"

        ingestion_service = get_ingestion_service_fn()
        result = await ingestion_service.ingest_pdf(
            pdf_path=pdf_path,
            document_id=document_id,
            resume=True,
        )

        ingestion_jobs[job_id]["total_pages"] = result.total_pages
        ingestion_jobs[job_id]["processed_pages"] = result.successful_pages
        ingestion_jobs[job_id]["progress_percent"] = result.success_rate

        if create_neo4j_module:
            user_graph = get_user_graph_repository_fn()
            if user_graph.is_available():
                user_graph.ensure_module_node(
                    module_id=document_id,
                    title=document_id.replace("_", " ").title(),
                )
                logger_obj.info("[ADMIN] Created Module node in Neo4j: %s", document_id)

        ingestion_jobs[job_id]["status"] = "completed"
        logger_obj.info(
            "[ADMIN] Ingestion completed for %s: %.0f%% success",
            document_id,
            result.success_rate * 100,
        )
        cleanup_old_jobs()
    except Exception as exc:
        ingestion_jobs[job_id]["status"] = "failed"
        ingestion_jobs[job_id]["error"] = "Ingestion processing failed"
        logger_obj.error("[ADMIN] Ingestion failed for %s: %s", document_id, exc)
        cleanup_old_jobs()
