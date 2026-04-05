"""
Answer Verifier - Phase 7.4

Verifies generated answers for hallucinations and accuracy.

Features:
- Factual consistency checking
- Citation verification
- Confidence scoring
- Warning generation
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.singleton import singleton_factory
from app.engine.agentic_rag.runtime_llm_socket import (
    ainvoke_agentic_rag_llm,
    resolve_agentic_rag_llm,
)
from app.engine.llm_factory import ThinkingTier
from app.engine.llm_pool import get_llm_moderate  # SOTA: Shared LLM Pool

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of answer verification.

    NOTE: confidence is on 0-100 scale (from LLM verification prompt).
    """
    is_valid: bool
    confidence: float  # 0-100 scale (matches LLM prompt output)
    issues: List[str]
    warning: Optional[str] = None

    @property
    def needs_warning(self) -> bool:
        """Check if answer needs a warning. Confidence is 0-100 scale."""
        return not self.is_valid or self.confidence < 70  # 0-100 scale threshold


VERIFY_PROMPT = """Bạn là Answer Verifier cho hệ thống Wiii.

Kiểm tra xem câu trả lời có chính xác với nguồn không.

Câu trả lời:
{answer}

Nguồn tham khảo:
{sources}

Trả về JSON:
{{
    "is_factually_correct": true/false,
    "confidence": 0-100,
    "issues": ["issue1", "issue2"],
    "has_unsupported_claims": true/false
}}

Kiểm tra:
1. Thông tin trong câu trả lời có xuất hiện trong nguồn không?
2. Có thông tin bịa đặt (hallucination) không?
3. Số liệu, tên, điều luật có chính xác không?

CHỈ TRẢ VỀ JSON."""


class AnswerVerifier:
    """
    Verifies answers for hallucinations.
    
    Usage:
        verifier = AnswerVerifier()
        result = await verifier.verify(answer, sources)
        if result.needs_warning:
            answer = f"⚠️ {result.warning}\\n{answer}"
    """
    
    def __init__(self, min_confidence: float = 70.0):
        """
        Initialize verifier.
        
        Args:
            min_confidence: Minimum confidence to pass verification
        """
        self._llm = None
        self._min_confidence = min_confidence
        self._init_llm()
    
    def _init_llm(self):
        """Initialize Gemini LLM from shared pool for verification."""
        try:
            # SOTA: Use shared LLM from pool (memory optimized)
            self._llm = self._resolve_runtime_llm()
            logger.info("AnswerVerifier initialized with shared MODERATE tier LLM")
        except Exception as e:
            logger.error("Failed to initialize AnswerVerifier LLM: %s", e)
            self._llm = None

    def _resolve_runtime_llm(self):
        """Resolve the request-time MODERATE-tier verifier LLM."""
        llm = resolve_agentic_rag_llm(
            tier=ThinkingTier.MODERATE,
            cached_llm=self._llm,
            fallback_factory=get_llm_moderate,
            component="AnswerVerifier",
        )
        if llm is not None:
            self._llm = llm
        return llm
    
    async def verify(
        self,
        answer: str,
        sources: List[Dict[str, Any]]
    ) -> VerificationResult:
        """
        Verify answer against sources.
        
        Args:
            answer: Generated answer to verify
            sources: Source documents used for generation
            
        Returns:
            VerificationResult with validity and confidence
        """
        if not answer:
            return VerificationResult(
                is_valid=False,
                confidence=0,
                issues=["Empty answer"],
                warning="Không có câu trả lời"
            )
        
        if not sources:
            # No sources to verify against
            return VerificationResult(
                is_valid=True,
                confidence=50,  # Uncertain
                issues=["No sources to verify against"],
                warning="Câu trả lời có thể không chính xác do thiếu nguồn tham khảo"
            )
        
        llm = self._resolve_runtime_llm()
        if not llm:
            return self._rule_based_verify(answer, sources)
        
        try:
            # Format sources
            source_text = "\n---\n".join([
                s.get("content", s.get("text", ""))[:500]
                for s in sources[:3]  # Limit to 3 sources
            ])
            
            messages = [
                SystemMessage(content="You are a fact-checker. Return only valid JSON."),
                HumanMessage(content=VERIFY_PROMPT.format(
                    answer=answer[:1500],  # Limit answer length
                    sources=source_text
                ))
            ]
            
            response = await ainvoke_agentic_rag_llm(
                llm=llm,
                messages=messages,
                tier=ThinkingTier.MODERATE,
                component="AnswerVerifier",
            )
            
            # SOTA FIX: Handle Gemini 2.5 Flash content block format
            from app.services.output_processor import extract_thinking_from_response
            text_content, _ = extract_thinking_from_response(response.content)
            result = text_content.strip()
            
            # Parse JSON
            import json
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            result = result.strip()
            
            data = json.loads(result)
            
            is_correct = data.get("is_factually_correct", True)
            confidence = float(data.get("confidence", 80))
            issues = data.get("issues", [])
            has_unsupported = data.get("has_unsupported_claims", False)
            
            is_valid = is_correct and not has_unsupported and confidence >= self._min_confidence
            
            warning = None
            if not is_valid:
                if has_unsupported:
                    warning = "Câu trả lời có thể chứa thông tin chưa được xác minh"
                elif confidence < self._min_confidence:
                    warning = f"Độ tin cậy thấp ({confidence:.0f}%). Vui lòng kiểm tra lại với nguồn chính thức"
                else:
                    warning = "Một số thông tin có thể không chính xác"
            
            logger.info("[VERIFIER] valid=%s confidence=%.0f%% issues=%d", is_valid, confidence, len(issues))
            
            return VerificationResult(
                is_valid=is_valid,
                confidence=confidence,
                issues=issues,
                warning=warning
            )
            
        except Exception as e:
            logger.warning("LLM verification failed: %s", e)
            return self._rule_based_verify(answer, sources)
    
    async def check_citations(
        self,
        answer: str,
        sources: List[Dict[str, Any]]
    ) -> Dict[str, bool]:
        """
        Check if citations in answer match sources.
        
        Args:
            answer: Answer with citations
            sources: Source documents
            
        Returns:
            Dict mapping citation to validity
        """
        # Simple rule-based citation check
        import re
        
        # Find patterns like "Điều 15", "Rule 15", "SOLAS Chapter II-2"
        citation_patterns = [
            r"Điều\s+\d+",
            r"Rule\s+\d+",
            r"SOLAS\s+Chapter\s+[\w-]+",
            r"MARPOL\s+Annex\s+\w+"
        ]
        
        citations_found = []
        for pattern in citation_patterns:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            citations_found.extend(matches)
        
        # Check if citations appear in sources
        source_text = " ".join([
            s.get("content", s.get("text", ""))
            for s in sources
        ]).lower()
        
        results = {}
        for citation in citations_found:
            results[citation] = citation.lower() in source_text
        
        return results
    
    def _rule_based_verify(
        self,
        answer: str,
        sources: List[Dict[str, Any]]
    ) -> VerificationResult:
        """Fallback rule-based verification."""
        # Simple keyword overlap check
        source_text = " ".join([
            s.get("content", s.get("text", ""))
            for s in sources
        ]).lower()
        
        answer_words = set(answer.lower().split())
        source_words = set(source_text.split())
        
        overlap = answer_words.intersection(source_words)
        overlap_ratio = len(overlap) / max(len(answer_words), 1)
        
        confidence = min(100, overlap_ratio * 150)  # Scale to 0-100
        
        issues = []
        if overlap_ratio < 0.3:
            issues.append("Low keyword overlap with sources")
        
        return VerificationResult(
            is_valid=confidence >= self._min_confidence,
            confidence=confidence,
            issues=issues,
            warning="Không thể xác minh hoàn toàn do giới hạn hệ thống" if confidence < self._min_confidence else None
        )
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._llm is not None


get_answer_verifier = singleton_factory(AnswerVerifier)
