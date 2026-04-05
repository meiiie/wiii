"""Setup and small helper routines for CorrectiveRAG."""

from __future__ import annotations

from app.cache.cache_manager import get_cache_manager
from app.cache.models import CacheConfig
from app.core.config import settings
from app.engine.agentic_rag.answer_verifier import get_answer_verifier
from app.engine.agentic_rag.query_analyzer import get_query_analyzer
from app.engine.agentic_rag.query_rewriter import get_query_rewriter
from app.engine.agentic_rag.retrieval_grader import get_retrieval_grader


def initialize_corrective_rag_impl(
    instance,
    rag_agent,
    max_iterations,
    grade_threshold,
    enable_verification,
    logger_obj,
    *,
    settings_obj=settings,
    get_query_analyzer_fn=get_query_analyzer,
    get_retrieval_grader_fn=get_retrieval_grader,
    get_query_rewriter_fn=get_query_rewriter,
    get_answer_verifier_fn=get_answer_verifier,
    get_cache_manager_fn=get_cache_manager,
) -> None:
    """Populate CorrectiveRAG dependencies and runtime settings."""
    instance._max_iterations = (
        max_iterations if max_iterations is not None else settings_obj.rag_max_iterations
    )
    instance._grade_threshold = (
        grade_threshold if grade_threshold is not None else (settings_obj.rag_confidence_high * 10)
    )
    instance._enable_verification = (
        enable_verification if enable_verification is not None else settings_obj.enable_answer_verification
    )

    if rag_agent is not None:
        instance._rag = rag_agent
        logger_obj.info("[CRAG] Using provided RAG agent (legacy mode)")
    else:
        try:
            from app.engine.agentic_rag.rag_agent import get_rag_agent

            instance._rag = get_rag_agent()
            logger_obj.info("[CRAG] Using RAGAgent singleton (memory optimized)")
        except Exception as exc:
            logger_obj.error("[CRAG] Failed to get RAGAgent singleton: %s", exc)
            instance._rag = None

    instance._analyzer = get_query_analyzer_fn()
    instance._grader = get_retrieval_grader_fn()
    instance._rewriter = get_query_rewriter_fn()
    instance._verifier = get_answer_verifier_fn()

    instance._cache_enabled = settings_obj.semantic_cache_enabled
    if instance._cache_enabled:
        cache_config = CacheConfig(
            similarity_threshold=settings_obj.cache_similarity_threshold,
            response_ttl=settings_obj.cache_response_ttl,
            max_response_entries=settings_obj.cache_max_response_entries,
            log_cache_operations=settings_obj.cache_log_operations,
            adaptive_ttl=getattr(settings_obj, "cache_adaptive_ttl", True),
            adaptive_ttl_max_multiplier=getattr(settings_obj, "cache_adaptive_ttl_max_multiplier", 3.0),
            enabled=True,
        )
        instance._cache = get_cache_manager_fn(cache_config)
        logger_obj.info("[CRAG] Semantic cache enabled (threshold=%s)", cache_config.similarity_threshold)
    else:
        instance._cache = None
        logger_obj.info("[CRAG] Semantic cache disabled")

    logger_obj.info(
        "CorrectiveRAG initialized (max_iter=%s, threshold=%s)",
        max_iterations,
        grade_threshold,
    )


def calculate_confidence_impl(analysis, grading, verification) -> float:
    """Calculate overall confidence score on 0-100 scale."""
    scores = []
    if analysis:
        scores.append(analysis.confidence * 100)
    if grading:
        scores.append(grading.avg_score * 10)
    if verification:
        scores.append(verification.confidence)
    if not scores:
        return 70.0
    return sum(scores) / len(scores)
