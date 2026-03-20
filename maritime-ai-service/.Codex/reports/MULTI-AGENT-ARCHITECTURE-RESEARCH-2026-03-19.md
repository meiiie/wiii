# Multi-Agent Architecture Research: Merge vs Specialize (March 2026)

**Date:** 2026-03-19
**Scope:** Evidence-based analysis of how top AI platforms handle agent architecture
**Relevance:** Architecture decision for Wiii's multi-agent system (RAG/Tutor/Direct/Memory)

---

## Executive Summary

The 2026 SOTA consensus is **neither "merge everything" nor "keep everything separate."** It is **adaptive routing with complexity-gated agent activation.** Every top platform uses a single primary agent loop for simple queries, and selectively activates specialized agents/sub-agents only when complexity demands it. The key finding: **the number of agents is dynamic per request, not static.**

---

## 1. Claude Code / Anthropic

### Architecture: Single Agent Loop + On-Demand Sub-Agents

**Claude Code itself is a single-threaded agent loop** (codenamed nO) using the TAOR pattern (Think-Act-Observe-Repeat). It is NOT a multi-agent swarm internally. The core is one agent with tools (Read, Write, Execute, Connect), and Bash acts as the universal adapter.

**Sub-agent delegation** is supported but optional: the main loop can spawn a specialized sub-agent (planner, reviewer) via the `Agent` tool, let it run in isolation, and return results back to the parent. This is on-demand, not always-on.

**Agent Teams** (launched with Opus 4.6, Feb 2026): Multiple Claude Code instances can coordinate as a team. One session acts as team lead, spawning teammates. **Recommended limit: 3-4 subagents maximum.** More than that causes productivity drops from routing overhead.

**Anthropic's official guidance** (blog: "When to use multi-agent systems"):
- Multi-agent systems use **15x more tokens** than standard chat
- Agents use **4x more tokens** than chat interactions
- Three valid reasons for multi-agent: **(1) context pollution, (2) parallelizable tasks, (3) tool specialization (20+ tools degrades selection)**
- "Start with simple prompts, optimize them, and add multi-step agentic systems only when simpler solutions fall short"

**Key quote:** "Five well-designed tools outperform twenty overlapping ones. If you can't definitively say which tool to use in a given situation, neither can your agent."

### Verdict: ONE primary loop, sub-agents spawned on-demand for complexity.

---

## 2. OpenAI Codex / ChatGPT

### Architecture: Unified Core + Mode-Based Tool Activation

**ChatGPT Agent Mode** (2026) represents a **major consolidation.** OpenAI unified the previously separate Operator (web interaction) and Deep Research (analysis) capabilities into a single agent architecture. The unified system allows multiple tools to share state, enabling fluid transitions between browsing, analysis, and code execution in one environment.

**The Tools dropdown** exposes six modes from ONE underlying system: Agent Mode, Deep Research, Create Image, Study & Learn, Web Search, Canvas. These are **integrated tools within a single conversational flow**, not separate agents.

**Codex CLI/App**: Uses a single primary agent loop (the "App Server" protocol — Items, Turns, Threads). Subagents are spawned **only when explicitly requested or when tasks are highly parallel**. Three built-in roles: default, worker, explorer. Custom agents can be defined as TOML files.

**Key architecture principle:** "The App Server now powers every Codex experience (CLI, VS Code, web app) through a single, stable API." Codex only spawns a new agent when explicitly asked.

### Verdict: MERGED into unified architecture. Modes are tool configurations, not separate agents.

---

## 3. Grok 4.20 (xAI)

### Architecture: Complexity-Gated Multi-Agent Council

**4 agents** share the same ~3T-parameter MoE backbone:
- **Captain/Grok**: Coordinator, task decomposition, synthesis
- **Harper**: Research & facts, X firehose real-time search
- **Benjamin**: Math, code, logic, step-by-step verification
- **Lucas**: Creative framing, contrarian pressure

**Critical finding: NOT always all 4.**
- **Simple queries**: Bypass the council entirely, use single-pass Grok 4.1 (Fast mode)
- **xAI recommends Fast mode for 80% of daily queries**
- The router is a lightweight MoE-style gate trained to detect complexity
- Full 4-agent mode triggers only for complex, reasoning-heavy, multi-disciplinary tasks

**Grok 4.20 Heavy**: Scales to **16 specialized agents** for extreme-complexity research tasks ($30/month SuperGrok).

**Result**: Hallucination reduced 65% (12% to 4.2%) on complex queries via peer-review mechanism.

### Verdict: SELECTIVE activation. 80% of queries = 1 agent. 20% = 4 agents. Heavy = 16 agents.

---

## 4. Google Gemini

### Architecture: Tiered Routing + Research Sub-Agents

**For simple queries**: Single model call. Google's own routing strategy:
- **Flash-Lite**: Simple queries, classifications, short responses
- **Flash**: General-purpose (moderate code gen, summarization, chat)
- **Pro**: Complex reasoning, multi-step analysis

**For Deep Research**: Lead agent + sub-agents architecture. The orchestrator receives the query, creates a plan, breaks it into sub-tasks, delegates to multiple "web search" sub-agents in parallel. Sub-agents are typically search-focused, not reasoning-focused.

**Google Research paper** ("Towards a Science of Scaling Agent Systems," 180 configurations tested):
- **Parallelizable tasks**: Centralized coordination improved performance by 80.9%
- **Sequential reasoning tasks**: Every multi-agent variant DEGRADED performance by 39-70%
- Independent agents amplify errors **17x**; centralized orchestration limits it to **4.4x**
- **Predictive model**: 87% accuracy in choosing optimal strategy
- **Tool-coordination trade-off**: More tools + more agents = disproportionate overhead
- **Capability saturation**: Adding agents yields diminishing returns past a threshold

### Verdict: SINGLE agent for simple queries. Multi-agent ONLY for parallel research tasks. Research proves multi-agent HURTS sequential reasoning.

---

## 5. Cursor

### Architecture: Planner-Worker Separation (NOT Merged)

Cursor explicitly **keeps planners and workers separate** with three distinct agent types:

1. **Root Planners**: Own entire scope, deliver targeted tasks. **Perform NO coding themselves.**
2. **Sub-Planners**: Spawned recursively for narrow slices when root planner identifies subdivisions.
3. **Workers**: Execute in complete isolation (own git worktrees), no inter-worker communication. Write comprehensive handoffs on completion.

**Scale achievement**: ~1,000 commits/hour across 10M tool calls, several hundred concurrent workers building a browser from scratch in one week.

**Key design**: Isolation is the principle. Each agent runs in its own worktree. Changes merge back to working branch on completion.

### Verdict: SEPARATE roles, but this is a code generation context where parallelism is natural. Not comparable to conversational AI routing.

---

## 6. Vercel v0

### Architecture: Composite Model = One Agent, Multiple Specialized Pipelines

v0 is effectively **one agent** with a composite internal architecture:
- **Base LLM**: State-of-the-art frontier model (swappable)
- **RAG pipeline**: Documentation, UI examples, project sources, Vercel knowledge
- **Quick Edit pipeline**: Optimized for small changes
- **AutoFix model**: Custom streaming post-processing for error correction
- **LLM Suspense**: Streaming manipulation layer

This is a **single agent with multi-stage processing**, not separate agents. The "composite model" decouples specialized pieces from the base model so they can be upgraded independently.

**Key insight**: "As base models improve, the architecture allows quick upgrades to the latest frontier model while keeping the rest of the architecture stable."

### Verdict: ONE agent with pipeline stages. NOT multi-agent. Specialization happens at the pipeline level, not the agent level.

---

## 7. Quantitative Evidence Summary

| Platform | Simple Query | Complex Query | Architecture |
|----------|-------------|---------------|--------------|
| Claude Code | 1 agent loop | 1 + sub-agents on demand | Single loop + delegation |
| ChatGPT | 1 unified agent | 1 + tools activated | Merged (2026 consolidation) |
| Grok 4.20 | 1 agent (Fast) | 4 agents (council) | Complexity-gated |
| Gemini | 1 model (Flash-Lite/Flash) | Lead + sub-agents | Tiered routing |
| Cursor | 1 planner | N planners + N workers | Separate (code-specific) |
| Vercel v0 | 1 composite | 1 composite | Pipeline stages, not agents |

**Token cost of multi-agent** (Anthropic data):
- Chat: 1x tokens
- Single agent: 4x tokens
- Multi-agent: 15x tokens

**Google Research findings** (180 configurations):
- Multi-agent on parallelizable tasks: +80.9% performance
- Multi-agent on sequential tasks: -39% to -70% performance
- Error amplification: 17x (independent) vs 4.4x (centralized orchestrator)

---

## 8. KEY QUESTION: What Should Wiii Do?

### Current Wiii Architecture
- **Supervisor** routes to: RAG Agent, Tutor Agent, Direct Response, Memory Agent
- LLM-first routing via `RoutingDecision` structured output
- 4 separate specialized agents with separate prompts and tool sets

### Analysis Against Each Option

#### Option A: Keep 4 Separate Agents with Supervisor Routing
**Pros:**
- Aligns with Anthropic's "tool specialization" justification (each agent has focused tools)
- Context isolation prevents pollution between RAG retrieval context and memory context
- Proven architecture in production

**Cons:**
- Supervisor routing adds 1 LLM call overhead on every request (~500ms-2s)
- 4 agents = likely 15x token cost vs direct response
- Google research: sequential reasoning (most chat queries) DEGRADES with multi-agent
- Most queries are simple and don't need 4-agent coordination

#### Option B: Merge into 1-2 Universal Agents
**Pros:**
- Eliminates supervisor routing latency
- Matches ChatGPT 2026 approach (unified with tool activation)
- Lower token cost per request
- Matches Vercel v0 approach (one agent, pipeline stages)

**Cons:**
- Risk of context pollution (RAG retrieval context mixed with memory context)
- 20+ tools in one agent degrades tool selection (Anthropic data)
- Loses specialized prompt engineering per agent type

#### Option C: Adaptive Complexity-Gated Architecture (RECOMMENDED)

**This is what EVERY top platform actually does in 2026:**

1. **Single primary agent** handles 80% of requests directly (like Grok Fast mode, Gemini Flash, Claude Code main loop)
2. **Complexity gate** (lightweight classifier or LLM judge) determines if specialization is needed
3. **Specialized sub-agents** activated ONLY when the gate triggers (like Grok council, Gemini Deep Research sub-agents, Claude Code Agent tool)
4. **Pipeline specialization** replaces agent specialization where possible (like v0 composite model)

### Concrete Recommendation for Wiii

```
User Query
    │
    ▼
┌─────────────────────────────┐
│  Complexity Gate             │  (lightweight: keyword + short LLM classify)
│  - Simple? → Primary Agent   │  (80% of queries)
│  - Needs RAG? → RAG Pipeline │  (tool, not separate agent)
│  - Needs teaching? → Tutor   │  (sub-agent with pedagogical prompt)
│  - Personal? → Memory lookup │  (tool call, not separate agent)
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│  Primary Agent               │  (ONE agent with 8-12 well-designed tools)
│  Tools:                      │
│  - rag_search (retrieval)    │  ← Was RAG Agent, now a tool
│  - memory_lookup             │  ← Was Memory Agent, now a tool
│  - web_search                │
│  - product_search            │
│  - visual_create             │
│  - ... (domain tools)        │
└─────────────────────────────┘
    │
    ▼  (only when complexity gate fires)
┌─────────────────────────────┐
│  Tutor Sub-Agent             │  (separate context for teaching)
│  - Different system prompt   │
│  - Pedagogical tools         │
│  - Socratic method           │
└─────────────────────────────┘
```

**Why this is SOTA:**
1. **80% of queries** go through ONE agent = fast, cheap, simple
2. **RAG becomes a tool** (like every other platform does retrieval — not a separate agent)
3. **Memory becomes a tool** (lookup + store, no separate agent needed)
4. **Tutor stays separate** because it has fundamentally different system prompt + behavior (Anthropic's "specialization" justification — different system prompts/expertise)
5. **Supervisor routing call eliminated** for simple queries (saves 500ms-2s + tokens)
6. **Matches proven patterns**: ChatGPT unified tools, Grok complexity-gating, Claude Code single-loop-with-delegation, v0 composite pipeline

### Migration Path

**Phase 1**: Convert Memory Agent to a tool (memory_lookup, memory_store) callable by Primary Agent
**Phase 2**: Convert RAG Agent to a RAG tool pipeline (search → grade → generate) callable by Primary Agent
**Phase 3**: Keep Tutor as sub-agent, activated by complexity gate when query is clearly educational
**Phase 4**: Replace Supervisor with lightweight complexity gate (cheaper than full LLM routing call)
**Phase 5**: Keep Direct Response as the Primary Agent's default behavior

**Net result**: From 5 LLM calls (supervisor + agent + grader + synthesizer + ...) to 1-2 LLM calls for 80% of queries.

---

## Sources

- [When to use multi-agent systems (and when not to) - Anthropic/Claude](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them)
- [How we built our multi-agent research system - Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Building effective agents - Anthropic](https://www.anthropic.com/research/building-effective-agents)
- [How Claude Code works - Claude Code Docs](https://code.claude.com/docs/en/how-claude-code-works)
- [Claude Code: Behind-the-scenes of the master agent loop](https://blog.promptlayer.com/claude-code-behind-the-scenes-of-the-master-agent-loop/)
- [Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams)
- [Introducing the Codex app - OpenAI](https://openai.com/index/introducing-the-codex-app/)
- [Unrolling the Codex agent loop - OpenAI](https://openai.com/index/unrolling-the-codex-agent-loop/)
- [Codex Subagents - OpenAI Developers](https://developers.openai.com/codex/subagents)
- [Introducing ChatGPT agent - OpenAI](https://openai.com/index/introducing-chatgpt-agent/)
- [ChatGPT Tools interface: six modes](https://www.datastudios.org/post/chatgpt-and-the-new-tools-interface-six-modes-to-access-agent-research-study-and-creation)
- [OpenAI Publishes Codex App Server Architecture - InfoQ](https://www.infoq.com/news/2026/02/opanai-codex-app-server/)
- [How the xAI Grok 4.20 Agents Work - NextBigFuture](https://www.nextbigfuture.com/2026/02/how-the-xai-grok-4-20-agents-work.html)
- [Grok 4.20 Agents Explained - AdwaitX](https://www.adwaitx.com/grok-4-20-agents-harper-benjamin-lucas/)
- [Grok 4.20 Heavy: 16-Agent System](https://aitoolland.com/grok-4-20-heavy-guide/)
- [Grok 4.20 Beta Explained - BuildFastWithAI](https://www.buildfastwithai.com/blogs/grok-4-20-beta-explained-2026)
- [Towards a Science of Scaling Agent Systems - Google Research](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/)
- [Google Publishes Scaling Principles for Agentic Architectures - InfoQ](https://www.infoq.com/news/2026/03/google-multi-agent/)
- [Scaling Agent Systems paper - arXiv](https://arxiv.org/abs/2512.08296)
- [Gemini Deep Research Agent API docs](https://ai.google.dev/gemini-api/docs/deep-research)
- [Cursor Agent Best Practices](https://cursor.com/blog/agent-best-practices)
- [Cursor Scaling Agents](https://cursor.com/blog/scaling-agents)
- [How Cursor Divided AI Agents Into Planners And Workers](https://officechai.com/ai/how-cursor-divided-ai-agents-into-planners-and-workers-to-build-a-browser-in-a-week/)
- [Cursor Background Agents guide](https://ameany.io/blog/cursor-background-agents/)
- [Introducing the v0 composite model family - Vercel](https://vercel.com/blog/v0-composite-model-family)
- [How we made v0 an effective coding agent - Vercel](https://vercel.com/blog/how-we-made-v0-an-effective-coding-agent)
- [Choosing the Right Multi-Agent Architecture - LangChain](https://blog.langchain.com/choosing-the-right-multi-agent-architecture/)
- [Optimizing Latency and Cost in Multi-Agent Systems](https://www.hockeystack.com/applied-ai/optimizing-latency-and-cost-in-multi-agent-systems)
- [Multi-Agent Supervisor Architecture - Databricks](https://www.databricks.com/blog/multi-agent-supervisor-architecture-orchestrating-enterprise-ai-scale)
