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
    thinking_lifecycle: Optional[Dict[str, Any]]  # Serialized lifecycle authority for visible thinking
    
    # CHỈ THỊ SỐ 29: Native thinking from Gemini (SOTA 2025)
    thinking: Optional[str]  # Native Gemini thinking (priority)
    _public_thinking_fragments: Optional[List[str]]  # Visible interval thinking fragments captured during the turn
    _thinking_trajectory: Optional[Dict[str, Any]]  # Internal thought trajectory authority
    
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
    capability_context: Optional[str]  # Runtime capability handbook summary for this turn

    # Agentic Loop Tool Events (Sprint 58: Enhanced Streaming)
    # Tool calls from agentic loop for SSE streaming
    tool_call_events: Optional[List[Dict[str, Any]]]

    # Adaptive Thinking Effort (Sprint 66: per-request thinking control)
    # Maps to provider params: Claude effort, OpenAI reasoning_effort, Gemini thinking_level
    thinking_effort: Optional[str]  # "low" | "medium" | "high" | "max"

    # Per-Request Provider Selection: user-chosen LLM provider for this turn
    provider: Optional[str]  # "auto" | "google" | "zhipu" | None (= auto)
    model: Optional[str]  # Effective model selected for this turn when known

    # Runtime execution metadata (must live in AgentState so LangGraph preserves it)
    _execution_provider: Optional[str]  # Concrete provider that actually answered
    _execution_model: Optional[str]  # Concrete model that actually answered
    _llm_failover_events: Optional[List[Dict[str, Any]]]  # Structured failover trail for this turn

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

    # Sprint 160: Multi-Tenant Data Isolation — org_id threaded through pipeline
    organization_id: Optional[str]

    # Sprint 189b: Evidence images from document retrieval (page thumbnails)
    evidence_images: Optional[List[Dict[str, Any]]]

    # Sprint 200: User-uploaded images for visual product search
    images: Optional[List[Dict[str, Any]]]

    # Sprint 203: Conversation phase for natural behavior (OpenClaw heartbeat-inspired)
    conversation_phase: Optional[str]  # "opening" | "engaged" | "deep" | "closing"

    # Sprint 222: Universal Host Context Engine
    host_context: Optional[Dict[str, Any]]  # Raw HostContext from request
    host_capabilities: Optional[Dict[str, Any]]  # Raw HostCapabilities from request
    host_action_feedback: Optional[Dict[str, Any]]  # Recent host action results from request
    host_context_prompt: Optional[str]  # Formatted prompt block (graph-level injection)
    host_capabilities_prompt: Optional[str]  # Host capability/action block
    host_session: Optional[Dict[str, Any]]  # HostSessionV1 runtime overlay for this turn
    host_session_prompt: Optional[str]  # Formatted host-session block for prompts
    operator_session: Optional[Dict[str, Any]]  # OperatorSessionV1 metadata
    operator_context_prompt: Optional[str]  # Formatted operator block for prompts
    widget_feedback_prompt: Optional[str]  # Formatted widget/app result context
    living_context_prompt: Optional[str]  # Formatted LivingContextBlockV1 prompt
    memory_block_context: Optional[str]  # MemoryBlockV1 section extracted for prompt reuse
    reasoning_policy: Optional[Dict[str, Any]]  # ReasoningPolicyV1 metadata for this turn

    # Sprint 163 Phase 4: Parallel dispatch + aggregator
    subagent_reports: Optional[List[Dict[str, Any]]]  # List[SubagentReport.model_dump()]
    _aggregator_action: Optional[str]  # "synthesize"|"use_best"|"re_route"|"escalate"
    _aggregator_reasoning: Optional[str]
    _reroute_count: Optional[int]
    _parallel_targets: Optional[List[str]]  # Agent names for parallel dispatch
