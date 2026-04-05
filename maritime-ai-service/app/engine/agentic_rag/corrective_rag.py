"""
Corrective RAG - Phase 7.5

Main orchestrator for Agentic RAG with self-correction.

Flow:
1. Analyze query complexity
2. Retrieve documents
3. Grade relevance
4. Rewrite query if needed (self-correction)
5. Generate answer
6. Verify answer (hallucination check)

Features:
- Multi-step retrieval for complex queries
- Self-correction loop
- Hallucination prevention
- Confidence scoring
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator

from app.engine.agentic_rag.query_analyzer import (
    QueryAnalysis, get_query_analyzer
)
from app.engine.agentic_rag.retrieval_grader import (
    GradingResult, get_retrieval_grader
)
from app.engine.agentic_rag.query_rewriter import (
    get_query_rewriter
)
from app.engine.agentic_rag.answer_verifier import (
    VerificationResult, get_answer_verifier
)
from app.engine.reasoning_tracer import (
    StepNames, get_reasoning_tracer
)
# CHỈ THỊ SỐ 29 v2: SOTA Native-First Thinking (no ThinkingGenerator needed)
# Pattern: Use Gemini's native thinking directly (aligns with Claude/Qwen/Gemini 2025)
from app.models.schemas import ReasoningTrace

# =============================================================================
# SEMANTIC CACHE (SOTA 2025 - RAG Latency Optimization)
# =============================================================================
from app.core.config import settings
from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH
from app.engine.agentic_rag.corrective_rag_generation import (
    generate_answer_impl,
    generate_fallback_impl,
)
from app.engine.agentic_rag.corrective_rag_retrieval_runtime import (
    retrieve_impl,
)
from app.engine.agentic_rag.corrective_rag_process_runtime import (
    process_impl,
)
from app.engine.agentic_rag.corrective_rag_stream_runtime import (
    process_streaming_impl,
)
from app.engine.agentic_rag.corrective_rag_setup import (
    calculate_confidence_impl,
    initialize_corrective_rag_impl,
)
from app.engine.agentic_rag.corrective_rag_surface import (
    build_house_fallback_reply,
    build_retrieval_surface_text,
    is_no_doc_retrieval_text,
    normalize_visible_text,
)

logger = logging.getLogger(__name__)



@dataclass
class CorrectiveRAGResult:
    """Result from Corrective RAG processing.

    NOTE: confidence is on 0-100 scale (matching LLM prompt and _calculate_confidence).
    Normalized to 0-1 at boundaries (rag_tools.py, reasoning trace).
    """
    answer: str
    sources: List[Dict[str, Any]]
    query_analysis: Optional[QueryAnalysis] = None
    grading_result: Optional[GradingResult] = None
    verification_result: Optional[VerificationResult] = None
    was_rewritten: bool = False
    rewritten_query: Optional[str] = None
    iterations: int = 1
    confidence: float = 80.0  # 0-100 scale (Sprint 83: was 0.8, fixed to match actual scale)
    reasoning_trace: Optional[ReasoningTrace] = None  # Feature: reasoning-trace
    thinking_content: Optional[str] = None  # Legacy: structured summary (fallback)
    thinking: Optional[str] = None  # CHỈ THỊ SỐ 29: Natural Vietnamese thinking
    evidence_images: List[Dict[str, Any]] = field(default_factory=list)  # Sprint 189b

    @property
    def has_warning(self) -> bool:
        """Check if result needs a warning. Confidence is 0-100 scale."""
        if self.verification_result:
            return self.verification_result.needs_warning
        return self.confidence < 70  # 0-100 scale threshold


class CorrectiveRAG:
    """
    Corrective RAG with self-correction loop.
    
    Usage:
        crag = CorrectiveRAG(rag_agent)
        result = await crag.process("What is Rule 15?", context)
        if result.has_warning:
            logger.warning("Verification warning: %s", result.verification_result.warning)
    """
    
    def __init__(
        self,
        rag_agent=None,
        max_iterations: int = None,
        grade_threshold: float = None,
        enable_verification: bool = None
    ):
        """
        Initialize Corrective RAG.
        
        SOTA Pattern (Dec 2025): Self-Reflective Agentic RAG
        - Confidence-based smart iteration, not hardcoded loops
        - Uses configurable settings from settings.rag_* 
        - Reference: Self-RAG (Asai et al.), Meta CRAG (ICLR 2025)
        
        This follows LangGraph CRAG architecture where nodes are self-contained
        and compose their own dependencies rather than relying on DI.
        
        Args:
            rag_agent: (Deprecated) External RAG agent. If None, auto-creates one.
            max_iterations: Maximum rewrite iterations (default from settings)
            grade_threshold: Minimum grade to accept retrieval (default from settings)
            enable_verification: Whether to verify answers against sources
        """
        initialize_corrective_rag_impl(
            self,
            rag_agent,
            max_iterations,
            grade_threshold,
            enable_verification,
            logger,
            settings_obj=settings,
            get_query_analyzer_fn=get_query_analyzer,
            get_retrieval_grader_fn=get_retrieval_grader,
            get_query_rewriter_fn=get_query_rewriter,
            get_answer_verifier_fn=get_answer_verifier,
        )
    
    async def process(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> CorrectiveRAGResult:
        """
        Process query through Corrective RAG pipeline.
        
        Args:
            query: User query
            context: Additional context (user_id, session_id, etc.)
            
        Returns:
            CorrectiveRAGResult with answer and metadata
        
        **Feature: reasoning-trace**
        """
        # Source-inspection anchor preserved for isolation hardening tests:
        # cache calls in the runtime path still pass org_id=_org separately.
        return await process_impl(
            self,
            query,
            context,
            settings_obj=settings,
            result_cls=CorrectiveRAGResult,
            get_reasoning_tracer_fn=get_reasoning_tracer,
            step_names_cls=StepNames,
        )
    
    async def _retrieve(
        self,
        query: str,
        context: Dict[str, Any],
        query_embedding_override: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve documents for grading while preserving full chunk content."""
        return await retrieve_impl(
            self,
            query=query,
            context=context,
            query_embedding_override=query_embedding_override,
            logger=logger,
        )

    
    async def _generate_fallback(
        self,
        query: str,
        context: Dict[str, Any],
    ) -> str:
        """Generate a response using model general knowledge when RAG has 0 docs."""
        return await generate_fallback_impl(
            query=query,
            context=context,
            settings_obj=settings,
        )

    async def _generate(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        """
        Generate answer from graded documents using RAGAgent.

        REFACTOR-005: Now uses generate_from_documents() to avoid duplicate retrieval.
        Documents have already been retrieved and graded, so we generate directly
        from them instead of re-querying (saves ~40-60ms).

        CHỈ THỊ SỐ 29: Now returns native_thinking from Gemini for hybrid display.

        Returns:
            Tuple of (answer, documents, native_thinking)
        """
        return await generate_answer_impl(
            rag_agent=self._rag,
            query=query,
            documents=documents,
            context=context,
            generate_fallback=self._generate_fallback,
        )
    
    # =========================================================================
    # V3 SOTA: Full CRAG Pipeline + True Token Streaming
    async def process_streaming(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        SOTA 2025: Full CRAG pipeline with progressive SSE events.

        The heavy streaming implementation lives in a dedicated runtime module so
        this class stays focused on public API and dependency ownership.
        """
        async for event in process_streaming_impl(
            self,
            query,
            context,
            result_cls=CorrectiveRAGResult,
            get_reasoning_tracer_fn=get_reasoning_tracer,
            settings_obj=settings,
            step_names_cls=StepNames,
            build_retrieval_surface_text_fn=build_retrieval_surface_text,
            build_house_fallback_reply_fn=build_house_fallback_reply,
            is_no_doc_retrieval_text_fn=is_no_doc_retrieval_text,
            normalize_visible_text_fn=normalize_visible_text,
            max_content_snippet_length=MAX_CONTENT_SNIPPET_LENGTH,
        ):
            yield event
    
    def _calculate_confidence(
        self,
        analysis: Optional[QueryAnalysis],
        grading: Optional[GradingResult],
        verification: Optional[VerificationResult]
    ) -> float:
        """Calculate overall confidence score on 0-100 scale.

        All inputs are normalized to 0-100 before averaging:
        - analysis.confidence: 0-1 → *100
        - grading.avg_score: 0-10 → *10
        - verification.confidence: already 0-100 (from LLM prompt)
        """
        return calculate_confidence_impl(analysis, grading, verification)
    
    def is_available(self) -> bool:
        """Check if all components are available."""
        return (
            self._analyzer.is_available() and
            self._grader.is_available()
        )


# Singleton
_corrective_rag: Optional[CorrectiveRAG] = None

def get_corrective_rag(rag_agent=None) -> CorrectiveRAG:
    """Get or create CorrectiveRAG singleton."""
    global _corrective_rag
    if _corrective_rag is None:
        _corrective_rag = CorrectiveRAG(rag_agent=rag_agent)
    return _corrective_rag
