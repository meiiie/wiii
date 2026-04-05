"""
Retrieval Grader - Phase 7.2

Grades the relevance of retrieved documents to a query.

Features:
- LLM-based relevance scoring (0-10)
- Batch grading for multiple documents
- Feedback generation for query rewriting
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.constants import DEFAULT_RELEVANCE_THRESHOLD, MAX_CONTENT_SNIPPET_LENGTH, MAX_DOCUMENT_PREVIEW_LENGTH
from app.core.resilience import retry_on_transient
from app.engine.agentic_rag.runtime_llm_socket import (
    ainvoke_agentic_rag_llm,
    resolve_agentic_rag_llm,
)
from app.engine.llm_factory import ThinkingTier
from app.engine.agentic_rag.retrieval_grader_support import (
    batch_grade_legacy_impl,
    batch_grade_structured_impl,
    build_feedback_direct_impl,
    generate_feedback_impl,
    parse_batch_response_impl,
    sequential_grade_documents_impl,
)
from app.engine.llm_pool import get_llm_moderate  # SOTA: Shared LLM Pool

logger = logging.getLogger(__name__)


@dataclass
class DocumentGrade:
    """Grade for a single document."""
    document_id: str
    content_preview: str
    score: float  # 0-10
    is_relevant: bool
    reason: str


@dataclass 
class GradingResult:
    """Result of grading multiple documents."""
    query: str
    grades: List[DocumentGrade] = field(default_factory=list)
    avg_score: float = 0.0
    relevant_count: int = 0
    feedback: str = ""
    
    def __post_init__(self):
        if self.grades:
            self.avg_score = sum(g.score for g in self.grades) / len(self.grades)
            self.relevant_count = sum(1 for g in self.grades if g.is_relevant)
    
    @property
    def needs_rewrite(self) -> bool:
        """
        Check if query needs rewriting based on grades.
        
        SOTA 2025 Pattern (Self-RAG + Meta CRAG):
        - Trust the retriever: modern hybrid search is good enough
        - Only rewrite when truly failed (zero relevant docs)
        - Uses configurable confidence thresholds
        
        Reference:
        - Self-RAG (Asai et al.): Confidence-based iteration
        - Meta CRAG: Lightweight retrieval evaluator
        - Anthropic: Plan-Do-Check-Refine (one loop, not multi-iteration)
        """
        from app.core.config import settings
        
        # SOTA Pattern: If we found ANY relevant doc, trust the retrieval
        if self.relevant_count >= 1:
            return False
        
        # Normalize score to 0-1 confidence scale
        normalized_confidence = self.avg_score / 10.0
        
        # Only rewrite if ZERO relevant docs AND below MEDIUM confidence threshold
        # Uses configurable threshold instead of hardcoded 4.0
        return normalized_confidence < settings.rag_confidence_medium



GRADING_PROMPT = """Bạn là Retrieval Grader cho hệ thống AI.

Đánh giá mức độ liên quan của document với query.

Query: {query}

Document:
{document}

Trả về JSON:
{{
    "score": 0-10,
    "is_relevant": true/false,
    "reason": "Lý do ngắn gọn"
}}

Hướng dẫn chấm điểm:
- 9-10: Trực tiếp trả lời hoàn toàn query
- 7-8: Liên quan mạnh, chứa thông tin chính
- 5-6: Liên quan một phần, cần bổ sung
- 3-4: Liên quan yếu, chỉ context chung
- 0-2: Không liên quan

CHỈ TRẢ VỀ JSON."""


FEEDBACK_PROMPT = """Dựa trên kết quả grading sau, đề xuất cách cải thiện query:

Query gốc: {query}

Kết quả:
- Điểm trung bình: {avg_score}/10
- Số documents liên quan: {relevant_count}/{total}
- Vấn đề chính: {issues}

Đề xuất query mới hoặc keywords bổ sung:"""


# SOTA 2025: Batch grading reduces 5 LLM calls → 1 LLM call
# Reference: LangChain llm.batch pattern, ROGRAG framework
BATCH_GRADING_PROMPT = """Bạn là Retrieval Grader cho hệ thống AI.

Đánh giá mức độ liên quan của TỪNG document với query dưới đây.

Query: {query}

Documents:
{documents}

Trả về JSON ARRAY (một mảng các object):
[
    {{"doc_index": 0, "score": 0-10, "is_relevant": true/false, "reason": "Lý do ngắn gọn"}},
    {{"doc_index": 1, "score": 0-10, "is_relevant": true/false, "reason": "Lý do ngắn gọn"}},
    ...
]

Hướng dẫn chấm điểm:
- 9-10: Trực tiếp trả lời hoàn toàn query
- 7-8: Liên quan mạnh, chứa thông tin chính
- 5-6: Liên quan một phần, cần bổ sung
- 3-4: Liên quan yếu, chỉ context chung
- 0-2: Không liên quan

CHỈ TRẢ VỀ JSON ARRAY, KHÔNG CÓ TEXT KHÁC."""


class RetrievalGrader:
    """
    Grades document relevance for Corrective RAG.
    
    Usage:
        grader = RetrievalGrader()
        result = await grader.grade_documents(query, documents)
        if result.needs_rewrite:
            # Trigger query rewriting
    """
    
    def __init__(self, threshold: float = DEFAULT_RELEVANCE_THRESHOLD):
        """
        Initialize grader.
        
        Args:
            threshold: Minimum score to consider document relevant
        """
        self._llm = None
        self._threshold = threshold
        self._init_llm()
    
    def _init_llm(self):
        """Initialize Gemini LLM from shared pool for grading."""
        try:
            # SOTA: Use shared LLM from pool (memory optimized)
            self._llm = self._resolve_runtime_llm()
            logger.info("RetrievalGrader initialized with shared MODERATE tier LLM")
        except Exception as e:
            logger.error("Failed to initialize RetrievalGrader LLM: %s", e)
            self._llm = None

    def _resolve_runtime_llm(self):
        """Resolve the request-time MODERATE-tier grading LLM."""
        llm = resolve_agentic_rag_llm(
            tier=ThinkingTier.MODERATE,
            cached_llm=self._llm,
            fallback_factory=get_llm_moderate,
            component="RetrievalGrader",
        )
        if llm is not None:
            self._llm = llm
        return llm
    
    async def grade_document(
        self,
        query: str,
        document: Dict[str, Any]
    ) -> DocumentGrade:
        """
        Grade a single document.

        Args:
            query: User query
            document: Document dict with 'content', 'id' keys

        Returns:
            DocumentGrade with score and relevance
        """
        doc_id = document.get("id", document.get("node_id", "unknown"))
        content = document.get("content", document.get("text", ""))[:MAX_DOCUMENT_PREVIEW_LENGTH]

        llm = self._resolve_runtime_llm()
        if not llm:
            # Fallback: keyword matching
            return self._rule_based_grade(query, doc_id, content)

        try:
            # Sprint 67: Structured Outputs — constrained decoding for grading
            from app.core.config import settings
            if getattr(settings, 'enable_structured_outputs', False):
                return await self._grade_document_structured(query, doc_id, content)

            return await self._grade_document_legacy(query, doc_id, content)

        except Exception as e:
            logger.warning("LLM grading failed: %s", e)
            return self._rule_based_grade(query, doc_id, content)

    @retry_on_transient()
    async def _grade_document_structured(self, query: str, doc_id: str, content: str) -> DocumentGrade:
        """Grade single document using structured output."""
        from app.engine.structured_schemas import SingleDocGrade

        messages = [
            SystemMessage(content="You are a document relevance grader."),
            HumanMessage(content=GRADING_PROMPT.format(query=query, document=content))
        ]

        from app.services.structured_invoke_service import StructuredInvokeService

        result = await StructuredInvokeService.ainvoke(
            llm=self._llm,
            schema=SingleDocGrade,
            payload=messages,
            tier="moderate",
        )
        return DocumentGrade(
            document_id=doc_id,
            content_preview=content[:MAX_CONTENT_SNIPPET_LENGTH],
            score=result.score,
            is_relevant=result.score >= self._threshold,
            reason=result.reason,
        )

    @retry_on_transient()
    async def _grade_document_legacy(self, query: str, doc_id: str, content: str) -> DocumentGrade:
        """Grade single document using legacy JSON parsing."""
        messages = [
            SystemMessage(content="You are a document relevance grader. Return only valid JSON."),
            HumanMessage(content=GRADING_PROMPT.format(query=query, document=content))
        ]

        response = await ainvoke_agentic_rag_llm(
            llm=self._llm,
            messages=messages,
            tier=ThinkingTier.MODERATE,
            component="RetrievalGraderLegacy",
        )

        # SOTA FIX: Handle Gemini 2.5 Flash content block format
        from app.services.output_processor import extract_thinking_from_response
        text_content, _ = extract_thinking_from_response(response.content)
        result = text_content.strip()

        # Parse JSON
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
        result = result.strip()

        data = json.loads(result)
        score = float(data.get("score", 5.0))

        return DocumentGrade(
            document_id=doc_id,
            content_preview=content[:MAX_CONTENT_SNIPPET_LENGTH],
            score=score,
            is_relevant=score >= self._threshold,
            reason=data.get("reason", ""),
        )
    
    async def grade_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        query_embedding: Optional[List[float]] = None
    ) -> GradingResult:
        """
        Grade multiple documents.
        
        SOTA 2025 Phase 3: Tiered grading with embedding fast-pass.
        - Tier 1: Embedding similarity → Auto PASS/FAIL (skip LLM)
        - Tier 2: LLM grading → Only for uncertain docs
        
        Expected speedup: 70-75% reduction in grader latency.
        
        Args:
            query: User query
            documents: List of document dicts
            query_embedding: Pre-computed query embedding (optional, for tiered grading)
            
        Returns:
            GradingResult with all grades and summary
        """
        self._resolve_runtime_llm()

        if not documents:
            return GradingResult(
                query=query,
                grades=[],
                feedback="No documents retrieved. Try different keywords."
            )
        
        # ====================================================================
        # PHASE 2: HYBRID CONFIDENCE PRE-FILTER (SOTA 2025 - Self-RAG)
        # ====================================================================
        # Fast non-LLM evaluation: BM25 + embedding + maritime boosting
        # Reference: Anthropic Contextual Retrieval, Self-RAG
        # Latency: ~0.1s vs 14s for LLM-only grading
        # ====================================================================
        from app.engine.agentic_rag.confidence_evaluator import get_hybrid_confidence_evaluator
        
        hybrid_evaluator = get_hybrid_confidence_evaluator()
        hybrid_results = hybrid_evaluator.evaluate_batch(query, documents, query_embedding)
        
        # Calculate aggregate confidence
        aggregate_confidence = hybrid_evaluator.aggregate_confidence(hybrid_results)
        
        logger.info(
            "[GRADER] Hybrid pre-filter: aggregate=%.2f, HIGH=%d, MEDIUM=%d",
            aggregate_confidence,
            sum(1 for r in hybrid_results if r.is_high_confidence),
            sum(1 for r in hybrid_results if r.is_medium_confidence and not r.is_high_confidence),
        )
        
        # Separate by hybrid confidence level
        high_conf_docs = []
        high_conf_results = []
        needs_mini_judge_docs = []
        
        for doc, result in zip(documents, hybrid_results):
            if result.is_high_confidence:
                # HIGH confidence from hybrid → skip Mini-Judge
                high_conf_docs.append(doc)
                high_conf_results.append(result)
            else:
                # MEDIUM or LOW → needs Mini-Judge verification
                needs_mini_judge_docs.append(doc)
        
        # ====================================================================
        # PHASE 3.5: LLM MINI-JUDGE PRE-GRADING (SOTA 2025)
        # ====================================================================
        # Only called for documents not already HIGH confidence from hybrid
        # Root Cause Fix: Bi-encoder similarity ≠ Relevance (65-80% accuracy)
        # Solution: LLM Mini-Judge for binary relevance (85-95% accuracy)
        # ====================================================================
        from app.engine.agentic_rag.mini_judge_grader import get_mini_judge_grader
        
        mini_judge = get_mini_judge_grader()
        
        # Build grades list
        grades = []
        
        # Add HIGH confidence docs from hybrid (no LLM needed)
        for doc, result in zip(high_conf_docs, high_conf_results):
            doc_id = doc.get("id", doc.get("node_id", "unknown"))
            content_preview = doc.get("content", doc.get("text", ""))[:100]
            
            grades.append(DocumentGrade(
                document_id=doc_id,
                content_preview=content_preview,
                score=result.score * 10,  # Convert 0-1 to 0-10
                is_relevant=True,
                reason=f"[Hybrid HIGH] BM25={result.bm25_score:.2f}, Domain={result.domain_boost:.2f}"
            ))
        
        # Mini-Judge only for non-HIGH confidence docs
        relevant_docs = []
        relevant_results = []
        uncertain_docs = []
        
        if needs_mini_judge_docs:
            judge_results = await mini_judge.pre_grade_batch(query, needs_mini_judge_docs)
            
            for doc, result in zip(needs_mini_judge_docs, judge_results):
                if result.is_relevant and result.confidence in ("high", "medium"):
                    relevant_docs.append(doc)
                    relevant_results.append(result)
                else:
                    uncertain_docs.append(doc)
            
            # Add Mini-Judge approved docs
            for doc, result in zip(relevant_docs, relevant_results):
                grades.append(DocumentGrade(
                    document_id=result.document_id,
                    content_preview=result.content_preview,
                    score=8.5,  # High score for Mini-Judge approved
                    is_relevant=True,
                    reason=f"[Mini-Judge] {result.reason}"
                ))
        
        # ====================================================================
        # SOTA 2025 Phase 2.4a: Early Exit on Sufficient Relevant Docs
        # ====================================================================
        # Pattern: Self-RAG (Asai et al. 2023) - Skip grading when confident
        # Reference: Anthropic Contextual Retrieval, Cohere Re-ranking
        # Key insight: Major labs use re-ranking (~200ms), not LLM grading (19s)
        # This early exit saves 19s when fast evaluators find 2+ relevant docs
        # ====================================================================
        fast_path_relevant_count = len(high_conf_docs) + len(relevant_docs)
        
        if fast_path_relevant_count >= 2:
            # SOTA: Sufficient relevant docs from fast-path - skip LLM batch
            logger.info(
                "[GRADER] SOTA Early Exit: %d relevant docs "
                "from Hybrid+MiniJudge - skipping LLM batch grading (save ~19s)",
                fast_path_relevant_count,
            )
        elif uncertain_docs:
            # Only grade when truly uncertain (0-1 relevant from fast-path)
            llm_grades = await self.batch_grade_documents(query, uncertain_docs[:5])
            grades.extend(llm_grades)
        
        logger.info(
            "[GRADER] Summary: %d docs → Hybrid HIGH=%d, Mini-Judge=%d, LLM Full=%d (saved %d LLM calls)",
            len(documents), len(high_conf_docs), len(relevant_docs),
            0 if fast_path_relevant_count >= 2 else min(len(uncertain_docs), 5),
            len(high_conf_docs) + len(relevant_docs),
        )
        
        result = GradingResult(query=query, grades=grades)
        
        # ====================================================================
        # SOTA FIX: Direct rule-based feedback (NO LLM call!)
        # ====================================================================
        # Root Cause: _generate_feedback() used MODERATE LLM (~19s latency)
        # SOTA Pattern: GradingResult already has avg_score + grades[].reason
        # Reference: LangChain CRAG, Meta CRAG Benchmark, OpenAI RAG 2025
        # ====================================================================
        if result.needs_rewrite:
            issues = [g.reason for g in grades if not g.is_relevant][:3]
            result.feedback = self._build_feedback_direct(
                result.avg_score, result.relevant_count, len(grades), issues
            )
        
        logger.info("[GRADER] Query='%s...' avg_score=%.1f relevant=%d/%d", query[:50], result.avg_score, result.relevant_count, len(grades))
        
        return result
    
    async def batch_grade_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> List[DocumentGrade]:
        """
        SOTA 2025: Batch grade multiple documents in single LLM call.

        Reduces 5 sequential calls → 1 batch call.
        Expected speedup: ~40s → ~10s per grading phase.

        Reference: LangChain llm.batch pattern, ROGRAG framework.
        """
        if not documents:
            return []

        llm = self._resolve_runtime_llm()

        # Fallback to rule-based if no LLM
        if not llm:
            return [
                self._rule_based_grade(
                    query,
                    doc.get("id", doc.get("node_id", "unknown")),
                    doc.get("content", doc.get("text", ""))[:MAX_DOCUMENT_PREVIEW_LENGTH]
                )
                for doc in documents
            ]

        # Format documents for batch prompt
        docs_text = "\n\n".join([
            f"[Document {i}]\nID: {doc.get('id', doc.get('node_id', 'unknown'))}\n{doc.get('content', doc.get('text', ''))[:800]}"
            for i, doc in enumerate(documents)
        ])

        try:
            # Sprint 67: Structured Outputs — constrained decoding for batch grading
            from app.core.config import settings
            if getattr(settings, 'enable_structured_outputs', False):
                return await self._batch_grade_structured(query, documents, docs_text)

            return await self._batch_grade_legacy(query, documents, docs_text)

        except Exception as e:
            logger.warning("Batch grading failed: %s, falling back to sequential", e)
            return await self._sequential_grade_documents(query, documents)

    @retry_on_transient()
    async def _batch_grade_structured(self, query: str, documents: List[Dict[str, Any]],
                                       docs_text: str) -> List[DocumentGrade]:
        """Batch grade using structured output."""
        return await batch_grade_structured_impl(
            llm=self._llm,
            threshold=self._threshold,
            query=query,
            documents=documents,
            docs_text=docs_text,
            prompt=BATCH_GRADING_PROMPT,
            document_grade_cls=DocumentGrade,
        )

    @retry_on_transient()
    async def _batch_grade_legacy(self, query: str, documents: List[Dict[str, Any]],
                                   docs_text: str) -> List[DocumentGrade]:
        """Batch grade using legacy JSON parsing."""
        return await batch_grade_legacy_impl(
            llm=self._llm,
            query=query,
            documents=documents,
            docs_text=docs_text,
            prompt=BATCH_GRADING_PROMPT,
            parse_batch_response=self._parse_batch_response,
        )
    
    async def _sequential_grade_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]]
    ) -> List[DocumentGrade]:
        """Fallback: Sequential grading when batch fails."""
        return await sequential_grade_documents_impl(
            query=query,
            documents=documents,
            grade_document=self.grade_document,
        )
    
    def _parse_batch_response(
        self,
        response: str,
        documents: List[Dict[str, Any]]
    ) -> List[DocumentGrade]:
        """Parse batch grading JSON response."""
        return parse_batch_response_impl(
            response=response,
            documents=documents,
            threshold=self._threshold,
            document_grade_cls=DocumentGrade,
            rule_based_grade=self._rule_based_grade,
        )
    
    def _build_feedback_direct(
        self,
        avg_score: float,
        relevant_count: int,
        total: int,
        issues: List[str]
    ) -> str:
        """
        SOTA: Zero-latency feedback generation using rule-based approach.
        
        Replaces LLM call (~19s) with direct string formatting (0ms).
        Reference: LangChain CRAG, Meta CRAG Benchmark, OpenAI RAG 2025
        
        Args:
            avg_score: Average relevance score (0-10)
            relevant_count: Number of relevant documents
            total: Total documents graded
            issues: List of reasons why documents weren't relevant
            
        Returns:
            Formatted feedback string for QueryRewriter
        """
        return build_feedback_direct_impl(
            avg_score=avg_score,
            relevant_count=relevant_count,
            total=total,
            issues=issues,
        )
    
    async def _generate_feedback(
        self,
        query: str,
        avg_score: float,
        relevant_count: int,
        total: int,
        issues: List[str]
    ) -> str:
        """Generate feedback for query rewriting."""
        self._resolve_runtime_llm()
        return await generate_feedback_impl(
            llm=self._llm,
            query=query,
            avg_score=avg_score,
            relevant_count=relevant_count,
            total=total,
            issues=issues,
            prompt=FEEDBACK_PROMPT,
        )
    
    def _rule_based_grade(
        self, 
        query: str, 
        doc_id: str, 
        content: str
    ) -> DocumentGrade:
        """Fallback rule-based grading using keyword overlap."""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        overlap = query_words.intersection(content_words)
        overlap_ratio = len(overlap) / max(len(query_words), 1)
        
        # Convert ratio to score (0-10)
        score = min(10.0, overlap_ratio * 15)  # Generous scoring
        
        return DocumentGrade(
            document_id=doc_id,
            content_preview=content[:MAX_CONTENT_SNIPPET_LENGTH],
            score=score,
            is_relevant=score >= self._threshold,
            reason=f"Keyword overlap: {len(overlap)} words"
        )
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._resolve_runtime_llm() is not None


# Singleton
_grader: Optional[RetrievalGrader] = None

def get_retrieval_grader() -> RetrievalGrader:
    """Get or create RetrievalGrader singleton."""
    global _grader
    if _grader is None:
        _grader = RetrievalGrader()
    return _grader
