"""
Grader Agent Node - Quality Control Specialist

Evaluates response quality and provides feedback.

**Integrated with agents/ framework for config and tracing.**
"""

import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.resilience import retry_on_transient
from app.engine.llm_pool import get_llm_moderate
from app.engine.multi_agent.state import AgentState
from app.engine.agents import GRADER_AGENT_CONFIG

logger = logging.getLogger(__name__)


GRADING_PROMPT = """Bạn là Quality Grader cho hệ thống AI.

Đánh giá chất lượng câu trả lời.

**Query gốc:** {query}

**Câu trả lời:** {answer}

Trả về JSON:
{{
    "score": 0-10,
    "is_helpful": true/false,
    "is_accurate": true/false,
    "is_complete": true/false,
    "feedback": "Góp ý ngắn gọn"
}}

Tiêu chí:
- Helpful: Có trả lời đúng câu hỏi không?
- Accurate: Thông tin có chính xác không?
- Complete: Có đầy đủ thông tin không?

CHỈ TRẢ VỀ JSON."""


class GraderAgentNode:
    """
    Grader Agent - Quality control specialist.
    
    Responsibilities:
    - Evaluate response quality
    - Check accuracy
    - Provide improvement feedback
    
    Implements agents/ framework integration.
    """
    
    def __init__(self, min_score: float = 6.0):
        """
        Initialize Grader Agent.
        
        Args:
            min_score: Minimum acceptable score
        """
        self._llm = None
        self._min_score = min_score
        self._config = GRADER_AGENT_CONFIG
        self._init_llm()
        logger.info("GraderAgentNode initialized with config: %s", self._config.id)
    
    def _init_llm(self):
        """Initialize grading LLM with MODERATE tier thinking."""
        try:
            # CHỈ THỊ SỐ 28: Use MODERATE tier (4096 tokens) for grading
            self._llm = get_llm_moderate()  # Shared pool instance
        except Exception as e:
            logger.error("Failed to initialize Grader LLM: %s", e)
            self._llm = None
    
    async def process(self, state: AgentState) -> AgentState:
        """
        Grade agent outputs.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with grading results
        """
        query = state.get("query", "")
        outputs = state.get("agent_outputs", {})
        
        # Get the main output
        main_output = (
            outputs.get("rag") or 
            outputs.get("tutor") or 
            outputs.get("memory") or 
            ""
        )
        
        if not main_output:
            state["grader_score"] = 0.0
            state["grader_feedback"] = "No output to grade"
            state["current_agent"] = "grader"
            return state
        
        try:
            result = await self._grade_response(query, main_output)
            
            state["grader_score"] = result.get("score", 5.0)
            state["grader_feedback"] = result.get("feedback", "")
            state["current_agent"] = "grader"
            
            # Log result
            is_pass = result.get("score", 0) >= self._min_score
            logger.info("[GRADER] Score=%s/10 Pass=%s", result.get("score", 0), is_pass)
            
        except Exception as e:
            logger.error("[GRADER] Error: %s", e)
            state["grader_score"] = 5.0  # Default
            state["grader_feedback"] = "Grading failed"
            state["error"] = "grader_error"
        
        return state
    
    async def _grade_response(self, query: str, answer: str) -> dict:
        """Grade a single response."""
        if not self._llm:
            return self._rule_based_grade(query, answer)

        try:
            # Sprint 67: Structured Outputs — constrained decoding for grading
            from app.core.config import settings
            if getattr(settings, 'enable_structured_outputs', False):
                return await self._grade_structured(query, answer)

            return await self._grade_legacy(query, answer)

        except Exception as e:
            logger.warning("LLM grading failed: %s", e)
            return self._rule_based_grade(query, answer)

    @retry_on_transient()
    async def _grade_structured(self, query: str, answer: str) -> dict:
        """Grade using structured output (constrained decoding)."""
        from app.engine.structured_schemas import QualityGradeResult

        structured_llm = self._llm.with_structured_output(QualityGradeResult)
        messages = [
            SystemMessage(content="You are a quality grader. Grade the response quality."),
            HumanMessage(content=GRADING_PROMPT.format(
                query=query,
                answer=answer[:1500]
            ))
        ]

        result = await structured_llm.ainvoke(messages)
        return result.model_dump()

    @retry_on_transient()
    async def _grade_legacy(self, query: str, answer: str) -> dict:
        """Grade using legacy JSON parsing."""
        messages = [
            SystemMessage(content="You are a quality grader. Return only valid JSON."),
            HumanMessage(content=GRADING_PROMPT.format(
                query=query,
                answer=answer[:1500]
            ))
        ]

        response = await self._llm.ainvoke(messages)

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

        return json.loads(result)
    
    def _rule_based_grade(self, query: str, answer: str) -> dict:
        """Fallback rule-based grading."""
        # Simple heuristics
        score = 5.0
        
        # Length check
        if len(answer) > 100:
            score += 1.0
        if len(answer) > 500:
            score += 1.0
        
        # Query word coverage
        query_words = set(query.lower().split())
        answer_lower = answer.lower()
        coverage = sum(1 for w in query_words if w in answer_lower) / max(len(query_words), 1)
        score += coverage * 2
        
        # Cap at 10
        score = min(10.0, score)
        
        _is_helpful = score >= 6
        _is_complete = len(answer) > 200
        # Sprint 144: Vietnamese feedback with quality breakdown
        _fb_parts = []
        if _is_helpful:
            _fb_parts.append("Hữu ích: Có")
        else:
            _fb_parts.append("Hữu ích: Chưa đạt")
        _fb_parts.append(f"Đầy đủ: {'Có' if _is_complete else 'Chưa đủ chi tiết'}")
        _fb_parts.append(f"Độ dài: {len(answer)} ký tự")
        _fb_parts.append(f"Độ phủ từ khóa: {coverage:.0%}")
        return {
            "score": score,
            "is_helpful": _is_helpful,
            "is_accurate": True,  # Can't verify without LLM
            "is_complete": _is_complete,
            "feedback": " | ".join(_fb_parts)
        }
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self._llm is not None


# Singleton
_grader_node: Optional[GraderAgentNode] = None

def get_grader_agent_node() -> GraderAgentNode:
    """Get or create GraderAgentNode singleton."""
    global _grader_node
    if _grader_node is None:
        _grader_node = GraderAgentNode()
    return _grader_node
