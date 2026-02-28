"""
Structured Output Schemas - Sprint 67 + Sprint 71

Pydantic models for LLM structured outputs (constrained decoding).
Used with LangChain's `.with_structured_output()` when `enable_structured_outputs=True`.

Components:
- RoutingDecision: SOTA agent routing with CoT, intent, confidence (Sprint 71)
- QualityGradeResult: Response quality grading
- GuardianLLMResult: Content moderation decisions
- SingleDocGrade: Single document relevance grading
- BatchDocGrades: Batch document grading
"""

from typing import Literal, Optional, List

from pydantic import BaseModel, Field


# =============================================================================
# Supervisor Routing (Sprint 71: SOTA with CoT, intent, confidence)
# =============================================================================

class RoutingDecision(BaseModel):
    """SOTA structured output for supervisor routing (Sprint 71).

    Enhanced with chain-of-thought reasoning, intent classification,
    and confidence scoring for confidence-gated fallback.
    """
    reasoning: str = Field(
        default="",
        description="Brief chain-of-thought reasoning for the routing decision (Vietnamese)"
    )
    intent: Literal["lookup", "learning", "personal", "social", "off_topic", "web_search", "product_search", "colleague_consult"] = Field(
        default="lookup",
        description="Query intent: lookup=tra cứu, learning=học/giải thích/quiz, personal=ngữ cảnh cá nhân, social=chào hỏi/cảm ơn, off_topic=không liên quan domain, web_search=tìm kiếm web/tin tức/pháp luật, product_search=tìm kiếm/so sánh sản phẩm/giá cả trên sàn TMĐT, colleague_consult=hỏi ý kiến Bro/đồng nghiệp về trading/crypto/rủi ro (chỉ admin)"
    )
    agent: Literal["RAG_AGENT", "TUTOR_AGENT", "MEMORY_AGENT", "DIRECT", "PRODUCT_SEARCH_AGENT", "COLLEAGUE_AGENT"] = Field(
        description="The agent to route the query to"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Routing confidence 0-1"
    )


# =============================================================================
# Quality Grader (GraderAgentNode)
# =============================================================================

class QualityGradeResult(BaseModel):
    """Structured output for response quality grading."""
    score: float = Field(ge=0, le=10, description="Quality score 0-10")
    is_helpful: bool = Field(description="Does the answer address the question?")
    is_accurate: bool = Field(description="Is the information accurate?")
    is_complete: bool = Field(description="Is the answer complete?")
    feedback: str = Field(description="Brief feedback in Vietnamese")


# =============================================================================
# Guardian Agent
# =============================================================================

class PronounRequestInfo(BaseModel):
    """Pronoun request info detected in user message."""
    detected: bool = Field(default=False, description="Whether a pronoun request was detected")
    appropriate: bool = Field(default=False, description="Whether the pronoun request is appropriate")
    user_called: str = Field(default="bạn", description="How AI should address user")
    ai_self: str = Field(default="tôi", description="How AI should refer to itself")


class GuardianLLMResult(BaseModel):
    """Structured output for Guardian content moderation."""
    action: Literal["ALLOW", "BLOCK", "FLAG"] = Field(
        description="Moderation decision: ALLOW, BLOCK, or FLAG"
    )
    reason: Optional[str] = Field(default=None, description="Reason for decision")
    confidence: float = Field(default=0.8, ge=0, le=1, description="Decision confidence")
    pronoun_request: Optional[PronounRequestInfo] = Field(
        default=None, description="Pronoun request info if detected"
    )


# =============================================================================
# Retrieval Grader (single document)
# =============================================================================

class SingleDocGrade(BaseModel):
    """Structured output for single document relevance grading."""
    score: float = Field(ge=0, le=10, description="Relevance score 0-10")
    is_relevant: bool = Field(description="Whether the document is relevant")
    reason: str = Field(description="Brief reason in Vietnamese")


# =============================================================================
# Retrieval Grader (batch)
# =============================================================================

class BatchDocGradeItem(BaseModel):
    """Single item in batch document grading."""
    doc_index: int = Field(ge=0, description="Index of the document in the batch")
    score: float = Field(ge=0, le=10, description="Relevance score 0-10")
    is_relevant: bool = Field(description="Whether the document is relevant")
    reason: str = Field(description="Brief reason in Vietnamese")


class BatchDocGrades(BaseModel):
    """Structured output for batch document grading."""
    grades: List[BatchDocGradeItem] = Field(description="List of document grades")


# =============================================================================
# Aggregator Decision (Sprint 163 Phase 4)
# =============================================================================

class AggregatorDecisionSchema(BaseModel):
    """Structured output for aggregator merge strategy decision."""
    action: Literal["synthesize", "use_best", "re_route", "escalate"] = Field(
        description="Merge strategy: synthesize=combine, use_best=pick one, re_route=retry, escalate=fail"
    )
    primary_agent: str = Field(
        default="",
        description="Name of the primary agent to use"
    )
    secondary_agents: List[str] = Field(
        default_factory=list,
        description="Names of secondary agents for supplementary content"
    )
    reasoning: str = Field(
        default="",
        description="Brief reasoning for the decision (Vietnamese)"
    )
    re_route_target: Optional[str] = Field(
        default=None,
        description="Target agent for re-routing (only when action=re_route)"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Decision confidence 0-1"
    )
