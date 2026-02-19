"""
Agent State Schema - Phase 8.1

Shared state between all agents in the multi-agent system.
"""

from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict, total=False):
    """
    Shared state between agents.
    
    All agents read and write to this state.
    LangGraph manages state transitions.
    """
    # Input
    query: str
    user_id: str
    session_id: str
    
    # Context
    context: Dict[str, Any]
    user_context: Dict[str, Any]
    learning_context: Dict[str, Any]
    
    # Messages
    messages: List[Dict[str, Any]]
    
    # Routing
    current_agent: str
    next_agent: str
    
    # Agent outputs
    agent_outputs: Dict[str, Any]
    rag_output: str
    tutor_output: str
    memory_output: str
    
    # Quality
    grader_score: float
    grader_feedback: str
    
    # Final
    final_response: str
    sources: List[Dict[str, Any]]
    tools_used: List[Dict[str, Any]]  # SOTA: Track tool usage for transparency
    
    # Metadata
    iteration: int
    max_iterations: int
    error: Optional[str]
    
    # CHỈ THỊ SỐ 28: SOTA Reasoning Trace for API transparency
    reasoning_trace: Optional[Any]  # ReasoningTrace from CorrectiveRAG
    thinking_content: Optional[str]  # Structured prose summary (fallback)
    
    # CHỈ THỊ SỐ 29: Native thinking from Gemini (SOTA 2025)
    thinking: Optional[str]  # Native Gemini thinking (priority)
    
    # CHỈ THỊ SỐ 30: Trace ID for graph-level universal tracing
    # Actual ReasoningTracer stored in module-level dict (not in state) to avoid
    # msgpack serialization failures with LangGraph checkpoint
    _trace_id: Optional[str]  # Key into graph._TRACERS dict

    # Guardian Agent (SOTA 2026: Defense-in-depth Layer 2)
    guardian_passed: Optional[bool]  # Whether Guardian allowed the message through

    # Domain Plugin System (Wiii)
    domain_id: str  # Active domain for this request (e.g. "maritime")
    domain_config: Dict[str, Any]  # Domain routing config (keywords, descriptions)
    skill_context: Optional[str]  # Activated SKILL.md content (progressive disclosure)

    # Agentic Loop Tool Events (Sprint 58: Enhanced Streaming)
    # Tool calls from agentic loop for SSE streaming
    tool_call_events: Optional[List[Dict[str, Any]]]

    # Adaptive Thinking Effort (Sprint 66: per-request thinking control)
    # Maps to provider params: Claude effort, OpenAI reasoning_effort, Gemini thinking_level
    thinking_effort: Optional[str]  # "low" | "medium" | "high" | "max"

    # Sprint 69: Event bus ID for intra-node real-time streaming
    # String key into module-level _EVENT_QUEUES dict (avoids serialization issues)
    _event_bus_id: Optional[str]

    # Sprint 71: SOTA Routing Metadata for observability
    # {intent, confidence, reasoning, method} from supervisor routing
    routing_metadata: Optional[Dict[str, Any]]

    # Sprint 74: Answer dedup — tutor signals that answer was already streamed
    # via event bus (as thinking_delta or answer_delta), so graph_streaming
    # should skip post-hoc re-emission
    _answer_streamed_via_bus: Optional[bool]

    # Sprint 80b: Domain notice — gentle UI indicator when answer is outside active domain
    domain_notice: Optional[str]


