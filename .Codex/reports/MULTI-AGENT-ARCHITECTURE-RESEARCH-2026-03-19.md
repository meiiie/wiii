# Multi-Agent Architecture Research: Top AI Platforms (March 2026)

**Date:** 2026-03-19
**Type:** Research Report
**Status:** COMPLETE

---

## Executive Summary

As of March 2026, **every major AI platform uses some form of multi-agent or multi-component architecture**. However, the implementations vary dramatically:

| Pattern | Platforms |
|---------|-----------|
| **Native multi-agent (shared backbone)** | Grok 4.20 (4 agents on shared MoE weights) |
| **Orchestrator + parallel subagents** | Claude Code, OpenAI Codex, Gemini Deep Research, Anthropic Research |
| **Composite model family (specialized models)** | Vercel v0 (base + AutoFix + Quick Edit) |
| **Recursive planner-worker** | Cursor (planners spawn sub-planners + workers) |
| **Parallel cascade agents** | Windsurf (5 parallel Cascade agents via git worktrees) |
| **Single model + tools/modes** | ChatGPT (Canvas, Agent Mode, Deep Research as modes) |

**No major consumer platform uses LangGraph internally.** LangGraph is used by enterprise teams (LinkedIn, Uber, Klarna, Elastic) building their own agent systems, not by the platforms themselves. The top platforms all built custom orchestration.

---

## 1. Grok (xAI) — Grok 4.20 Beta

### Architecture: Native 4-Agent Collaboration on Shared MoE Backbone

Grok 4.20 Beta (shipped February 17, 2026) introduced a **native, inference-time multi-agent system baked directly into the forward pass**. This is NOT an external framework — the agents are distinct specialized sub-models running on a shared Mixture-of-Experts (MoE) backbone (~3T parameters).

#### The Four Agents

| Agent | Role | Specialization |
|-------|------|----------------|
| **Grok (Captain)** | Coordinator/Aggregator | Task decomposition, strategy, conflict resolution, final synthesis |
| **Harper** | Research & Facts | Real-time search, X firehose (~68M tweets/day), fact-verification |
| **Benjamin** | Math/Code/Logic | Step-by-step reasoning, numerical verification, proofs, code |
| **Lucas** | Creative & Balance | Divergent thinking, blind-spot detection, writing/UX optimization |

#### Workflow

1. Prompt analyzed once, broken into sub-tasks
2. All 4 agents receive full context + specialized lens, generate initial analyses **in parallel**
3. Structured internal debate rounds: Harper grounds claims, Benjamin checks logic, Lucas spots biases
4. Iterative correction until consensus or flagged uncertainties
5. Grok (Captain) synthesizes final response

#### Key Technical Details

- Trained on Colossus cluster (200,000 GPUs, expanding to 1M)
- Adds only **1.5-2.5x latency** vs single Grok 4.1 pass (NOT 4x)
- **65% reduction in hallucinations** (from ~12% to ~4.2%)
- Activates automatically on sufficiently complex queries — NOT user-orchestrated

#### DeepSearch

Separate research **mode** (not a separate agent). Performs exhaustive multi-source web search, consults X publications, synthesizes into structured report. Uses the same multi-agent backbone.

#### Think Mode

Reasoning **mode** — shows step-by-step reasoning chain before final answer. Same model, different inference behavior (extended chain-of-thought).

---

## 2. Claude Code (Anthropic)

### Architecture: Orchestrator + Subagent Spawning

Claude Code uses a **parent agent that spawns subagents** via the Agent tool (previously called Task tool).

#### How Subagents Work

- Each subagent gets a **fresh context window** (no parent conversation history)
- The **only channel** from parent to subagent is the Agent tool's prompt string
- Intermediate tool calls and results **stay inside the subagent**; only the final message returns
- Subagents **cannot spawn other subagents** (no recursive nesting)
- Multiple subagents can run **concurrently** (parallel execution)
- Subagents use the **same model** as the parent (not different/smaller models)

#### Agent Teams (February 2026)

Anthropic shipped Agent Teams — the ability for a lead AI to spawn **teammate agents** that coordinate through message passing:
- Lead Agent assigns work via Shared Task List
- Independent agents execute simultaneously in separate terminal panes
- Agents share findings, challenge each other, and coordinate on their own
- Goes beyond basic subagents into peer-to-peer coordination

#### Claude.ai Research System

Anthropic's internal research system uses a clearly defined multi-agent architecture:
- **Lead agent** (Claude Opus 4) orchestrates 3-5 subagents (Claude Sonnet 4) in parallel
- Each subagent explores a specific part of the problem space
- Subagents use 3+ tools in parallel within their own execution
- Results compressed and returned to lead agent for synthesis
- Cut research time by **up to 90%** for complex queries
- Lead (Opus 4) + subagents (Sonnet 4) **outperformed single-agent Opus 4 by 90.2%**
- Uses ~15x more tokens than single-agent chat

#### Artifacts

**NOT a separate agent.** Artifacts is a UI feature of Claude.ai that renders code/documents in a side panel. The model decides when to open an artifact based on output characteristics (e.g., >10 lines of code). Same model, different rendering behavior.

---

## 3. ChatGPT / OpenAI

### Architecture: Unified Model + Specialized Modes + Codex Subagents

#### ChatGPT Modes (NOT Separate Agents)

ChatGPT has 6 specialized functions via Tools dropdown — these are **modes of the same model**, not separate agents:

| Mode | What It Is |
|------|-----------|
| **Agent Mode** | Autonomous task execution with tool calling |
| **Deep Research** | Multi-step web research agent (o3-based, now GPT-5.4) |
| **Canvas** | Document/code editor side panel (collaborative editing) |
| **Create Image** | Image generation via DALL-E integration |
| **Study and Learn** | Educational mode |
| **Web Search** | Real-time web search |

#### Deep Research

Uses a model optimized for web browsing and data analysis (originally o3-based, now GPT-5.4). Architecture:
1. Decomposes query into sub-questions
2. Autonomously browses web, gathers data from hundreds of sources
3. Adaptive search strategy — pivots based on findings
4. Cross-references sources, identifies contradictions
5. Generates structured report with citations
6. Takes 5-30 minutes

**NOT a separate agent** in the multi-model sense — it's a specialized inference mode with extended tool use and reasoning time.

#### Canvas

**UI feature, not a separate agent.** OpenAI trained GPT-4o to know when to open Canvas (e.g., writing >10 lines, coding tasks). Same model, different UI rendering. Code is sandboxed for live preview.

#### OpenAI Codex (Coding Agent)

Codex uses genuine multi-agent architecture with subagent spawning:

- **Default subagents**: "explorer" (codebase navigation), "worker" (parallel task execution), "default"
- Can spawn specialized agents in parallel, collecting results in one consolidated response
- **Custom agents** configurable as TOML files (~/.codex/agents/) with different models and instructions
- Subagents inherit sandbox/network rules from parent
- GA as of March 16, 2026

#### Model Evolution (2026)

- GPT-5.2 (Jan 2026) → GPT-5.2-Codex → GPT-5.3-Codex → **GPT-5.4** (March 2026, current)
- GPT-5.4 is first mainline model incorporating frontier coding capabilities
- API supports model routing: simple queries → Instant, complex → Thinking/Pro

---

## 4. Google Gemini

### Architecture: Agentic Workflows + Lead Agent Delegation

#### Deep Research

Uses a **genuine multi-agent architecture**:

1. Lead agent (Gemini 3 Pro reasoning core) receives query
2. Autonomously generates multi-step plan (NOT asking user follow-up questions)
3. Plan presented to user for review/approval
4. Lead agent **delegates to multiple sub-agents** running in parallel
5. Sub-agents are typically "web search" agents, each with specific research mandates
6. Delegation via structured API call with precise prompt, constraints, and permissions
7. Results gathered back for central synthesis

Key: The lead agent delegates work to sub-agents that "work for" it — this is genuine orchestrator-worker pattern, similar to Anthropic's research system.

#### Jules (Coding Agent)

- Autonomous, always-on coding agent
- Powered by Gemini 3 Pro (now Gemini 3.1 Pro)
- Architecture: Transformer-based MoE with **three-tier thinking system** (adjustable reasoning depth)
- Features: coherent multi-step planning, visual verification, agentic memories
- Single agent with tools, NOT multi-agent internally

#### Gems

**NOT separate agents.** Gems are the same underlying Gemini model configured with different system prompts. Functionally identical to saving a system prompt template. Users can manually chain multiple Gems as a pipeline, but this is user-orchestrated, not built-in multi-agent.

#### Agent Development Kit (ADK)

Google provides ADK for building custom multi-agent systems with directed graphs — similar concept to LangGraph but Google's own framework.

---

## 5. Vercel v0

### Architecture: Composite Model Family (Multiple Specialized Models)

Vercel v0 uses a **fundamentally different approach** — not one model with tools, but multiple specialized models working together:

#### The Composite Model Family

| Component | Purpose | Model |
|-----------|---------|-------|
| **Base Model** | Primary code generation | State-of-the-art frontier model (swappable) |
| **Quick Edit** | Fast inline edits | Optimized smaller model for streaming diffs |
| **AutoFix (vercel-autofixer-01)** | Error correction mid-stream | Custom model trained with Fireworks AI RFT |
| **Data Retrieval** | Documentation/context | Specialized retrieval pipeline |

#### AutoFix Technical Details

- **Separate model** trained via Reinforcement Fine-Tuning (RFT) with Fireworks AI
- Runs **concurrently** with base model output — checks stream for errors in real-time
- Performs at par with gpt-4o-mini and gemini-2.5-flash on error metrics
- Runs **10-40x faster** than those models (optimized for speed)
- Key advantage: base model can be swapped to latest SOTA without retraining AutoFix

#### Why This Matters

This is the most architecturally unique approach: **decoupled specialized models** rather than one model doing everything or subagent spawning. Each component is independently optimizable.

---

## 6. Cursor / Windsurf

### Cursor: Recursive Planner-Worker Architecture

Cursor's background agents use a **hierarchical multi-agent system**:

#### Architecture

- **Root planners** own entire project scopes
- When a planner's scope can be subdivided → **spawns sub-planners** (recursive)
- **Workers** pick up tasks, work on **isolated repo copies** (git worktrees)
- Workers are **unaware of the larger system** — no inter-worker communication
- Workers write a single handoff when done, submitted back to planners

#### Scale Achieved

- 7-day continuous run building a web browser
- Peak: ~1,000 commits/hour across 10M tool calls
- Several hundred concurrent workers at peak
- Used GPT-5.2 models (better at extended autonomous work)

#### Key Insight

"Allow some slack in correctness" — requiring 100% correctness before each commit caused serialization bottlenecks. Agents trust that fellow agents will fix issues.

#### Automations (March 2026)

New system that automatically launches agents triggered by:
- New codebase additions
- Slack messages
- Timers
- PagerDuty incidents (with MCP connections to server logs)
- Runs hundreds of automations per hour

### Windsurf: Parallel Cascade Agents

- Owned by Cognition AI (acquired from Codeium, Dec 2025, ~$250M)
- Core: **Cascade** — AI agent that understands entire codebase
- **Wave 13** (Feb 2026): 5 parallel Cascade agents via git worktrees
- **Arena Mode**: Two agents on same prompt, hidden model identities, user votes on quality
- Ranked #1 in LogRocket AI Dev Tool Power Rankings (Feb 2026)

---

## Cross-Cutting Analysis

### Q: Do any use a "supervisor" agent that routes to other agents?

**Yes, but implementations vary:**

| Platform | Supervisor Pattern |
|----------|-------------------|
| **Grok 4.20** | Grok (Captain) is the coordinator — but it's baked into MoE inference, not a separate routing step |
| **Claude Code** | Parent agent acts as orchestrator, spawning subagents via Agent tool |
| **OpenAI Codex** | Codex handles orchestration (spawning, routing, waiting, closing) |
| **Gemini Deep Research** | Lead agent creates plan and delegates to sub-agents |
| **Cursor** | Root planners delegate to sub-planners and workers |
| **Vercel v0** | No supervisor — composite pipeline where each model has a fixed role |

### Q: Do they use LangGraph or similar frameworks?

**No major consumer platform uses LangGraph internally.** All built custom orchestration:

- **Grok**: Native MoE inference-time multi-agent
- **Claude/Anthropic**: Custom Agent tool + Agent Teams protocol
- **OpenAI**: Custom Codex orchestration + Agents SDK
- **Google**: Custom orchestration (also provides ADK for developers)
- **Vercel**: Custom composite pipeline
- **Cursor**: Custom recursive planner-worker framework

**LangGraph users in production**: LinkedIn (AI recruiter), Uber (test generation), Klarna, Elastic, Replit — enterprise teams building their own systems, not the platforms themselves.

### Q: Single model + tools, or genuine multi-agent?

**Both patterns coexist, even within the same platform:**

| Genuine Multi-Agent | Single Model + Tools/Modes |
|--------------------|-----------------------------|
| Grok 4.20 (4 agents on shared backbone) | ChatGPT modes (Canvas, Agent Mode) |
| Claude Code subagents/teams | Claude.ai Artifacts |
| Anthropic Research System (Opus + Sonnet) | Google Gems |
| OpenAI Codex subagents | Jules (single agent + tools) |
| Gemini Deep Research (lead + sub-agents) | ChatGPT Deep Research (single extended agent) |
| Cursor planners + workers | — |
| Windsurf parallel Cascades | — |
| Vercel composite models | — |

### Q: How do they handle different capabilities?

The dominant 2026 pattern is **capability-specific routing**:

1. **Mode selection** (ChatGPT): User or system picks mode → same model, different tool access and behavior
2. **Automatic delegation** (Grok, Gemini): System detects query complexity → activates multi-agent or stays single
3. **Subagent spawning** (Claude Code, Codex): Parent decides when to delegate, creates specialized subagents
4. **Fixed pipeline** (Vercel): Each capability is a separate model in a deterministic pipeline
5. **Recursive decomposition** (Cursor): Planners recursively break work into worker-sized chunks

---

## Key Takeaways for Wiii Architecture

1. **Wiii's supervisor-based routing is a valid production pattern** — Gemini Deep Research, Claude Code, and Codex all use an orchestrator that delegates to specialized agents. The pattern is proven at scale.

2. **LangGraph is appropriate for Wiii's scale** — while top platforms built custom, they have 100+ engineer teams. LangGraph is the standard for teams building production multi-agent systems (LinkedIn, Uber, Klarna).

3. **The trend is toward parallel subagent execution** — every platform that uses multi-agent does it with parallel execution. Serial agent chains are outdated.

4. **Composite model approach (Vercel) is worth studying** — using specialized smaller models for specific tasks (like AutoFix) alongside a frontier base model is architecturally elegant and cost-effective.

5. **"Scaffolding beats raw model"** — by 2026, the consensus is that agent architecture matters more than model choice. Same model, different scaffolding = different results.

---

## Sources

### Grok / xAI
- [Grok 4.20 Beta: 4-Agent Multi-Agent Architecture — Medium](https://medium.com/@SarangMahatwo/grok-4-20-beta-xais-native-4-agent-multi-agent-architecture-a-technical-deep-dive-for-ai-a2b38487d974)
- [Grok 4.20 Agents Explained: Harper, Benjamin & Lucas](https://www.adwaitx.com/grok-4-20-agents-harper-benjamin-lucas/)
- [HOW THE XAI GROK 4.20 AGENTS WORK — NextBigFuture](https://www.nextbigfuture.com/2026/02/how-the-xai-grok-4-20-agents-work.html)
- [Grok 4.20 Beta: 4-Agent Collaboration System](https://www.adwaitx.com/grok-4-20-beta-multi-agent-features/)
- [Grok 3 Beta — The Age of Reasoning Agents — xAI](https://x.ai/news/grok-3)

### Claude / Anthropic
- [Create custom subagents — Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
- [Subagents in the SDK — Claude API Docs](https://platform.claude.com/docs/en/agent-sdk/subagents)
- [How we built our multi-agent research system — Anthropic](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Claude Code Agent Teams — Medium](https://cobusgreyling.medium.com/claude-code-agent-teams-ca3ec5f2d26a)
- [Claude Code Deep Dive: Subagents in Action — Medium](https://medium.com/@the.gigi/claude-code-deep-dive-subagents-in-action-703cd8745769)

### OpenAI / ChatGPT
- [Introducing GPT-5.4 — OpenAI](https://openai.com/index/introducing-gpt-5-4/)
- [Codex Subagents — OpenAI Developers](https://developers.openai.com/codex/subagents)
- [Introducing deep research — OpenAI](https://openai.com/index/introducing-deep-research/)
- [Introducing Canvas — OpenAI](https://openai.com/index/introducing-canvas/)
- [Introducing ChatGPT agent — OpenAI](https://openai.com/index/introducing-chatgpt-agent/)
- [Codex Subagents — Simon Willison](https://simonwillison.net/2026/Mar/16/codex-subagents/)

### Google Gemini
- [Build with Gemini Deep Research — Google Blog](https://blog.google/technology/developers/deep-research-agent-gemini-api/)
- [Gemini Deep Research Agent — Google AI Developers](https://ai.google.dev/gemini-api/docs/deep-research)
- [Building with Gemini 3 in Jules — Google Developers Blog](https://developers.googleblog.com/jules-gemini-3/)
- [How OpenAI, Gemini, and Claude Use Agents — ByteByteGo](https://blog.bytebytego.com/p/how-openai-gemini-and-claude-use)
- [How Anthropic Built a Multi-Agent Research System — ByteByteGo](https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent)

### Vercel v0
- [Introducing the v0 composite model family — Vercel](https://vercel.com/blog/v0-composite-model-family)
- [How we made v0 an effective coding agent — Vercel](https://vercel.com/blog/how-we-made-v0-an-effective-coding-agent)
- [40X Faster AutoFix with Fireworks AI — Fireworks Blog](https://fireworks.ai/blog/vercel)

### Cursor / Windsurf
- [Towards self-driving codebases — Cursor Blog](https://cursor.com/blog/self-driving-codebases)
- [Cursor Automations — TechCrunch](https://techcrunch.com/2026/03/05/cursor-is-rolling-out-a-new-system-for-agentic-coding/)
- [Cursor Background Agents Guide](https://ameany.io/blog/cursor-background-agents/)
- [Windsurf Review 2026 — PinkLime](https://pinklime.io/blog/windsurf-codeium-review-2026)

### Cross-Platform Comparison
- [Agentic Frameworks in 2026: What Actually Works — Zircon Tech](https://zircon.tech/blog/agentic-frameworks-in-2026-what-actually-works-in-production/)
- [The State of AI Coding Agents (2026) — Medium](https://medium.com/@dave-patten/the-state-of-ai-coding-agents-2026-from-pair-programming-to-autonomous-ai-teams-b11f2b39232a)
- [Choosing the Right Multi-Agent Architecture — LangChain Blog](https://blog.langchain.com/choosing-the-right-multi-agent-architecture/)
- [LangGraph: Build Stateful Multi-Agent Systems — Mager](https://www.mager.co/blog/2026-03-12-langgraph-deep-dive/)
