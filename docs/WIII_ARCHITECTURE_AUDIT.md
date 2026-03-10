# Wiii Architecture Audit

This document is a product-architecture audit of Wiii as it exists now.

It is not a full system map.
It is an opinionated reading of what the architecture is really optimized for, what is structurally strong, and where the codebase is at risk of spreading beyond its center of gravity.

## Executive Read

Wiii already has a clear thesis.
It is not trying to be a generic chat app.
It is trying to be a persistent, agentic, context-aware intelligence that can live across product surfaces, remember across time, operate inside organizations, and gradually accumulate an internal life model.

That thesis is stronger than most AI products.
The codebase reflects it surprisingly well.

The architectural risk is not lack of ambition.
The architectural risk is that too many advanced subsystems are now first-class at the same time:

- multi-agent orchestration
- Living Agent continuity
- LMS integration
- multi-tenant org model
- MCP interoperability
- browser and product search tooling
- universal host context
- cross-platform identity and sync

The system is coherent, but expensive to keep coherent.

## Audit Lens

This audit uses one simple rule:

Architecture is healthy when most complexity compounds into the core product thesis.
Architecture is unhealthy when complexity accumulates faster than it strengthens the thesis.

## The Core Thesis

The strongest product thesis visible in the codebase is:

Wiii is a domain-capable, organization-aware, long-lived intelligence that should feel continuous across conversations, channels, and contexts.

That thesis has five structural layers:

1. Wiii Core: request execution, agent routing, retrieval, tools, streaming.
2. Wiii Living: continuity, soul, emotion, goals, reflections, skill growth.
3. Wiii Host: desktop, embed, LMS, MCP, browser, future host applications.
4. Wiii Org: permissions, branding, tenant boundaries, operational ownership.
5. Wiii Data: durable memory, retrieval substrate, auth state, learning state.

The best parts of the architecture are the parts where these five layers reinforce each other instead of competing.

## What Is Working Well

### 1. The System Has A Real Center

Many AI codebases are collections of features.
Wiii already has a center: continuity plus orchestration.

The orchestrator, multi-agent graph, memory systems, living-agent feedback loop, and desktop UX all point toward the same product identity.
That is rare and valuable.

This means Wiii is not guessing what it is.
It already knows.

### 2. Core Runtime Is Layered Correctly

The backend request path is structurally sound:

- API and middleware establish boundaries
- ChatOrchestrator normalizes the task
- agent routing separates execution strategies
- retrieval and tools act as context providers
- output processing and SSE shape the user-visible interaction

This is a strong execution model because it prevents direct coupling between transport, orchestration, retrieval, and UI delivery.

### 3. Living Agent Is Not Cosmetic

This is one of the project's strongest architectural decisions.

The Living Agent system is not only a prompt flavor.
It is wired into runtime behavior through:

- sentiment analysis
- emotion updates
- episodic memory
- heartbeat scheduling
- journal and reflection loops
- identity and narrative synthesis

That gives Wiii a serious claim to continuity.
If maintained carefully, this is one of the product's clearest differentiators.

### 4. Multi-Tenant Design Is Real, Not Superficial

Organization-aware middleware, thread identity, repository filters, org settings, and permission surfaces show that tenancy is treated as an architectural concern rather than a UI switch.

That matters because Wiii clearly wants to operate in institutional settings such as schools, LMS deployments, and admin-governed environments.

### 5. Data Layer Is Pragmatic And Powerful

Using PostgreSQL as the primary operational memory substrate is a strong practical choice.
It lets the system support:

- transactional business state
- semantic memories
- chat history
- auth state
- org isolation
- learning profiles
- vector retrieval
- sparse retrieval

This creates schema complexity, but it also keeps the platform operationally unified.

### 6. Desktop UX Reflects The Product Thesis

The desktop app is not built as a thin wrapper around chat.
It exposes:

- chat and streaming
- admin operations
- org context
- living-agent state
- preview and source panels
- embed and cross-surface behavior

This matters because the UI is aligned with the thesis that Wiii is a workspace intelligence, not only a responder.

## Where The Architecture Is At Risk

### 1. Too Many Strategic Fronts Are Active At Once

The current system is carrying many ambitious programs simultaneously:

- Living Agent
- LMS production integration
- MCP server and client
- browser and product search platform
- universal context engine
- cross-platform identity and sync
- multi-tenant org customization
- adaptive and advanced RAG modes

Each of these could be a roadmap of its own.
Together they create coordination drag and integration entropy.

The danger is not any single subsystem.
The danger is the number of first-tier subsystems competing for architectural attention.

### 2. Feature Flags Reduce Blast Radius But Increase Reality Fragmentation

Feature flags are used heavily and often appropriately.
But at this scale they create another problem: too many possible system realities.

When many critical subsystems are optional, the number of valid runtime combinations grows quickly.
That raises the cost of reasoning, testing, and debugging.

In other words, flags protect rollout safety but can weaken system legibility.

### 3. The Living Thesis Is Stronger Than Its Product Boundary

Living Agent is strategically important, but its boundary is still porous.

Right now, the system sometimes reads like:

- product AI platform
- autonomous soul system
- LMS copilot
- multi-channel identity layer
- experimental host runtime

all at once.

The architectural question is not whether Living belongs.
It does.
The question is whether every adjacent subsystem truly strengthens the Living thesis or merely expands the surface area around it.

### 4. The Codebase Has High Cognitive Load For New Contributors

The system is documented, which helps.
But there is still a steep mental load because understanding one feature often requires context from:

- feature flags
- prompt loader behavior
- middleware and org context
- agent state propagation
- data isolation helpers
- frontend store coordination

This is not a sign of bad engineering.
It is a sign of maturity pressure.
The system is moving from rapid capability addition into a phase where architectural compression matters more.

### 5. JSONB Flexibility Can Become Semantic Drift

The data model is pragmatic, but several areas store important product meaning inside flexible structures.
That is useful early.
Over time it risks:

- inconsistent semantics
- weak invariants
- duplicated interpretation logic
- migration difficulty

This is especially relevant for living-agent metadata, org settings, review schedules, and evolving integration payloads.

## What Is Truly Core Versus Peripheral

### Core

These are the parts that most directly strengthen the product thesis and should remain protected:

- ChatOrchestrator and multi-agent runtime
- retrieval and memory stack
- org-aware execution model
- living-agent continuity loop
- desktop and embed runtime surfaces
- auth and identity federation
- thread and cross-session continuity

### Strategic But Secondary

These are valuable, but should be judged by whether they clearly serve the core thesis:

- LMS data pull and push features
- MCP interoperability
- universal context engine
- advanced RAG strategy variants
- product search and browser automation

These should not be removed casually, but they should be held to a higher bar: each one should justify how it deepens continuity, usefulness, or deployment viability.

### Peripheral Or High-Risk Expansion Zones

These are the areas most likely to generate architectural drag if allowed to expand without discipline:

- too many search backends with overlapping value
- parallel experimental context systems
- multiple identity and sync paths without a sharply defined source of truth
- feature-flagged subsystems that are rarely exercised together

The issue is not that these are bad ideas.
The issue is that they can absorb large amounts of maintenance energy while only weakly improving the central thesis.

## Recommended Architectural Posture

### 1. Protect The Core Loop

The most valuable loop in Wiii is:

request → context → routing → tool/retrieval execution → response → memory/emotion/continuity update

Any new system should be judged by whether it strengthens this loop.
If it does not, it should be treated as optional or deferred.

### 2. Compress Around The Five-Layer Model

Future design choices should be forced through this question:

Is this primarily Core, Living, Host, Org, or Data?

If a feature cannot be placed clearly, it is usually a signal that the architecture boundary is still fuzzy.

### 3. Prefer Fewer Strong Platforms Over Many Partial Ones

Wiii appears strongest when it acts as:

- a serious desktop and embed assistant
- a real LMS-aware intelligence
- a continuity-rich agent with persistent identity

That is already a lot.
Trying to become every kind of host-aware AI runtime simultaneously risks weakening the product's clarity.

### 4. Turn Feature Flags Into Tiers

A likely next maturity step is to classify subsystems into tiers such as:

- foundational
- production-supported
- experimental
- dormant

This would reduce the mental cost of reading the codebase and help contributors understand what is essential versus optional.

### 5. Keep Living Agent Integrated, But Narrow Its Contract

Living should stay central.
But its integration contract should stay explicit:

- what Living reads
- what Living writes
- what parts of Core can be influenced synchronously
- what parts only update asynchronously

This is how the project keeps the soul thesis without turning every module into soft state.

## Final Assessment

Wiii is one of the rarer AI codebases where the architecture actually expresses a product worldview.

The worldview is coherent:

- intelligence should be persistent
- memory should matter
- context should be host-aware
- deployment should be organization-safe
- the AI should have continuity beyond the current turn

That is the strongest quality of the project.

The main threat is not technical weakness.
The main threat is successful over-expansion.

If Wiii keeps compressing complexity back toward its core thesis, it can become unusually distinctive.
If it keeps adding strategic fronts faster than it consolidates them, the system may remain impressive but increasingly expensive to evolve.

## Recommended Reading Order After This Audit

- [WIII_PROJECT_MENTAL_MODEL.md](WIII_PROJECT_MENTAL_MODEL.md): one-page system model
- [../maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md](../maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md): full subsystem architecture
- [../maritime-ai-service/docs/architecture/SYSTEM_FLOW.md](../maritime-ai-service/docs/architecture/SYSTEM_FLOW.md): request and streaming sequences
- [../wiii-desktop/README.md](../wiii-desktop/README.md): frontend runtime and UX surfaces