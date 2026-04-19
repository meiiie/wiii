# OpenAI Agents SDK: Routing & Handoff Architecture Research

**Date**: 2026-04-19
**Repository**: https://github.com/openai/openai-agents-python
**Purpose**: Understand OpenAI's agent routing/handoff patterns and extract applicable improvements for Wiii's multi-agent system

---

## 1. Architecture Overview

The OpenAI Agents SDK is a lightweight Python framework for building multi-agent LLM workflows. It is **provider-agnostic** -- works with OpenAI Responses API, Chat Completions API, and 100+ other LLMs via integrations.

### Core Abstractions

| Concept | Description |
|---------|-------------|
| **Agent** | An LLM configured with `instructions`, `tools`, `handoffs`, `guardrails`, `output_type`, `hooks` |
| **Handoff** | Agent-to-agent delegation where the receiving agent takes over the conversation |
| **Runner** | Orchestrator that executes the agent loop (LLM call -> process tool calls/handoffs -> continue or stop) |
| **Guardrail** | Safety check that can halt execution (`tripwire_triggered=True`) |
| **Context** | Dependency injection object (`RunContextWrapper`) passed to tools, handoffs, guardrails |
| **Hooks** | Lifecycle callbacks (on_agent_start/end, on_handoff, on_tool_start/end, on_llm_start/end) |

### Agent Loop Flow

```
Runner.run(agent, input)
  |
  v
[Loop until max_turns or final_output]
  |
  +---> LLM call (with instructions + tools + handoffs as tools)
  |
  +---> Process response:
  |       - text output -> return if output_type matches
  |       - tool calls -> execute tools, append to history, continue loop
  |       - handoff call -> switch to target agent, continue loop
  |
  +---> Check output guardrails (last agent only)
```

### Key Files

```
src/agents/
  agent.py          # Agent/AgentBase dataclasses, as_tool() method
  handoffs/
    __init__.py     # Handoff dataclass, handoff() factory, HandoffInputData
  guardrail.py      # InputGuardrail, OutputGuardrail, ToolGuardrail
  run.py            # Runner class (~92KB, orchestrates the loop)
  run_config.py     # RunConfig with handoff filters, nesting config
  lifecycle.py      # RunHooks, AgentHooks (lifecycle callbacks)
  items.py          # Typed message/event items
  result.py         # RunResult, RunResultBase
```

---

## 2. Key Design Patterns

### Pattern 1: LLM-Driven Routing via Tool Descriptions

**This is the most important insight.** OpenAI does NOT use a separate routing LLM, keyword matching, or structured output classification for routing. Instead:

- Each agent has a `handoff_description` field
- Handoffs are presented to the LLM as tools named `transfer_to_{agent_name}`
- The default tool description is: `"Handoff to the {agent.name} agent to handle the request. {agent.handoff_description}"`
- The LLM itself decides which handoff tool to invoke based on the tool name + description
- **No knowledge-aware routing exists.** There is no concept of checking what documents or knowledge an agent has access to before routing.

```python
# From handoffs/__init__.py
default_tool_name = transform_string_function_style(f"transfer_to_{agent.name}")
default_tool_description = (
    f"Handoff to the {agent.name} agent to handle the request. "
    f"{agent.handoff_description or ''}"
)
```

**Why this matters**: The LLM reads the `handoff_description` and decides which agent to transfer to. This is pure "LLM-as-router" -- the routing intelligence comes entirely from the LLM's understanding of the tool descriptions and the conversation context.

### Pattern 2: Two Multi-Agent Patterns

#### Handoff Pattern (Decentralized)
- Agent A decides to hand off to Agent B
- Agent B receives full conversation history
- Agent B is now in control and may hand off to Agent C
- The Runner loops: each agent runs until it produces output or hands off

#### Manager Pattern (Centralized)
- A central orchestrator agent calls specialist agents as **tools** (via `agent.as_tool()`)
- The orchestrator retains conversation control
- Specialists return results but do NOT take over the conversation
- Better for parallel execution and when you need aggregation

```python
# Manager pattern example from docs
orchestrator = Agent(
    name="orchestrator",
    instructions="Route to the right specialist",
    tools=[
        spanish_agent.as_tool(tool_name="translate_to_spanish", tool_description="..."),
        french_agent.as_tool(tool_name="translate_to_french", tool_description="..."),
    ],
)
```

### Pattern 3: Guardrails (Safety Layer)

Three types of guardrails with different scoping:

| Type | When | Scope | Behavior |
|------|------|-------|----------|
| **Input** | Before first agent runs | First agent only | Parallel or blocking, can set tripwire |
| **Output** | After last agent completes | Last agent only | Can set tripwire to halt |
| **Tool** | Before every function tool call | Every agent | Can approve/deny/modify |

**Tripwire pattern**: When `tripwire_triggered=True`, a `GuardrailTripwireTriggered` exception is raised and execution halts immediately. This is a fail-fast safety mechanism.

**Parallel vs Blocking input guardrails**:
- `run_in_parallel=True` (default): Guardrail runs alongside the agent. If tripwire fires, the agent is interrupted.
- `run_in_parallel=False`: Guardrail must complete before the agent starts. Safer but adds latency.

### Pattern 4: Input Filters (Conversation Transformation)

When a handoff occurs, the receiving agent gets the conversation history. But you might not want to pass everything:

```python
# HandoffInputFilter transforms history before passing to next agent
def my_filter(handoff_input_data: HandoffInputData) -> HandoffInputData:
    # Remove tool calls/results, keep only message text
    return HandoffInputData(
        input_history=...,     # Previous turns
        pre_handoff_items=..., # Items from before this handoff
        new_items=...,         # New items since last turn
    )
```

Built-in filters:
- `handoff_filters.remove_all_tools` -- strips all tool calls/results from history
- Custom filters can summarize, truncate, or transform history

### Pattern 5: Dynamic Agent Configuration

```python
# Dynamic instructions -- computed at runtime
def dynamic_instructions(ctx: RunContextWrapper, agent: Agent) -> str:
    return f"You are helping {ctx.context.user_name}..."

agent = Agent(name="helper", instructions=dynamic_instructions)

# Dynamic handoff enable/disable
def should_enable(ctx: RunContextWrapper, agent: AgentBase) -> bool:
    return ctx.context.feature_enabled  # Runtime decision

handoff_obj = handoff(target_agent, is_enabled=should_enable)
```

### Pattern 6: Lifecycle Hooks

```python
hooks = RunHooks(
    on_agent_start=lambda ctx, agent: log(f"Starting {agent.name}"),
    on_agent_end=lambda ctx, agent, output: log(f"Finished {agent.name}"),
    on_handoff=lambda ctx, from_agent, to_agent: log(f"Handoff: {from_agent.name} -> {to_agent.name}"),
    on_tool_start=lambda ctx, agent, tool: log(f"Tool: {tool.name}"),
    on_tool_end=lambda ctx, agent, tool, result: log(f"Tool result: {result}"),
)
```

Hooks are also available per-agent via `AgentHooks` -- allows agent-specific lifecycle callbacks.

---

## 3. Answers to Specific Questions

### Q: Knowledge-Aware Routing?

**No.** OpenAI's framework has zero concept of checking what knowledge an agent has before routing to it. There is no:
- Document/capability registry
- Knowledge store inspection
- Semantic capability matching
- Tool inventory analysis for routing decisions

Routing is entirely driven by the LLM reading `handoff_description` text. The assumption is that the developer writes good descriptions that accurately represent what each agent can do.

### Q: Input Preprocessing / Pre-Routing Analysis?

**Minimal.** There are two mechanisms:

1. **Input guardrails** -- These run BEFORE the first agent, but they are for safety/relevance checks (tripwire pattern), not for routing decisions.

2. **The LLM call itself** -- The "pre-routing analysis" IS the LLM call. The LLM reads the instructions + tool descriptions (including handoff tools) and decides. There is no separate classification step.

OpenAI explicitly avoids a separate routing/classification step. The philosophy is: let the LLM figure it out in one shot.

### Q: Best Practices for Multi-Agent Routing?

From official documentation:

1. **Use Manager pattern for orchestration** -- A single orchestrator that calls specialists as tools gives more control and parallelism
2. **Use Handoff pattern for delegation** -- When you want an agent to fully take over a conversation
3. **Write good `handoff_description`** -- This is the ONLY metadata the LLM uses for routing decisions. Be specific and clear
4. **Use input filters** -- Control what conversation history the receiving agent sees (prevent context pollution)
5. **Use guardrails for safety** -- Input guardrails for first-agent safety, output guardrails for last-agent safety, tool guardrails for every tool call
6. **Dynamic instructions for personalization** -- Compute instructions at runtime based on context
7. **`RECOMMENDED_PROMPT_PREFIX`** -- A prefix string you should add to your orchestrator agent's instructions to improve handoff accuracy

---

## 4. Comparison: OpenAI Agents SDK vs Wiii Supervisor

### Architecture Comparison

| Aspect | OpenAI Agents SDK | Wiii (Current) |
|--------|------------------|----------------|
| **Routing mechanism** | LLM chooses handoff tool by description | LLM structured output (`RoutingDecision`) + rule-based fallback |
| **Routing model** | Same model as the agent (no separate routing LLM) | Dedicated supervisor LLM (separate from agent LLMs) |
| **Agent selection** | `handoff_description` text as tool description | `RoutingDecision` structured output with intent + confidence |
| **Fallback** | LLM simply picks a tool | Rule-based fallback (4 guardrails: social, personal, domain, default) |
| **Conversation transfer** | Full history transferred (filterable) | State dict passed via LangGraph state |
| **Safety** | Guardrails (input/output/tool, tripwire pattern) | Guardian agent (entry point, fail-open) |
| **Orchestration** | Runner loop (max_turns) | LangGraph graph (node-based) |
| **Knowledge awareness** | None | Domain keyword matching (via `_get_domain_keywords`) |
| **Dynamic config** | `is_enabled` callable, dynamic instructions | Feature flags + runtime hints |
| **Hooks/lifecycle** | `RunHooks` + `AgentHooks` (7 callbacks) | Graph event bus + streaming queue |

### What Wiii Already Does Better

1. **Domain-aware routing**: Wiii's `DomainRouter` + keyword matching is more sophisticated than OpenAI's text-only `handoff_description`. Wiii can route based on domain plugins, organization context, and skill handbooks.

2. **Confidence gating**: Wiii's `CONFIDENCE_THRESHOLD` with rule-based fallback is a safety net that OpenAI lacks. If the LLM is uncertain, Wiii has a deterministic fallback.

3. **Rule-based guardrails**: Wiii's 4-rule fallback (`_rule_based_route`) catches edge cases that a pure LLM approach might miss.

4. **Organization context**: Wiii routes considering multi-tenant org boundaries, domain filtering, and persona overlays. OpenAI has no multi-tenancy concept.

5. **Rich agent types**: Wiii has 7 specialized agents (RAG, Tutor, Memory, Direct, Code Studio, Product Search, Colleague) vs OpenAI's generic Agent class.

### What Wiii Can Learn

#### L1. Handoff Description Pattern (Low Effort, High Value)

OpenAI's key insight: the LLM routes based on a **short text description** of what each agent does. Wiii's `RoutingDecision` structured output asks the LLM to pick from intent categories (lookup, learning, personal, social, off_topic, web_search), but the LLM doesn't see a natural language description of each agent's capabilities.

**Recommendation**: Add `agent_description` strings to each agent's configuration and include them in the supervisor routing prompt. This gives the LLM richer context for routing decisions.

```python
# Example: in supervisor_contract.py or agent_config.py
AGENT_ROUTING_DESCRIPTIONS = {
    "rag_agent": "Handles factual lookup queries about maritime regulations, COLREGs, SOLAS, MARPOL. Has access to a knowledge base with 10,000+ documents. Best for 'what does rule X say?' type questions.",
    "tutor_agent": "Handles teaching and explanation requests. Uses pedagogical approach with step-by-step explanations. Best for 'explain how X works' or 'teach me about Y' type questions.",
    "memory_agent": "Handles personal context, user preferences, and cross-session memory. Best for 'remember that...' or 'what did we discuss about...' type questions.",
    # ...
}
```

#### L2. Input Filter Pattern (Medium Effort, High Value)

OpenAI's `HandoffInputFilter` allows transforming conversation history before passing it to the receiving agent. Wiii's agents all see the full state dict via LangGraph, which can be noisy.

**Recommendation**: Implement per-agent context filtering. When routing to `memory_agent`, include full conversation history. When routing to `rag_agent`, include only the current query + recent turns. When routing to `tutor_agent`, include the query + pedagogical context.

#### L3. Tripwire Guardrails (Low Effort, Medium Value)

OpenAI's `tripwire_triggered` pattern is elegant for safety. Wiii's `GuardianAgent` is "fail-open" -- if it errors, the request passes through. A tripwire pattern would be "fail-closed" for specific scenarios.

**Recommendation**: Add a configurable `fail_closed` mode to GuardianAgent for specific checks (e.g., content policy violations should fail-closed, not fail-open).

#### L4. Agent-as-Tool Pattern (Low Effort, Medium Value)

OpenAI's `agent.as_tool()` pattern allows using agents as tools within another agent. This is useful for the "Manager pattern" where an orchestrator calls multiple specialists and aggregates results.

**Recommendation**: For Wiii's `DIRECT` agent, which already has 8 bound tools, consider making some agents callable as tools (e.g., RAG agent as a tool for the Direct agent to use when it needs knowledge). This enables composition without routing back through the supervisor.

#### L5. Lifecycle Hooks (Medium Effort, Low-Medium Value)

OpenAI's `RunHooks` provides structured callbacks for the entire agent lifecycle. Wiii has graph event bus + streaming queue, but they are ad-hoc.

**Recommendation**: Formalize agent lifecycle callbacks into a `RunHooks`-like interface. This would make observability, logging, and debugging easier. Currently scattered across multiple modules.

#### L6. Dynamic Handoff Enable/Disable (Trivial Effort, Low Value)

OpenAI's `is_enabled` callable on handoffs allows runtime decisions about whether a handoff is available. Wiii already has feature flags, but they are not per-request dynamic.

**Recommendation**: Consider per-request agent availability (e.g., disable `product_search_agent` when no search platforms are configured, disable `code_studio_agent` when no tools are available).

---

## 5. Summary

### Key Takeaways

1. **OpenAI's approach is radically simple**: No separate routing model, no structured output classification, no knowledge awareness. Just "present agents as tools with descriptions, let the LLM decide." This works because modern LLMs are good at understanding tool descriptions.

2. **Wiii's approach is more robust**: Confidence gating, rule-based fallbacks, domain awareness, and org filtering make Wiii's routing more reliable in production. The complexity is justified by the multi-tenant, multi-domain nature of the system.

3. **The best improvement is the simplest**: Adding `handoff_description`-style natural language descriptions of each agent's capabilities to the supervisor routing prompt would improve routing accuracy with minimal code change.

4. **Input filters are the most impactful architectural change**: Per-agent context filtering would reduce noise, improve agent performance, and reduce token usage.

5. **OpenAI's framework is a toolkit, not an architecture**: It provides primitives (Agent, Handoff, Guardrail, Runner) but doesn't prescribe how to combine them. Wiii's LangGraph-based architecture is more opinionated and more suitable for the complex multi-domain, multi-tenant use case.

### Priority Recommendations

| Priority | Recommendation | Effort | Impact |
|----------|---------------|--------|--------|
| **P0** | Add agent capability descriptions to supervisor routing prompt | Low | High |
| **P1** | Implement per-agent context filtering (input filter pattern) | Medium | High |
| **P2** | Add fail-closed mode to GuardianAgent | Low | Medium |
| **P3** | Formalize lifecycle hooks interface | Medium | Medium |
| **P4** | Agent-as-tool for Director agent composition | Medium | Medium |
| **P5** | Dynamic per-request agent enable/disable | Trivial | Low |
