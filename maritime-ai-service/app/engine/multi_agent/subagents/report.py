"""Structured report models for subagent results and aggregator decisions.

Sprint 163 Phase 4: Supervisor-Reads-Reports pattern.
Subagents return SubagentReport (structured evaluation of their result).
Aggregator reads reports and produces AggregatorDecision (merge strategy).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from app.engine.multi_agent.subagents.result import SubagentResult, SubagentStatus


class ReportVerdict(str, Enum):
    """Quality verdict for a subagent's output."""

    CONFIDENT = "confident"
    PARTIAL = "partial"
    LOW_CONFIDENCE = "low_confidence"
    EMPTY = "empty"
    ERROR = "error"


class SubagentReport(BaseModel):
    """Structured report wrapping a subagent's result for the aggregator.

    The supervisor dispatches queries to multiple subagents in parallel.
    Each result is wrapped in a SubagentReport with quality metadata so
    the aggregator can make informed merge decisions without re-reading
    full outputs.
    """

    agent_name: str = Field(..., min_length=1, max_length=64)
    agent_type: str = Field(default="general", max_length=32)
    result: SubagentResult = Field(default_factory=SubagentResult)
    verdict: ReportVerdict = Field(default=ReportVerdict.EMPTY)
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = Field(default="", max_length=500)
    can_stand_alone: bool = Field(default=False)
    needs_complement: List[str] = Field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """Report has actionable content (confident or partial)."""
        return self.verdict in (ReportVerdict.CONFIDENT, ReportVerdict.PARTIAL)

    @property
    def is_high_quality(self) -> bool:
        """Report is confident with high relevance."""
        return self.verdict == ReportVerdict.CONFIDENT and self.relevance_score >= 0.7

    def to_aggregator_summary(self) -> str:
        """One-line summary for inclusion in aggregator LLM prompt."""
        quality = "HIGH" if self.is_high_quality else (
            "OK" if self.is_usable else "LOW"
        )
        standalone = "yes" if self.can_stand_alone else "no"
        return (
            f"[{self.agent_name}] quality={quality} "
            f"relevance={self.relevance_score:.2f} "
            f"standalone={standalone} | {self.summary}"
        )


def build_report(
    agent_name: str,
    agent_type: str,
    result: SubagentResult,
) -> SubagentReport:
    """Build a SubagentReport from a SubagentResult with auto-verdict.

    Evaluates the result quality and assigns verdict, relevance_score,
    summary, and can_stand_alone automatically.
    """
    # Determine verdict from result status and confidence
    if result.status == SubagentStatus.ERROR:
        verdict = ReportVerdict.ERROR
    elif result.status == SubagentStatus.TIMEOUT:
        verdict = ReportVerdict.ERROR
    elif result.status == SubagentStatus.SKIPPED:
        verdict = ReportVerdict.EMPTY
    elif not result.output and not result.data:
        verdict = ReportVerdict.EMPTY
    elif result.confidence >= 0.7:
        verdict = ReportVerdict.CONFIDENT
    elif result.confidence >= 0.4:
        verdict = ReportVerdict.PARTIAL
    else:
        verdict = ReportVerdict.LOW_CONFIDENCE

    # Auto-generate summary
    if result.output:
        summary = result.output[:200].replace("\n", " ").strip()
    elif result.error_message:
        summary = f"Error: {result.error_message[:150]}"
    else:
        summary = "No output"

    # Can stand alone if confident with sufficient output
    can_stand_alone = (
        verdict == ReportVerdict.CONFIDENT
        and len(result.output) >= 50
    )

    # Needs complement hints
    needs_complement: List[str] = []
    if verdict == ReportVerdict.PARTIAL:
        if agent_type == "retrieval":
            needs_complement.append("teaching")
        elif agent_type == "teaching":
            needs_complement.append("retrieval")

    return SubagentReport(
        agent_name=agent_name,
        agent_type=agent_type,
        result=result,
        verdict=verdict,
        relevance_score=result.confidence,
        summary=summary,
        can_stand_alone=can_stand_alone,
        needs_complement=needs_complement,
    )


class AggregatorDecision(BaseModel):
    """Decision from the aggregator on how to merge subagent reports.

    Actions:
    - synthesize: Merge content from multiple agents
    - use_best: Use the primary agent's output as-is
    - re_route: Send query to a different agent
    - escalate: All agents failed, return error
    """

    action: str = Field(
        default="use_best",
        pattern=r"^(synthesize|use_best|re_route|escalate)$",
    )
    primary_agent: str = Field(default="")
    secondary_agents: List[str] = Field(default_factory=list)
    reasoning: str = Field(default="", max_length=500)
    re_route_target: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
