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
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, AsyncGenerator

from app.engine.agentic_rag.query_analyzer import (
    QueryAnalysis, QueryComplexity, get_query_analyzer
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
from app.cache.cache_manager import get_cache_manager
from app.cache.models import CacheConfig
from app.core.config import settings
from app.core.constants import MAX_CONTENT_SNIPPET_LENGTH

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
            print(f"Warning: {result.verification_result.warning}")
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
        # SOTA: Use configurable settings, not hardcoded values
        self._max_iterations = max_iterations if max_iterations is not None else settings.rag_max_iterations
        # Convert normalized confidence (0-1) to grade scale (0-10)
        self._grade_threshold = grade_threshold if grade_threshold is not None else (settings.rag_confidence_high * 10)
        self._enable_verification = enable_verification if enable_verification is not None else settings.enable_answer_verification
        
        # ================================================================
        # COMPOSITION PATTERN: Self-contained RAG capability
        # ================================================================
        if rag_agent is not None:
            # Backward compatibility: Use provided rag_agent
            self._rag = rag_agent
            logger.info("[CRAG] Using provided RAG agent (legacy mode)")
        else:
            # SOTA: Use RAGAgent singleton (memory-efficient)
            # Reference: SOTA_DEEP_ROOT_CAUSE_ANALYSIS.md
            try:
                from app.engine.agentic_rag.rag_agent import get_rag_agent
                self._rag = get_rag_agent()  # ✓ Singleton = reuse LLM!
                logger.info("[CRAG] Using RAGAgent singleton (memory optimized)")
            except Exception as e:
                logger.error("[CRAG] Failed to get RAGAgent singleton: %s", e)
                self._rag = None
        
        # ================================================================
        # CRAG COMPONENTS (Query Analysis, Grading, Rewriting, Verification)
        # ================================================================
        self._analyzer = get_query_analyzer()
        self._grader = get_retrieval_grader()
        self._rewriter = get_query_rewriter()
        self._verifier = get_answer_verifier()
        
        # ================================================================
        # SEMANTIC CACHE (SOTA 2025 - RAG Latency Optimization)
        # ================================================================
        self._cache_enabled = settings.semantic_cache_enabled
        if self._cache_enabled:
            cache_config = CacheConfig(
                similarity_threshold=settings.cache_similarity_threshold,
                response_ttl=settings.cache_response_ttl,
                max_response_entries=settings.cache_max_response_entries,
                log_cache_operations=settings.cache_log_operations,
                adaptive_ttl=getattr(settings, 'cache_adaptive_ttl', True),
                adaptive_ttl_max_multiplier=getattr(settings, 'cache_adaptive_ttl_max_multiplier', 3.0),
                enabled=True
            )
            self._cache = get_cache_manager(cache_config)
            logger.info("[CRAG] Semantic cache enabled (threshold=%s)", cache_config.similarity_threshold)
        else:
            self._cache = None
            logger.info("[CRAG] Semantic cache disabled")
        
        logger.info("CorrectiveRAG initialized (max_iter=%s, threshold=%s)", max_iterations, grade_threshold)
    
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
        context = context or {}
        
        # Initialize reasoning tracer (Feature: reasoning-trace)
        tracer = get_reasoning_tracer()
        
        # ================================================================
        # SEMANTIC CACHE CHECK (SOTA 2025 - Cache-First Pattern)
        # ================================================================
        if self._cache_enabled and self._cache:
            try:
                # Get query embedding for semantic matching
                from app.engine.gemini_embedding import get_embeddings
                embeddings = get_embeddings()
                query_embedding = await embeddings.aembed_query(query)
                
                # Check cache (user-isolated — Sprint 121 RC-6, org-isolated — Sprint 160)
                _uid = context.get("user_id", "")
                # Sprint 160: Org-scoped cache key prefix
                _org = context.get("organization_id") or ""
                _cache_uid = f"{_org}:{_uid}" if _org else _uid
                cache_result = await self._cache.get(query, query_embedding, user_id=_cache_uid)
                
                if cache_result.hit:
                    logger.info(
                        "[CRAG] CACHE HIT! similarity=%.3f lookup_time=%.1fms",
                        cache_result.similarity, cache_result.lookup_time_ms,
                    )
                    
                    # ============================================================
                    # PHASE 2: Cache-Augmented Generation (SOTA 2025)
                    # Use ThinkingAdapter for natural, context-aware responses
                    # Instead of returning raw cache (anti-pattern)
                    # ============================================================
                    from app.engine.agentic_rag.thinking_adapter import get_thinking_adapter
                    from app.engine.agentic_rag.adaptive_router import get_adaptive_router
                    
                    # Get routing decision
                    router = get_adaptive_router()
                    routing = router.route(cache_result=cache_result)
                    
                    logger.info("[CRAG] Router: %s (%s)", routing.path.value, routing.reason)
                    
                    if routing.use_thinking_adapter:
                        # Adapt cached response with fresh thinking
                        adapter = get_thinking_adapter()
                        adapted = await adapter.adapt(
                            query=query,
                            cached_response=cache_result.value,
                            context=context,
                            similarity=cache_result.similarity
                        )
                        
                        logger.info(
                            "[CRAG] ThinkingAdapter: %.0fms (method=%s)",
                            adapted.adaptation_time_ms, adapted.adaptation_method,
                        )
                        
                        return CorrectiveRAGResult(
                            answer=adapted.answer,
                            sources=cache_result.value.get("sources", []),
                            iterations=0,
                            confidence=cache_result.value.get("confidence", 0.9),
                            reasoning_trace=None,
                            thinking=adapted.thinking,
                            thinking_content=f"[Cache-Augmented Generation]\n{adapted.thinking}"
                        )
                    else:
                        # Fallback for edge cases
                        cached_data = cache_result.value
                        return CorrectiveRAGResult(
                            answer=cached_data.get("answer", ""),
                            sources=cached_data.get("sources", []),
                            iterations=0,
                            confidence=cached_data.get("confidence", 0.9),
                            reasoning_trace=None,
                            thinking=cached_data.get("thinking"),
                            thinking_content="[Low similarity - fallback response]"
                        )
                else:
                    logger.debug("[CRAG] Cache MISS, proceeding with full pipeline")
                    
            except Exception as e:
                logger.warning("[CRAG] Cache lookup failed: %s, proceeding without cache", e)
                query_embedding = None  # Will regenerate if needed for storage
        else:
            query_embedding = None
        
        # Step 1: Analyze query
        tracer.start_step(StepNames.QUERY_ANALYSIS, "Phân tích độ phức tạp câu hỏi")
        logger.info("[CRAG] Step 1: Analyzing query: '%s...'", query[:50])
        analysis = await self._analyzer.analyze(query)
        logger.info("[CRAG] Analysis: %s", analysis)
        tracer.end_step(
            result=f"Độ phức tạp: {analysis.complexity.value}, Domain: {analysis.is_domain_related}",
            confidence=analysis.confidence,
            details={"complexity": analysis.complexity.value, "is_domain": analysis.is_domain_related, "topics": analysis.detected_topics}
        )
        
        # Step 2: Initial retrieval
        current_query = query
        documents = []
        grading_result = None
        was_rewritten = False
        rewritten_query = None
        iterations = 0
        
        for iteration in range(self._max_iterations):
            iterations = iteration + 1
            
            # Retrieval step
            tracer.start_step(StepNames.RETRIEVAL, f"Tìm kiếm tài liệu (lần {iterations})")
            logger.info("[CRAG] Step 2.%d: Retrieving for '%s...'", iterations, current_query[:50])
            
            # Retrieve documents
            documents = await self._retrieve(current_query, context)
            
            if not documents:
                logger.warning("[CRAG] No documents retrieved")
                tracer.end_step(result="Không tìm thấy tài liệu", confidence=0.0)
                
                if iteration < self._max_iterations - 1:
                    # Try rewriting
                    tracer.start_step(StepNames.QUERY_REWRITE, "Viết lại query do không có kết quả")
                    current_query = await self._rewriter.rewrite(
                        current_query, 
                        "No documents found"
                    )
                    rewritten_query = current_query
                    was_rewritten = True
                    tracer.end_step(result=f"Query mới: {current_query[:50]}...", confidence=0.7)
                    tracer.record_correction("Không tìm thấy tài liệu")
                    continue
                break
            else:
                tracer.end_step(
                    result=f"Tìm thấy {len(documents)} tài liệu",
                    confidence=0.8,
                    details={"doc_count": len(documents)}
                )
            
            # Step 3: Grade documents (PHASE 3: Tiered grading with fast-pass)
            tracer.start_step(StepNames.GRADING, "Đánh giá độ liên quan của tài liệu")
            logger.info("[CRAG] Step 3.%d: Grading %d documents", iterations, len(documents))
            
            # Ensure query_embedding for tiered grading
            if query_embedding is None:
                from app.engine.gemini_embedding import get_embeddings
                embeddings = get_embeddings()
                query_embedding = await embeddings.aembed_query(current_query)
            
            grading_result = await self._grader.grade_documents(
                current_query, documents, query_embedding=query_embedding
            )
            
            # SOTA: Normalize score to 0-1 confidence scale
            normalized_confidence = grading_result.avg_score / 10.0
            
            # Check if good enough (use configurable threshold)
            if grading_result.avg_score >= self._grade_threshold:
                logger.info(
                    "[CRAG] Grade passed: %.1f/10 (confidence=%.2f >= %.2f)",
                    grading_result.avg_score, normalized_confidence, settings.rag_confidence_high,
                )
                tracer.end_step(
                    result=f"Điểm: {grading_result.avg_score:.1f}/10 - ĐẠT",
                    confidence=normalized_confidence,
                    details={"score": grading_result.avg_score, "passed": True, "confidence": normalized_confidence}
                )
                break
            
            # SOTA: Early exit if medium confidence and early_exit enabled
            elif settings.rag_early_exit_on_high_confidence and normalized_confidence >= settings.rag_confidence_medium:
                logger.info(
                    "[CRAG] MEDIUM confidence (%.2f) - early exit enabled, proceeding to generation",
                    normalized_confidence,
                )
                tracer.end_step(
                    result=f"Điểm: {grading_result.avg_score:.1f}/10 - MEDIUM (early exit)",
                    confidence=normalized_confidence,
                    details={"score": grading_result.avg_score, "passed": False, "early_exit": True}
                )
                break
            
            else:
                tracer.end_step(
                    result=f"Điểm: {grading_result.avg_score:.1f}/10 - Cần cải thiện",
                    confidence=normalized_confidence,
                    details={"score": grading_result.avg_score, "passed": False}
                )
            
            # ================================================================
            # SOTA 2025: Early exit on relevant docs (LangGraph short-circuit)
            # ================================================================
            # Pattern: Trust the retriever. If we have ANY relevant doc, proceed
            # Log showed: "avg_score=4.6 relevant=2/7" → 2 docs were enough!
            # This saves ~40s by avoiding unnecessary rewrite + second iteration
            # ================================================================
            if grading_result.relevant_count >= 1:
                logger.info(
                    "[CRAG] SOTA: Found %d relevant docs, skipping rewrite (trust retriever pattern)",
                    grading_result.relevant_count,
                )
                break
            
            # Step 4: Rewrite ONLY if ZERO relevant docs found
            if iteration < self._max_iterations - 1:
                tracer.start_step(StepNames.QUERY_REWRITE, "Viết lại query để cải thiện kết quả")
                logger.info("[CRAG] Step 4.%d: Rewriting query (score=%.1f, 0 relevant docs)", iterations, grading_result.avg_score)
                
                if analysis.complexity == QueryComplexity.COMPLEX:
                    # Decompose complex queries
                    sub_queries = await self._rewriter.decompose(current_query)
                    if len(sub_queries) > 1:
                        # Use first sub-query
                        current_query = sub_queries[0]
                else:
                    current_query = await self._rewriter.rewrite(
                        current_query,
                        grading_result.feedback
                    )
                
                rewritten_query = current_query
                was_rewritten = True
                tracer.end_step(
                    result=f"Query mới: {current_query[:50]}...",
                    confidence=0.8
                )
                tracer.record_correction(f"Không tìm thấy doc liên quan (score={grading_result.avg_score:.1f}/10)")
        
        # Step 5: Generate answer
        tracer.start_step(StepNames.GENERATION, "Tạo câu trả lời từ context")
        logger.info("[CRAG] Step 5: Generating answer")
        # CHỈ THỊ SỐ 29: Unpack native_thinking from _generate()
        answer, sources, native_thinking = await self._generate(query, documents, context)

        # Sprint 64: Ensure answer is in Vietnamese
        if answer and self._is_likely_english(answer):
            logger.info("[CRAG] Answer is in English, translating to Vietnamese...")
            answer = await self._translate_to_vietnamese(answer)

        tracer.end_step(
            result=f"Tạo câu trả lời dựa trên {len(sources)} nguồn",
            confidence=0.85,
            details={"source_count": len(sources)}
        )
        
        # ====================================================================
        # PHASE 3: SELF-RAG REFLECTION ANALYSIS (SOTA 2025)
        # ====================================================================
        # Parse reflection signals from answer to determine quality
        # Reference: Self-RAG (Asai et al.), Meta CRAG
        # ====================================================================
        reflection_result = None
        if settings.rag_enable_reflection:
            from app.engine.agentic_rag.reflection_parser import get_reflection_parser
            
            reflection_parser = get_reflection_parser()
            reflection_result = reflection_parser.parse(answer)
            
            logger.info(
                "[CRAG] Reflection: supported=%s, useful=%s, needs_correction=%s, confidence=%s",
                reflection_result.is_supported, reflection_result.is_useful,
                reflection_result.needs_correction, reflection_result.confidence.value,
            )
            
            # If correction needed and we haven't exceeded iterations, log it
            if reflection_result.needs_correction and iterations < self._max_iterations:
                logger.warning(
                    "[CRAG] Reflection suggests correction: %s",
                    reflection_result.correction_reason,
                )
                tracer.record_correction(f"Reflection: {reflection_result.correction_reason}")
        
        # Step 6: Verify (optional)
        # SOTA 2025: Skip verification for MEDIUM+ confidence (saves ~19s)
        # Pattern: Anthropic Plan-Do-Check-Refine - only verify LOW confidence
        # Phase 2.3b: Also skip if reflection.confidence == HIGH
        verification_result = None
        grading_confidence = grading_result.avg_score / 10.0 if grading_result else 0.5
        
        # Phase 2.3b: Skip verification if reflection says confidence=high
        reflection_is_high = (
            reflection_result and 
            reflection_result.confidence.value == "high" and
            reflection_result.is_supported and
            not reflection_result.needs_correction
        )
        
        should_verify = (
            self._enable_verification and
            analysis.requires_verification and
            len(sources) > 0 and  # Sprint 103: Skip when no sources (fallback answer — nothing to verify against)
            grading_confidence < settings.rag_confidence_medium and  # Only verify LOW confidence
            not reflection_is_high  # Phase 2.3b: Trust high reflection confidence
        )
        
        if should_verify:
            tracer.start_step(StepNames.VERIFICATION, "Kiểm tra độ chính xác và hallucination")
            logger.info("[CRAG] Step 6: Verifying answer (low confidence=%.2f)", grading_confidence)
            verification_result = await self._verifier.verify(answer, sources)
            
            if verification_result.warning:
                answer = f"⚠️ {verification_result.warning}\n\n{answer}"
                tracer.end_step(
                    result=f"Cảnh báo: {verification_result.warning}",
                    confidence=verification_result.confidence / 100 if verification_result.confidence else 0.5
                )
            else:
                tracer.end_step(
                    result="Đã xác minh - Không phát hiện vấn đề",
                    confidence=verification_result.confidence / 100 if verification_result.confidence else 0.9
                )
        elif reflection_is_high:
            logger.info("[CRAG] Skipping verification (reflection.confidence=HIGH, supported=True)")
        elif self._enable_verification and len(sources) == 0:
            logger.info("[CRAG] Skipping verification (0 sources — fallback answer from LLM general knowledge)")
        elif self._enable_verification and grading_confidence >= settings.rag_confidence_medium:
            logger.info("[CRAG] Skipping verification (confidence=%.2f >= MEDIUM)", grading_confidence)
        
        # Calculate overall confidence
        confidence = self._calculate_confidence(
            analysis, grading_result, verification_result
        )
        
        # Build reasoning trace
        reasoning_trace = tracer.build_trace(final_confidence=confidence / 100)
        
        # CHỈ THỊ SỐ 29 v2: SOTA Native-First Thinking
        # SOTA Pattern (2025): Use native model thinking directly
        # - Claude: Extended Thinking blocks
        # - Qwen QwQ: <think> blocks  
        # - Gemini 2.5: include_thoughts=True
        # No dual LLM call needed - Gemini already provides thinking
        thinking = None
        thinking_content = None
        
        # Priority 1: Native Gemini thinking (SOTA - zero extra latency)
        if native_thinking:
            thinking = native_thinking
            logger.info("[CRAG] Using native Gemini thinking: %d chars", len(thinking))
        
        # Priority 2: Structured summary (fallback when native unavailable)
        thinking_content = tracer.build_thinking_summary()
        if thinking_content:
            logger.info("[CRAG] Built structured thinking summary: %d chars", len(thinking_content))
        
        # Sprint 140b ROOT CAUSE FIX: Do NOT fall back to thinking_content.
        # thinking_content is a ReasoningTracer pipeline dump (internal debug)
        # that was cascading through rag_tools→tutor→graph_streaming→SSE as
        # "AI thinking".  When native thinking is unavailable, thinking stays
        # empty — this correctly results in no thinking block on the frontend.
        # thinking_content is still returned separately for reasoning_trace metadata.
        if not thinking:
            logger.info("[CRAG] No native thinking available — thinking_content kept separate for metadata only")
        
        logger.info("[CRAG] Complete: iterations=%d, confidence=%.0f%%", iterations, confidence)
        
        # ================================================================
        # CACHE STORAGE (SOTA 2025 - Store for future hits)
        # ================================================================
        # Sprint 27 FIX: confidence is 0-100 scale, was comparing against 0.7 (always true)
        if self._cache_enabled and self._cache and confidence >= 70:
            try:
                # Get embedding if not already computed
                if query_embedding is None:
                    from app.engine.gemini_embedding import get_embeddings
                    embeddings = get_embeddings()
                    query_embedding = await embeddings.aembed_query(query)
                
                # Extract document IDs for cache invalidation
                doc_ids = [s.get("document_id", "") for s in sources if s.get("document_id")]
                
                # Store in cache
                cache_data = {
                    "answer": answer,
                    "sources": sources,
                    "confidence": confidence,
                    "thinking": thinking
                }
                # Sprint 160: Org-scoped cache key
                _cache_org = context.get("organization_id") or ""
                _cache_uid = context.get("user_id", "")
                _cache_user = f"{_cache_org}:{_cache_uid}" if _cache_org else _cache_uid
                await self._cache.set(
                    query=query,
                    embedding=query_embedding,
                    response=cache_data,
                    document_ids=doc_ids,
                    metadata={"iterations": iterations, "was_rewritten": was_rewritten},
                    user_id=_cache_user,
                )
                logger.info("[CRAG] Response cached (confidence=%.0f%%, docs=%d)", confidence, len(doc_ids))
                
            except Exception as e:
                logger.warning("[CRAG] Failed to cache response: %s", e)
        
        return CorrectiveRAGResult(
            answer=answer,
            sources=sources,
            query_analysis=analysis,
            grading_result=grading_result,
            verification_result=verification_result,
            was_rewritten=was_rewritten,
            rewritten_query=rewritten_query,
            iterations=iterations,
            confidence=confidence,
            reasoning_trace=reasoning_trace,
            thinking_content=thinking_content,  # Structured summary (legacy)
            thinking=thinking  # CHỈ THỊ SỐ 29: Natural thinking
        )
    
    async def _retrieve(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents for grading using HybridSearchService directly.
        
        SOTA Pattern (2024-2025): CRAG grading requires FULL document content.
        
        Previous implementation used RAGAgent.query() → Citation → lost content.
        Now uses HybridSearchService.search() → HybridSearchResult → full content.
        
        Reference: LangChain CRAG grading requires knowledge strips (full chunks).
        """
        if not self._rag:
            logger.warning("[CRAG] No RAG agent available")
            return []
        
        try:
            # ================================================================
            # SOTA FIX: Use HybridSearchService directly for full content
            # ================================================================
            # Access HybridSearchService from RAGAgent
            hybrid_search = getattr(self._rag, '_hybrid_search', None)
            
            if hybrid_search and hybrid_search.is_available():
                # Direct hybrid search - returns HybridSearchResult with content
                # Sprint 160: Pass org_id for multi-tenant isolation
                _org_id = context.get("organization_id")
                results = await hybrid_search.search(
                    query=query,
                    limit=10,
                    org_id=_org_id
                )
                
                # Convert to grading format WITH full content
                documents = []
                for r in results:
                    doc = {
                        "node_id": r.node_id,
                        "content": r.content,  # ✅ FULL CONTENT for grading!
                        "title": r.title,
                        "score": r.rrf_score,
                        # Source highlighting fields
                        "image_url": r.image_url,
                        "page_number": r.page_number if hasattr(r, 'page_number') else None,
                        "document_id": r.document_id if hasattr(r, 'document_id') else None,
                        "bounding_boxes": r.bounding_boxes if hasattr(r, 'bounding_boxes') else None,
                    }
                    documents.append(doc)
                
                logger.info("[CRAG] Retrieved %d documents via HybridSearchService (SOTA)", len(documents))
                return documents
            
            # Fallback: Use RAGAgent.query() if HybridSearch unavailable
            logger.warning("[CRAG] HybridSearch unavailable, falling back to RAGAgent")
            user_role = context.get("user_role", "student")
            history = context.get("conversation_history", "")
            
            response = await self._rag.query(
                question=query,
                limit=10,
                conversation_history=history,
                user_role=user_role
            )
            
            # Convert RAGResponse.citations - use title as content (best effort)
            documents = []
            for citation in response.citations:
                doc = {
                    "node_id": getattr(citation, 'node_id', ''),
                    "content": getattr(citation, 'title', ''),  # Use title (has actual text)
                    "title": getattr(citation, 'title', 'Unknown'),
                    "score": getattr(citation, 'relevance_score', 0),
                    "image_url": getattr(citation, 'image_url', None),
                    "page_number": getattr(citation, 'page_number', None),
                    "document_id": getattr(citation, 'document_id', None),
                    "bounding_boxes": getattr(citation, 'bounding_boxes', None),
                }
                documents.append(doc)
            
            logger.info("[CRAG] Retrieved %d documents via RAGAgent (fallback)", len(documents))
            return documents
            
        except Exception as e:
            logger.error("[CRAG] RAGAgent retrieval failed: %s", e)
            return []

    
    @staticmethod
    def _is_likely_english(text: str) -> bool:
        """Detect if text is primarily English (lacks Vietnamese diacritics)."""
        if not text or len(text) < 30:
            return False
        vn_diacritics = set(
            "àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợ"
            "ùúủũụưứừửữựỳýỷỹỵđÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆ"
            "ÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ"
        )
        vn_count = sum(1 for c in text if c in vn_diacritics)
        return vn_count / max(len(text), 1) < 0.01

    async def _translate_to_vietnamese(self, text: str) -> str:
        """Translate English text to Vietnamese using LLM light."""
        try:
            from app.engine.llm_pool import get_llm_light
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = get_llm_light()
            if not llm:
                return text

            messages = [
                SystemMessage(content=(
                    "Dịch đoạn văn sau sang tiếng Việt tự nhiên, chính xác. "
                    "Giữ nguyên thuật ngữ chuyên ngành hàng hải/giao thông bằng tiếng Anh "
                    "nếu cần (ví dụ: COLREGs, SOLAS, starboard). "
                    "CHỈ trả lời bản dịch tiếng Việt, KHÔNG thêm giải thích hay ghi chú. "
                    "KHÔNG bao gồm quá trình suy nghĩ."
                )),
                HumanMessage(content=text),
            ]
            response = await llm.ainvoke(messages)

            from app.services.output_processor import extract_thinking_from_response
            translated, _ = extract_thinking_from_response(response.content)
            result = translated.strip()
            if result and len(result) > 20:
                logger.info("[CRAG] Translated fallback to Vietnamese: %d chars", len(result))
                return result
            return text
        except Exception as e:
            logger.warning("[CRAG] Translation failed, using original: %s", e)
            return text

    async def _generate_fallback(
        self,
        query: str,
        context: Dict[str, Any],
    ) -> str:
        """Generate a response using LLM general knowledge when RAG finds 0 documents.

        Instead of returning a static "Không tìm thấy" error, this asks the LLM
        to answer based on its training data while being transparent about the
        lack of database sources.

        If the LLM responds in English, an additional translation step converts
        the response to Vietnamese before returning to the user.
        """
        try:
            from app.engine.llm_pool import get_llm_light
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = get_llm_light()
            if not llm:
                return "Xin lỗi, tôi không tìm thấy thông tin trong cơ sở dữ liệu."

            from app.core.config import settings
            # Sprint 80: Extract domain name for off-topic boundary
            domain_name = context.get("domain_name", "")
            if not domain_name:
                domain_name = context.get("domain_config", {}).get("domain_name", "")
            if not domain_name:
                domain_name = getattr(settings, "default_domain", "maritime")
                # Map domain ID to Vietnamese display name
                domain_display = {
                    "maritime": "Hàng hải",
                    "traffic_law": "Luật Giao thông",
                }.get(domain_name, domain_name)
                domain_name = domain_display

            # Sprint 89: Inject identity from wiii_identity.yaml for persona consistency
            from app.prompts.prompt_loader import get_prompt_loader
            loader = get_prompt_loader()
            identity = loader.get_identity().get("identity", {})
            personality = identity.get("personality", {}).get("summary", "")
            emoji_usage = identity.get("voice", {}).get("emoji_usage", "")
            user_name = context.get("user_name", "")
            name_hint = f"User tên {user_name}. " if user_name else ""

            # Sprint 101: Inject avoid rules to prevent pet name confusion
            avoid_rules = identity.get("response_style", {}).get("avoid", [])
            avoid_text = " ".join(f"Tránh: {r}." for r in avoid_rules) if avoid_rules else ""

            messages = [
                SystemMessage(content=(
                    f"Bạn là {settings.app_name}. {personality} "
                    f"{name_hint}"
                    f"{avoid_text} "
                    f"Chuyên ngành: {domain_name}. "
                    "Cơ sở dữ liệu không có tài liệu phù hợp cho câu hỏi này. "
                    f"CHỈ trả lời nếu câu hỏi THỰC SỰ liên quan đến {domain_name}. "
                    f"Nếu câu hỏi KHÔNG liên quan đến {domain_name} (ví dụ: nấu ăn, "
                    "giải trí, thời tiết, lập trình, v.v.), hãy lịch sự từ chối: "
                    f"'Mình là trợ lý chuyên về {domain_name}. "
                    f"Bạn có muốn hỏi về {domain_name} không?' "
                    "Nếu là lời chào, hãy chào lại tự nhiên. "
                    f"Nếu là câu hỏi liên quan {domain_name}, trả lời ngắn gọn và lưu ý "
                    "rằng đây là kiến thức tổng quát (chưa được xác minh từ tài liệu gốc). "
                    f"{emoji_usage} "
                    "BẮT BUỘC: Trả lời hoàn toàn bằng TIẾNG VIỆT. "
                    "TUYỆT ĐỐI KHÔNG trả lời bằng tiếng Anh. "
                    "QUAN TRỌNG: CHỈ trả lời nội dung, KHÔNG bao gồm quá trình suy nghĩ, "
                    "phân tích hay reasoning. Đi thẳng vào câu trả lời."
                )),
                HumanMessage(content=query),
            ]
            response = await llm.ainvoke(messages)

            from app.services.output_processor import extract_thinking_from_response
            text, _ = extract_thinking_from_response(response.content)
            text = text.strip()

            # Sprint 64: If LLM still responds in English, translate to Vietnamese
            if text and self._is_likely_english(text):
                logger.info("[CRAG] Fallback response is English, translating to Vietnamese...")
                text = await self._translate_to_vietnamese(text)

            return text

        except Exception as e:
            logger.warning("[CRAG] Fallback generation failed: %s", e)
            return "Xin lỗi, tôi không tìm thấy thông tin trong cơ sở dữ liệu."

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
        if not self._rag:
            return "Không thể tạo câu trả lời do thiếu cấu hình.", documents, None

        if not documents:
            # Fall back to LLM general knowledge instead of static error
            return await self._generate_fallback(query, context), [], None

        try:
            user_role = context.get("user_role", "student")
            history = context.get("conversation_history", "")
            # Sprint 89: Extract user_name and is_follow_up for persona consistency
            user_name = context.get("user_name")
            is_follow_up = context.get("is_follow_up", bool(history))

            # REFACTOR-005: Use generate_from_documents() instead of query()
            # This avoids duplicate retrieval since documents are already graded
            response = await self._rag.generate_from_documents(
                question=query,
                documents=documents,
                conversation_history=history,
                user_role=user_role,
                user_name=user_name,
                is_follow_up=is_follow_up
            )

            # CHỈ THỊ SỐ 29: Capture native_thinking from RAGResponse
            native_thinking = response.native_thinking
            if native_thinking:
                logger.info("[CRAG] Native thinking from Gemini: %d chars", len(native_thinking))

            return response.content, documents, native_thinking

        except Exception as e:
            logger.error("[CRAG] Generation failed: %s", e)
            return f"Lỗi khi tạo câu trả lời: {e}", documents, None
    
    # =========================================================================
    # V3 SOTA: Full CRAG Pipeline + True Token Streaming
    # Pattern: OpenAI Responses API + Claude Extended Thinking + Gemini astream
    # Reference: P3+ Implementation Plan (Dec 2025)
    # =========================================================================
    async def process_streaming(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        SOTA 2025: Full CRAG pipeline with progressive SSE events.
        
        Yields SSE events at each pipeline stage:
        - status: Processing stage updates (shown as typing indicator)
        - thinking: AI reasoning steps (shown in collapsible section)  
        - answer: Response tokens (streamed real-time via LLM.astream())
        - sources: Citation list with image_url for PDF highlighting
        - metadata: reasoning_trace, confidence, timing
        - done: Stream complete
        
        Pattern:
        - OpenAI Responses API (event types: reasoning, output, completion)
        - Claude Interleaved Thinking (thinking blocks between steps)
        - LangChain LCEL RunnableParallel (parallel execution)
        
        **Feature: p3-v3-full-crag-streaming**
        """
        import time
        # Note: get_reasoning_tracer and StepNames already imported at module level (line 37-39)
        
        context = context or {}
        start_time = time.time()
        tracer = get_reasoning_tracer()
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1: Query Understanding (emit events immediately)
        # ═══════════════════════════════════════════════════════════════════
        yield {"type": "status", "content": "Phân tích câu hỏi"}
        
        tracer.start_step(StepNames.QUERY_ANALYSIS, "Phân tích độ phức tạp câu hỏi")
        logger.info("[CRAG-V3] Phase 1: Analyzing query: '%s...'", query[:50])
        
        try:
            analysis = await self._analyzer.analyze(query)
            tracer.end_step(
                result=f"Độ phức tạp: {analysis.complexity.value}, Domain: {analysis.is_domain_related}",
                confidence=analysis.confidence,
                details={"complexity": analysis.complexity.value, "is_domain": analysis.is_domain_related}
            )
            
            # Sprint 144: Rich analysis thinking — expert-level breakdown
            _analysis_parts = [f"Độ phức tạp: {analysis.complexity.value}"]
            if analysis.detected_topics:
                _analysis_parts.append(f"Chủ đề: {', '.join(analysis.detected_topics[:5])}")
            if analysis.is_domain_related:
                _analysis_parts.append("Thuộc lĩnh vực chuyên ngành → Sử dụng Knowledge Base")
            else:
                _analysis_parts.append("Ngoài chuyên ngành → Sử dụng kiến thức chung LLM")
            if hasattr(analysis, 'confidence') and analysis.confidence:
                _analysis_parts.append(f"Độ tin cậy phân tích: {analysis.confidence:.0%}")
            yield {
                "type": "thinking",
                "content": "\n".join(_analysis_parts),
                "step": "analysis",
                "details": {"topics": analysis.detected_topics, "is_domain": analysis.is_domain_related}
            }
        except Exception as e:
            logger.error("[CRAG-V3] Analysis failed: %s", e)
            yield {"type": "error", "content": f"Lỗi phân tích: {e}"}
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2: Retrieval (hybrid search + optional graphrag)
        # ═══════════════════════════════════════════════════════════════════
        yield {"type": "status", "content": "Tìm kiếm tài liệu"}
        
        tracer.start_step(StepNames.RETRIEVAL, "Tìm kiếm tài liệu")
        logger.info("[CRAG-V3] Phase 2: Retrieving documents")
        
        try:
            documents = await self._retrieve(query, context)
            tracer.end_step(
                result=f"Tìm thấy {len(documents)} tài liệu",
                confidence=0.8 if documents else 0.3,
                details={"doc_count": len(documents)}
            )
            
            # Sprint 144: Rich retrieval thinking — document list with titles
            _retrieval_parts = [f"Tìm thấy {len(documents)} tài liệu liên quan"]
            for i, doc in enumerate(documents[:5]):  # Top 5
                _doc_title = doc.get("title", "").strip() or f"Tài liệu {i+1}"
                _doc_score = doc.get("score") or doc.get("relevance_score")
                if _doc_score is not None:
                    _retrieval_parts.append(f"  {i+1}. {_doc_title} (điểm: {_doc_score:.2f})")
                else:
                    _retrieval_parts.append(f"  {i+1}. {_doc_title}")
            if len(documents) > 5:
                _retrieval_parts.append(f"  ... và {len(documents) - 5} tài liệu khác")
            yield {
                "type": "thinking",
                "content": "\n".join(_retrieval_parts),
                "step": "retrieval",
                "details": {"doc_count": len(documents)}
            }
            
            if not documents:
                no_doc_answer = "Không tìm thấy thông tin phù hợp trong cơ sở dữ liệu."
                yield {"type": "answer", "content": no_doc_answer}
                yield {"type": "result", "data": CorrectiveRAGResult(
                    answer=no_doc_answer,
                    sources=[],
                    query_analysis=analysis,
                    confidence=30.0,
                )}
                yield {"type": "done", "content": ""}
                return
                
        except Exception as e:
            logger.error("[CRAG-V3] Retrieval failed: %s", e)
            yield {"type": "error", "content": f"Lỗi tìm kiếm: {e}"}
            return
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3: Grading (CRAG core - quality control!)  
        # ═══════════════════════════════════════════════════════════════════
        yield {"type": "status", "content": "Đánh giá chất lượng tài liệu"}
        
        tracer.start_step(StepNames.GRADING, "Đánh giá độ liên quan của tài liệu")
        logger.info("[CRAG-V3] Phase 3: Grading documents")
        
        try:
            # FIXED: Use grade_documents (not grade_batch)
            grading_result = await self._grader.grade_documents(query, documents)
            passed = grading_result.avg_score >= self._grade_threshold
            grading_confidence = grading_result.relevant_count / len(documents) if documents else 0.5
            
            tracer.end_step(
                result=f"Điểm: {grading_result.avg_score:.1f}/10 - {'ĐẠT' if passed else 'CHƯA ĐẠT'}",
                confidence=grading_confidence,
                details={
                    "score": grading_result.avg_score,
                    "passed": passed,
                    "relevant_count": grading_result.relevant_count
                }
            )
            
            # Sprint 144: Rich grading thinking — expert quality assessment
            _grade_icon = "✅" if passed else "⚠️"
            _grade_parts = [
                f"{_grade_icon} Điểm chất lượng: {grading_result.avg_score:.1f}/10 — {'ĐẠT' if passed else 'CHƯA ĐẠT'}",
                f"Tài liệu liên quan: {grading_result.relevant_count}/{len(documents)}",
            ]
            _threshold = getattr(self, '_grade_threshold', 6.0)
            if not passed:
                _grade_parts.append(f"Ngưỡng yêu cầu: {_threshold}/10 → Cần tinh chỉnh câu hỏi")
            else:
                _grade_parts.append(f"Vượt ngưỡng {_threshold}/10 → Đủ chất lượng để tạo câu trả lời")
            yield {
                "type": "thinking",
                "content": "\n".join(_grade_parts),
                "step": "grading",
                "details": {"score": grading_result.avg_score, "passed": passed}
            }
            
        except Exception as e:
            logger.error("[CRAG-V3] Grading failed: %s", e)
            yield {"type": "thinking", "content": f"⚠️ Bỏ qua đánh giá: {e}", "step": "grading"}
            grading_result = None
            passed = True  # Continue without grading
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 4: Query Rewrite (if grading failed)
        # ═══════════════════════════════════════════════════════════════════
        rewritten_query = None
        if grading_result and not passed and self._rewriter:
            yield {"type": "status", "content": "Tinh chỉnh câu hỏi"}
            
            try:
                rewrite_result = await self._rewriter.rewrite(query)
                if rewrite_result.rewritten_query != query:
                    rewritten_query = rewrite_result.rewritten_query
                    logger.info("[CRAG-V3] Query rewritten: %s...", rewritten_query[:50])
                    
                    yield {
                        "type": "thinking",
                        "content": f"Tinh chỉnh câu hỏi để tìm kiếm chính xác hơn\nCâu gốc: {query[:80]}\nCâu mới: {rewritten_query[:80]}",
                        "step": "rewrite"
                    }
                    
                    # Re-retrieve with rewritten query
                    documents = await self._retrieve(rewritten_query, context)
                    
            except Exception as e:
                logger.warning("[CRAG-V3] Rewrite failed: %s", e)
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 5: Generation (TRUE streaming via astream!)
        # ═══════════════════════════════════════════════════════════════════
        yield {"type": "status", "content": "Tạo câu trả lời"}
        
        tracer.start_step(StepNames.GENERATION, "Tạo câu trả lời từ context")
        logger.info("[CRAG-V3] Phase 5: Generating response with streaming")
        
        gen_start_time = time.time()
        
        full_answer_parts = []  # Sprint 144: Accumulate answer tokens for result

        if not self._rag:
            yield {"type": "answer", "content": "Không thể tạo câu trả lời do thiếu cấu hình."}
            yield {"type": "done", "content": ""}
            return

        try:
            # Build context from documents
            context_parts = []
            sources_data = []
            
            for doc in documents:
                content = doc.get("content", "")
                title = doc.get("title", "Unknown")
                if content:
                    context_parts.append(f"[{title}]: {content}")
                
                # Prepare source data for later
                sources_data.append({
                    "title": title,
                    "content": content[:MAX_CONTENT_SNIPPET_LENGTH] if content else "",
                    "page_number": doc.get("page_number"),
                    "image_url": doc.get("image_url"),
                    "document_id": doc.get("document_id"),
                    "bounding_boxes": doc.get("bounding_boxes")
                })
            
            # Get user context
            user_context = context  # The dict passed to process_streaming
            user_role = user_context.get("user_role", "student")
            history = user_context.get("conversation_history", "")
            
            # SOTA PATTERN: Defensive defaults for data quality issues
            # Following OpenAI/Anthropic pattern - graceful degradation, never crash
            from app.models.knowledge_graph import KnowledgeNode, NodeType
            
            knowledge_nodes = []
            for i, doc in enumerate(documents):
                # CRITICAL: Use 'or' operator to handle empty strings
                # doc.get("title", "X") returns '' if title is empty string
                # doc.get("title") or "X" returns "X" if title is empty/None
                node = KnowledgeNode(
                    id=doc.get("node_id") or f"doc_{i}",
                    node_type=NodeType.REGULATION,
                    content=doc.get("content") or "No content",
                    title=doc.get("title") or f"Document {i+1}",
                    source=doc.get("document_id") or ""
                )
                knowledge_nodes.append(node)
            
            # Sprint 144: Intermediate response — user sees activity before LLM generation
            yield {
                "type": "answer",
                "content": f"Wiii tìm thấy {len(documents)} tài liệu liên quan, đang phân tích để trả lời...\n\n"
            }

            # Stream tokens from RAGAgent
            # FIXED: Removed invalid 'context' param, pass nodes correctly
            token_count = 0
            async for chunk in self._rag._generate_response_streaming(
                question=rewritten_query or query,
                nodes=knowledge_nodes,
                conversation_history=history,
                user_role=user_role,
                entity_context=""
            ):
                token_count += 1
                full_answer_parts.append(chunk)
                yield {"type": "answer", "content": chunk}
            
            gen_duration = (time.time() - gen_start_time) * 1000
            tracer.end_step(
                result=f"Tạo câu trả lời: {token_count} tokens",
                confidence=0.85,
                details={"token_count": token_count, "duration_ms": gen_duration}
            )
            
            logger.info("[CRAG-V3] Generation complete: %d tokens in %.0fms", token_count, gen_duration)
            
        except Exception as e:
            logger.error("[CRAG-V3] Generation failed: %s", e)
            yield {"type": "answer", "content": f"Lỗi khi tạo câu trả lời: {e}"}
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 6: Finalize (sources + metadata)
        # ═══════════════════════════════════════════════════════════════════
        total_time = time.time() - start_time
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            analysis, 
            grading_result, 
            None  # No verification in streaming mode
        )
        
        # Build reasoning trace
        reasoning_trace = tracer.build_trace(final_confidence=confidence / 100)
        
        # Emit sources
        yield {
            "type": "sources",
            "content": sources_data
        }
        
        # Emit metadata with reasoning_trace
        # FIX: ReasoningTrace is Pydantic BaseModel, use model_dump() (v2) or dict() (v1)
        reasoning_dict = None
        if reasoning_trace:
            try:
                # Pydantic v2: model_dump()
                reasoning_dict = reasoning_trace.model_dump()
            except AttributeError:
                # Pydantic v1 fallback: dict()
                reasoning_dict = reasoning_trace.dict()
        
        yield {
            "type": "metadata", 
            "content": {
                "reasoning_trace": reasoning_dict,
                "processing_time": total_time,
                "confidence": confidence,
                "model": settings.rag_model_version,
                "was_rewritten": rewritten_query is not None,
                "doc_count": len(documents)
            }
        }
        
        # Sprint 144: Yield CorrectiveRAGResult for rag_node to capture
        full_answer = "".join(full_answer_parts)
        yield {
            "type": "result",
            "data": CorrectiveRAGResult(
                answer=full_answer,
                sources=sources_data,
                query_analysis=analysis,
                grading_result=grading_result,
                was_rewritten=rewritten_query is not None,
                rewritten_query=rewritten_query,
                confidence=confidence,
                reasoning_trace=reasoning_trace,
            )
        }

        yield {"type": "done", "content": ""}

        logger.info("[CRAG-V3] Complete: %.2fs, confidence=%.0f%%", total_time, confidence)
    
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
        scores = []
        
        if analysis:
            scores.append(analysis.confidence * 100)
        
        if grading:
            scores.append(grading.avg_score * 10)  # Scale to 0-100
        
        if verification:
            scores.append(verification.confidence)
        
        if not scores:
            return 70.0  # Default
        
        return sum(scores) / len(scores)
    
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
