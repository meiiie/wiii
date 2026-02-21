"""Tutor subgraph state — pedagogical phase tracking."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class TutorSubgraphState(TypedDict, total=False):
    """State for the Tutor subgraph.

    Three phases: analysis → generation → refinement.
    Private fields track pedagogical approach and intermediate results.
    """

    # ── Input (shared with parent AgentState) ─────────────────────────
    query: str
    context: Dict[str, Any]
    user_id: str
    session_id: str
    domain_id: str
    organization_id: Optional[str]
    _event_bus_id: Optional[str]
    _trace_id: Optional[str]
    thinking_effort: Optional[str]

    # ── Subgraph-private: pedagogical state ───────────────────────────
    phase: str  # "analysis" | "generation" | "refinement"
    pedagogical_approach: Optional[str]  # "explain" | "socratic" | "example"
    learner_level: Optional[str]  # "beginner" | "intermediate" | "advanced"
    concepts_identified: List[str]
    explanation_draft: str

    # ── Output (flows back to parent AgentState) ──────────────────────
    final_response: str
    agent_outputs: Dict[str, Any]
    current_agent: str
    tools_used: List[Dict[str, Any]]
    thinking: Optional[str]
    _answer_streamed_via_bus: Optional[bool]
