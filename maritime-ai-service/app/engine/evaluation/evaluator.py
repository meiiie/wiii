"""
Lightweight Evaluation Framework — Response Quality Metrics.

SOTA 2026: Evaluation is the #1 differentiator for production RAG systems
(Google DeepMind, AWS Aegis, Anthropic eval patterns).

Metrics:
- Faithfulness: Is the answer grounded in retrieved context?
- Answer Relevancy: Does the answer address the user's query?
- Context Precision: Are the retrieved chunks actually useful?

Uses existing `get_llm_light()` for cost-efficient scoring.
Config-gated: Only runs when `settings.enable_evaluation` is True.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of evaluating a single response."""

    faithfulness: float = 0.0  # 0-1: answer grounded in context
    answer_relevancy: float = 0.0  # 0-1: answer addresses query
    context_precision: float = 0.0  # 0-1: retrieved chunks are useful
    overall_score: float = 0.0  # Weighted average
    details: Dict[str, str] = field(default_factory=dict)

    @property
    def is_acceptable(self) -> bool:
        """Score >= 0.6 is acceptable for production responses."""
        return self.overall_score >= 0.6


class ResponseEvaluator:
    """
    Lightweight evaluator for RAG response quality.

    Design decisions:
    - Uses LIGHT tier LLM (cheapest) for scoring
    - Single-prompt evaluation (not multi-turn)
    - Returns structured scores, not just pass/fail
    - Weights: faithfulness=0.4, relevancy=0.4, precision=0.2
    """

    WEIGHTS = {
        "faithfulness": 0.4,
        "answer_relevancy": 0.4,
        "context_precision": 0.2,
    }

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        """Lazy-load LIGHT tier LLM."""
        if self._llm is None:
            from app.engine.llm_pool import get_llm_light

            self._llm = get_llm_light()
        return self._llm

    async def evaluate(
        self,
        query: str,
        answer: str,
        context_chunks: Optional[List[str]] = None,
    ) -> EvaluationResult:
        """
        Evaluate a RAG response against the query and context.

        Args:
            query: Original user query
            answer: Generated answer
            context_chunks: Retrieved context chunks (if any)

        Returns:
            EvaluationResult with individual and overall scores
        """
        if not settings.enable_evaluation:
            return EvaluationResult(details={"skipped": "evaluation disabled"})

        if not answer or not answer.strip():
            return EvaluationResult(details={"skipped": "empty answer"})

        context_text = "\n---\n".join(context_chunks) if context_chunks else ""

        try:
            scores = await self._score_with_llm(query, answer, context_text)
            overall = sum(
                scores.get(metric, 0.0) * weight
                for metric, weight in self.WEIGHTS.items()
            )
            return EvaluationResult(
                faithfulness=scores.get("faithfulness", 0.0),
                answer_relevancy=scores.get("answer_relevancy", 0.0),
                context_precision=scores.get("context_precision", 0.0),
                overall_score=round(overall, 3),
                details={"method": "llm_scoring"},
            )
        except Exception as e:
            logger.warning("Evaluation failed: %s", e)
            return EvaluationResult(details={"error": "Evaluation failed"})

    async def _score_with_llm(
        self, query: str, answer: str, context: str
    ) -> Dict[str, float]:
        """Use LLM to score the response on 3 metrics."""
        prompt = self._build_eval_prompt(query, answer, context)
        llm = self._get_llm()

        try:
            response = await llm.ainvoke(prompt)
            content = (
                response.content
                if hasattr(response, "content")
                else str(response)
            )
            return self._parse_scores(content)
        except Exception as e:
            logger.warning("LLM scoring failed: %s", e)
            return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0}

    def _build_eval_prompt(
        self, query: str, answer: str, context: str
    ) -> str:
        """Build the evaluation prompt."""
        context_section = (
            f"CONTEXT:\n{context[:2000]}\n\n" if context else "CONTEXT: None provided\n\n"
        )

        return f"""You are an evaluation judge. Score the following response on 3 metrics.
Each score must be a decimal between 0.0 and 1.0.

QUERY: {query}

{context_section}ANSWER: {answer[:2000]}

Score these metrics:
1. faithfulness: Is the answer factually grounded in the context? (0.0=hallucinated, 1.0=fully grounded)
2. answer_relevancy: Does the answer address the user's query? (0.0=irrelevant, 1.0=perfectly relevant)
3. context_precision: Are the context chunks useful for answering? (0.0=useless, 1.0=highly precise)

Respond ONLY in this exact format (no other text):
faithfulness: 0.X
answer_relevancy: 0.X
context_precision: 0.X"""

    def _parse_scores(self, content: str) -> Dict[str, float]:
        """Parse LLM output into metric scores."""
        scores = {}
        for line in content.strip().split("\n"):
            line = line.strip()
            for metric in ["faithfulness", "answer_relevancy", "context_precision"]:
                if line.lower().startswith(metric):
                    try:
                        value = float(line.split(":")[-1].strip())
                        scores[metric] = max(0.0, min(1.0, value))
                    except (ValueError, IndexError):
                        scores[metric] = 0.0
        return scores


# Module-level singleton
_evaluator: Optional[ResponseEvaluator] = None


def get_evaluator() -> ResponseEvaluator:
    """Get or create the evaluator singleton."""
    global _evaluator
    if _evaluator is None:
        _evaluator = ResponseEvaluator()
    return _evaluator
