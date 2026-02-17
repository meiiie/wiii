"""
Wiii Evaluation Framework — Lightweight Response Quality Metrics.

SOTA 2026: Evaluation as a first-class concern (Google, AWS, Anthropic).
Opt-in via `enable_evaluation=True` in config.
"""

from app.engine.evaluation.evaluator import ResponseEvaluator, EvaluationResult

__all__ = ["ResponseEvaluator", "EvaluationResult"]
