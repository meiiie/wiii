"""DEPRECATED: Tutor subgraph builder — three-phase teaching pipeline.

LangGraph removed (De-LangGraphing Phase 3).
The node functions (analyze_node, generate_node, refine_node, output_node)
are preserved as they may be reused by a future pipeline implementation.

Original flow:
    START → analyze → generate → refine → END
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Literal

# LangGraph imports removed
# from langgraph.graph import END, START, StateGraph

from app.engine.multi_agent.subagents.tutor.state import TutorSubgraphState

logger = logging.getLogger(__name__)


async def analyze_node(state: Dict[str, Any]) -> dict:
    """Phase 1: Understand question, identify concepts, assess learner level."""
    query = state.get("query", "")
    context = state.get("context", {})

    # Determine pedagogical approach
    query_lower = query.lower()
    if any(kw in query_lower for kw in ["giải thích", "explain", "là gì", "what is"]):
        approach = "explain"
    elif any(kw in query_lower for kw in ["tại sao", "why", "vì sao"]):
        approach = "socratic"
    else:
        approach = "example"

    # Learner level from context
    level = context.get("learner_level", "intermediate")

    return {
        "phase": "analysis",
        "pedagogical_approach": approach,
        "learner_level": level,
        "concepts_identified": [],
    }


async def generate_node(state: Dict[str, Any]) -> dict:
    """Phase 2: Synthesize explanation using knowledge + tools if needed."""
    query = state.get("query", "")
    approach = state.get("pedagogical_approach", "explain")

    # Delegate to existing tutor agent for actual LLM generation
    response = f"[Tutor subgraph] Giải thích ({approach}): {query[:100]}"

    return {
        "phase": "generation",
        "explanation_draft": response,
    }


def should_refine(state: Dict[str, Any]) -> Literal["refine", "output"]:
    """Simple queries skip refinement."""
    query = state.get("query", "")
    if len(query) < 50:
        return "output"
    return "refine"


async def refine_node(state: Dict[str, Any]) -> dict:
    """Phase 3: Adapt to learner level, add examples, check understanding."""
    draft = state.get("explanation_draft", "")
    level = state.get("learner_level", "intermediate")

    refined = draft  # In full impl, LLM refines based on learner level

    return {
        "phase": "refinement",
        "final_response": refined,
        "agent_outputs": {"tutor": refined},
        "current_agent": "tutor_agent",
    }


async def output_node(state: Dict[str, Any]) -> dict:
    """Direct output without refinement (for simple queries)."""
    draft = state.get("explanation_draft", "")

    return {
        "phase": "output",
        "final_response": draft,
        "agent_outputs": {"tutor": draft},
        "current_agent": "tutor_agent",
    }


def build_tutor_subgraph():
    """DEPRECATED — LangGraph removed (De-LangGraphing Phase 3).

    Node functions (analyze_node, generate_node, etc.) are still available
    for direct async calls. Use WiiiRunner for orchestration.
    """
    raise RuntimeError(
        "build_tutor_subgraph() is deprecated (De-LangGraphing Phase 3). "
        "Use node functions directly or via WiiiRunner."
    )
