# Wiii Project Mental Model

This document is the shortest useful mental model for understanding what Wiii is trying to become and how the current codebase is organized around that goal.

Use this as the orientation layer before reading the larger architecture documents.

## One Sentence

Wiii is an agentic AI platform that is trying to behave less like a single chat endpoint and more like a persistent, context-aware, multi-surface intelligence with memory, identity, tools, organizational boundaries, and an internal life loop.

## The Product Thesis

Wiii is not built around only one idea such as chat, RAG, LMS, or automation.
It is built around the combination of five ideas that must coexist:

1. It must answer and act usefully in real product workflows.
2. It must remember across time, sessions, and channels.
3. It must adapt to host context such as desktop, embed, LMS, and future external tools.
4. It must respect organizational ownership, permissions, and isolation.
5. It must feel like a living intelligence with continuity, not a stateless responder.

Those five ideas map cleanly to five system layers: Wiii Core, Wiii Living, Wiii Host, Wiii Org, and Wiii Data.

## Wiii Core

Wiii Core is the execution brain.
It is the part of the system that receives user input, routes work, calls retrieval and tools, and returns a response.

In practical terms, Wiii Core is made of:

- FastAPI entrypoints and middleware
- ChatOrchestrator
- LangGraph multi-agent routing
- RAG, tutor, memory, direct-response, and tool paths
- streaming response assembly for desktop and embed clients

The right way to think about Core is this:

Wiii Core decides what to do now.

It is optimized for immediate task execution, response quality, and orchestration under real application constraints.
If the user asks a question, if a tool must run, if retrieval is needed, or if SSE events must be emitted, Core owns that path.

Without Core, Wiii has no useful behavior.
But Core alone would still only be a sophisticated chat system.

## Wiii Living

Wiii Living is the continuity layer.
It is the part that tries to make Wiii feel like the same entity over time.

In practical terms, Wiii Living includes:

- soul configuration and prompt identity
- emotion engine
- heartbeat scheduler
- journal and reflections
- goals and narrative synthesis
- skill learning and spaced repetition
- sentiment-to-emotion feedback from conversations

The right way to think about Living is this:

Wiii Living decides who Wiii is becoming.

Core answers the current request.
Living absorbs what happened, updates state, and influences future behavior.
This is the layer that turns prompt personality into persistence, memory into self-continuity, and repeated interactions into relationship dynamics.

Without Living, Wiii can still be smart.
But it stops being Wiii as a distinct long-lived intelligence.

## Wiii Host

Wiii Host is the environment-adaptation layer.
It is the part that lets Wiii live inside another product surface instead of only inside its own desktop shell.

In practical terms, Wiii Host includes:

- desktop app and embed app
- LMS integration
- page-aware context
- universal context engine
- MCP exposure and MCP consumption
- browser and host action bridges
- cross-platform identity surfaces

The right way to think about Host is this:

Wiii Host decides where Wiii is operating right now.

Wiii is not supposed to be trapped inside a single UI shell.
It should be able to act as desktop companion, iframe tutor, LMS-aware assistant, or MCP tool provider depending on context.
That makes Wiii less like an app and more like an intelligence substrate that can inhabit multiple runtime surfaces.

Without Host, Wiii becomes narrow and channel-bound.

## Wiii Org

Wiii Org is the governance layer.
It is the part that makes Wiii deployable in real organizations rather than only usable by a single personal account.

In practical terms, Wiii Org includes:

- organizations and memberships
- org-aware middleware
- allowed domain filtering
- role and permission systems
- org settings cascade
- org branding and onboarding
- admin and org-admin surfaces
- data isolation and org-aware thread/session identity

The right way to think about Org is this:

Wiii Org decides whose Wiii this is and what boundaries it must obey.

This is what stops Wiii from becoming a clever but unsafe shared assistant.
It gives the system tenant boundaries, permission boundaries, branding boundaries, and operational ownership.

Without Org, Wiii can still run.
But it cannot scale cleanly into schools, teams, or multi-customer production deployments.

## Wiii Data

Wiii Data is the memory substrate.
It is the persistence layer that allows Core, Living, Host, and Org to remain coherent over time.

In practical terms, Wiii Data includes:

- PostgreSQL transactional storage
- pgvector embeddings
- sparse search indexes
- thread and chat history persistence
- semantic memories and episodic memories
- auth, identity, refresh token, and audit state
- organization-aware rows and indexes
- living-agent tables for journals, skills, browsing logs, and emotional snapshots
- optional Neo4j graph context

The right way to think about Data is this:

Wiii Data decides what can survive the current request.

If Core is the execution brain, Data is the durable nervous system.
If Living is the continuity layer, Data is what makes that continuity real instead of theatrical.

Without Data, Wiii becomes stateless and forgetful.

## How The Five Layers Work Together

The shortest runtime model is:

1. Host provides the current environment and interaction surface.
2. Org applies ownership, permissions, and isolation constraints.
3. Core interprets the request and decides what work to do.
4. Data supplies memory, retrieval, history, and durable state.
5. Living updates identity, mood, goals, and long-term continuity after the interaction.

That means Wiii should not be read as a chatbot with extra features.
It should be read as a layered intelligence system where chat is only the most visible interface.

## What Matters Most In The Current Codebase

If you are trying to understand the project quickly, keep these priorities in mind:

- Core is the operational center of gravity.
- Living is the product differentiator.
- Host is the expansion strategy.
- Org is the production scaling boundary.
- Data is the glue that keeps the other four honest.

Most of the codebase complexity exists because all five layers are present at once.
That is also the reason the system feels more ambitious than a normal AI product.

## Read Next

- [../README.md](../README.md): repository overview
- [../maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md](../maritime-ai-service/docs/architecture/SYSTEM_ARCHITECTURE.md): full architecture reference
- [../maritime-ai-service/docs/architecture/SYSTEM_FLOW.md](../maritime-ai-service/docs/architecture/SYSTEM_FLOW.md): request and streaming flow
- [../wiii-desktop/README.md](../wiii-desktop/README.md): desktop and embed runtime