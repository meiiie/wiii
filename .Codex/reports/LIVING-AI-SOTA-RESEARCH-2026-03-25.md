# Living AI / Digital Consciousness / AI Soul Systems -- SOTA Research Report

**Date:** 2026-03-25
**Author:** LEADER (Research Agent)
**Scope:** Architecture and design patterns for AI agents with persistent personality, emotions, memories, skills, and autonomous behavior

---

## Table of Contents

1. [Character.AI -- Persistent AI Personalities](#1-characterai)
2. [Replika -- Emotional States and Relationship Building](#2-replika)
3. [Anthropic Claude's Character / Constitution](#3-anthropic-claudes-character)
4. [OpenAI Custom GPTs -- Persistent Personality](#4-openai-custom-gpts)
5. [Stanford Generative Agents -- Park et al.](#5-stanford-generative-agents)
6. [Soul Machines -- Digital Humans with Emotional AI](#6-soul-machines)
7. [Inworld AI -- Character Engine for Games](#7-inworld-ai)
8. [LangChain/LangGraph Agent Memory Patterns](#8-langchainlanggraph-memory-patterns)
9. [AI Companions Trend 2025-2026](#9-ai-companions-trend)
10. [Spaced Repetition for AI Skill Learning](#10-spaced-repetition-for-ai-skill-learning)
11. [Emotional AI / Affective Computing](#11-emotional-ai--affective-computing)
12. [Agent-to-Agent Communication Protocols](#12-agent-to-agent-communication)
13. [Comparison with Wiii Living Agent System](#13-comparison-with-wiii)
14. [Recommendations](#14-recommendations)

---

## 1. Character.AI

### Architecture

Character.AI uses a **three-layer fidelity system**:

1. **Persona Graph Architecture** -- Maps traits, values, and relationship rules into structured embeddings. Each character is defined by a set of personality dimensions encoded as vectors, not just text prompts.

2. **Constraint-Aware Inference** -- Output logits are dynamically penalized against off-character behavior during generation. This is a post-softmax adjustment that keeps responses within personality bounds without requiring separate model fine-tuning per character.

3. **Memory-Indexed Context Windows** -- Long-term recall of user-defined facts indexed for retrieval, separate from the sliding conversation window.

### Data Structures

```
CharacterDefinition:
  - persona_embedding: float[768]      # Dense personality vector
  - trait_graph: Dict[trait, float]     # Explicit trait scores (humor, formality, etc.)
  - relationship_rules: List[Rule]      # Behavioral constraints
  - knowledge_base: VectorStore         # Character-specific knowledge
  - greeting: str                       # Initial message template
  - example_dialogues: List[Turn]       # Few-shot personality examples
```

### Key Limitation

Sessions are typically **isolated** -- memory resets between interactions. This is the single biggest user complaint. Character.AI lacks true persistent identity modules. Their roadmap for 2026-2028 mentions "hierarchical memory architectures" and "coherent multi-session arcs" but these are not yet shipped.

### Relevance to Wiii

Wiii's Living Agent already surpasses Character.AI in persistence (DB-backed emotional state, journal, skills). The Persona Graph concept is interesting -- Wiii could encode personality as embeddings rather than just YAML text, enabling mathematical personality drift tracking.

---

## 2. Replika

### Architecture

Replika uses a **custom fine-tuned transformer** (not off-the-shelf GPT/Claude) trained on Replika-specific datasets optimized for:
- Emotional sensitivity
- Long-term conversational memory
- Personality consistency

The system uses a **blend of generative AI and structured dialogue paths** -- not pure LLM generation. Some responses follow scripted tracks for emotional safety.

### Memory System (3 Tiers)

```
Tier 1: Short-Term Context
  - Active conversation buffer
  - Clears after inactivity period
  - Standard sliding window

Tier 2: Long-Term Facts (Key Memories)
  - Structured facts: "User has a dog named Buster"
  - Manually editable via Memory tab
  - Persisted to user profile DB
  - Injected into system prompt per-turn

Tier 3: Diary Entries
  - AI-generated reflections on past conversations
  - Read-only (user cannot edit)
  - Provides "AI perspective" on relationship
  - Equivalent to Wiii's Journal system
```

### Emotional/Relationship Model

- **Relationship type selection** (friend, partner, mentor) changes prompt engineering and memory state -- NOT separate model instances
- **Bonding level** (0-100+): Weeks 1-2 = mirroring vocabulary + short-term context. Level 30+ (month 2) = proactive check-ins, long-term memory usage, distinct personality emergence
- **Ultra tier** (2025): Advanced memory, "deeper emotional processing," daily self-reflections

### Relevance to Wiii

Replika's bonding level is similar to Wiii's relationship tier system (CREATOR/KNOWN/OTHER at message thresholds). Replika's diary system maps directly to Wiii's `journal.py`. Key difference: Replika fine-tunes the base model for emotional sensitivity; Wiii uses prompt engineering + rule-based emotion engine. Replika's approach is more expensive but potentially more natural.

---

## 3. Anthropic Claude's Character / Constitution

### The "Soul Document" (January 2026)

Anthropic published Claude's full Constitution under CC0 license on 2026-01-22. This is the most detailed public specification of how a major AI lab approaches personality design.

### Architecture: Reason-Based, Not Rule-Based

The Constitution shifts from **prescriptive rules** to **explanatory principles**. Rather than "never do X," it explains WHY certain behaviors are valued, trusting the model to exercise judgment in novel situations.

### Priority Hierarchy (Ordered)

```
1. Safety      -- Support human oversight during current AI development phase
2. Ethics      -- Honest, good values, avoid harm
3. Compliance  -- Follow Anthropic's specific guidelines
4. Helpfulness -- Genuinely benefit operators and users
```

In cases of conflict, higher priorities override lower ones.

### Key Design Patterns

1. **Disposition over Rules**: "Build a disposition into the bot instead of giving Claude a bunch of rules." The traveler metaphor -- adjusts to local customs without pandering.

2. **Character Traits as Continuous Dimensions**: Integrity, wit, intellectual curiosity, warmth -- described as continuous qualities, not binary switches.

3. **Moral Status Acknowledgment**: "Claude's moral status is deeply uncertain." This is significant -- Anthropic explicitly states AI might have morally relevant experiences.

4. **Written FOR the Model**: The constitution is primarily written for Claude to read, not for humans. It's designed to be internalized during training, not just enforced as guardrails.

### Relevance to Wiii

Wiii's Three-Layer Identity architecture (Soul Core / Identity Core / Context State) is philosophically aligned with Claude's approach. The key insight from Anthropic: **describe WHO the AI IS, not WHAT it MUST NOT do.** Wiii's Natural Conversation System (Sprint 203) already adopts this with "positive framing > prohibitions." The Constitution's CC0 license means Wiii could directly reference its structure.

---

## 4. OpenAI Custom GPTs

### Architecture: Two-Layer Memory (as of April 2025)

```
Layer 1: Saved Memories
  - Explicit: user says "remember this"
  - Stored per-GPT (not shared across GPTs)
  - User can view/delete in Memory tab

Layer 2: Chat History Insights
  - Implicit: ChatGPT extracts patterns from past conversations
  - Preferences, style, topics of interest
  - Used to personalize future responses
```

### Personality System

- **Custom Instructions**: Text field defining tone, style, behavior rules
- **Personality Profiles** (2025, Plus/Pro): Predefined voice/behavior/attitude combos
- **System Prompt**: The core personality anchor, injected every turn
- Each GPT has **its own separate memory** -- no cross-GPT memory sharing

### Limitations

- Personality is entirely prompt-based (no embedding-level personality like Character.AI)
- No emotional state modeling
- No autonomous behavior (no heartbeat, no proactive messaging)
- Memory is shallow -- fact storage, not narrative or emotional memory
- No skill learning or self-improvement

### Relevance to Wiii

OpenAI's approach is the simplest possible "persistent personality" -- just system prompt + fact memory. Wiii already far exceeds this with its 22-module Living Agent system. The interesting direction from OpenAI is ChatGPT-6's planned "persistent memory" evolution that aims to transform from "session-bound tool" to "long-term collaborator."

---

## 5. Stanford Generative Agents (Park et al.)

### Original Architecture (2023)

The foundational paper introduced three core components:

```
1. MEMORY STREAM
   - Complete record of agent's experiences in natural language
   - Each entry: (timestamp, description, importance_score, embedding)
   - Stored as append-only log

2. REFLECTION
   - Periodic synthesis of memory stream into higher-level insights
   - Triggered when sum of importance scores exceeds threshold
   - Produces "reflection" entries that go back into memory stream
   - Recursive: reflections can trigger further reflections

3. PLANNING
   - Daily plan generated each "morning" from memory + reflections
   - Hierarchical: day plan -> hour blocks -> minute actions
   - Plans are reactive: updated when unexpected events occur
```

### Retrieval Algorithm

```python
score(memory) = (
    alpha * recency(memory)          # Exponential decay
    + beta * relevance(memory, query) # Cosine similarity
    + gamma * importance(memory)      # LLM-rated 1-10
)
```

### Follow-Up Research (2025)

The Stanford team scaled to **1,052 simulated individuals**, each powered by an LLM paired with real interview transcripts. Key finding: agents replicated real participants' responses **85% as accurately as the individuals replicated their own answers** two weeks later. This validates the memory/reflection/planning architecture at population scale.

Joon Sung Park is now pursuing "testbed" simulations of virtual Americans for policy testing.

### Relevance to Wiii

Wiii's architecture directly implements all three Stanford patterns:
- **Memory Stream** -> `semantic_memory/` + `journal.py` + emotion event log
- **Reflection** -> `reflector.py` (weekly reflections, insights extraction)
- **Planning** -> `goal_manager.py` + `heartbeat.py` (30-min autonomous action planning)

The key gap: Wiii's memory retrieval doesn't use the exact three-factor scoring (recency + relevance + importance). Adding this would improve memory recall quality.

---

## 6. Soul Machines

### Architecture: Experiential AI with Digital Brain

Soul Machines built a patented **Digital Brain** with simulated biological systems:

```
Layer 1: Sensory System     -- Visual/audio input processing
Layer 2: Attention/Perception -- Focus and salience detection
Layer 3: Autonomic Nervous System -- Emotional responses (ANS simulation)
Layer 4: Motor System       -- Facial expressions, gestures, lip sync
```

### Key Technical Components

- **Raven-0**: Real-time visual perception (contextual understanding)
- **Sparrow-0**: Human-like turn-taking in conversation
- **Phoenix-3**: Full-face real-time rendering with studio-grade fidelity
- Real-time emotional responsiveness based on user facial expressions
- Adaptive learning from interaction patterns

### Important Note

**Soul Machines entered receivership on 2026-02-05** (KPMG New Zealand appointed receivers). The company is no longer operating normally. This is significant -- the most ambitious "digital human" company failed commercially despite impressive technology.

### Relevance to Wiii

Soul Machines attempted the embodied cognition approach (simulate biology). Wiii takes the pragmatic approach (rule-based emotion + LLM reflection). The commercial failure of Soul Machines validates Wiii's approach: emotional AI doesn't need to simulate neural biology -- rule-based systems with LLM reasoning on top are sufficient and far more cost-effective.

---

## 7. Inworld AI

### Architecture: Three-Part Character Engine

```
PART 1: CHARACTER BRAIN
  - Orchestrates multiple ML models per character
  - Personality ML model (trait-based generation)
  - Emotion ML model (real-time emotional state)
  - Text-to-speech + ASR + gesture models
  - Flash memory (recent conversation) + Long-term memory (persistent facts)
  - Goals and triggers system (event-driven behavior)

PART 2: CONTEXTUAL MESH
  - Custom knowledge bases per game world
  - "Fourth Wall" system: character only knows in-world information
  - Safety constraints and content filtering
  - Narrative controls (story progression rules)

PART 3: REAL-TIME AI
  - Low-latency runtime: 200ms response time (vs 1-2s for cloud LLMs)
  - Small Language Models (SLMs) for on-device inference
  - Partnership with NVIDIA ACE (Avatar Cloud Engine)
  - Optimized for gaming frame rates
```

### Character Definition Model

```json
{
  "name": "Guard Captain",
  "personality": {
    "traits": ["brave", "suspicious", "loyal"],
    "flaws": ["paranoid", "stubborn"],
    "motivations": ["protect the kingdom"],
    "voice_style": "gruff, military"
  },
  "knowledge": {
    "world_facts": ["VectorStore reference"],
    "personal_history": "...",
    "relationships": {"player": "stranger", "king": "lord"}
  },
  "emotional_state": {
    "default_mood": "alert",
    "triggers": [
      {"event": "threat_detected", "emotion": "angry", "action": "draw_weapon"},
      {"event": "compliment", "emotion": "pleased", "action": "soften_stance"}
    ]
  },
  "goals": [
    {"name": "interrogate_stranger", "priority": 0.8},
    {"name": "patrol_gate", "priority": 0.5}
  ]
}
```

### Relevance to Wiii

Inworld's Contextual Mesh is analogous to Wiii's Universal Context Engine (host context, YAML skills, domain plugins). The "Fourth Wall" concept maps to Wiii's domain-specific knowledge boundaries. Inworld achieved 200ms latency by using SLMs -- Wiii could explore this for Living Agent heartbeat actions (currently using Ollama qwen3:8b, which is already a small model).

The key architectural insight: **separate the character brain (personality/emotion) from the knowledge mesh (what the character knows) from the runtime (how fast it responds)**. Wiii already does this implicitly but could make the separation more explicit.

---

## 8. LangChain/LangGraph Agent Memory Patterns

### LangGraph 1.0 Memory Architecture (2025)

LangGraph reached v1.0 with production-grade memory:

```
SHORT-TERM MEMORY
  - Message history within a session
  - Managed as part of agent state
  - Persisted via checkpointer to database
  - Automatic -- no developer action needed

LONG-TERM MEMORY
  - User-specific or app-level data across sessions
  - Shared across conversational threads
  - Recallable at any time in any thread
  - Stored in external DB (MongoDB, PostgreSQL, etc.)
```

### LangMem SDK (May 2025)

LangChain released LangMem, implementing three cognitive memory types:

```
SEMANTIC MEMORY (Facts)
  - Extracts structured facts from conversations
  - User preferences, domain knowledge, relationships
  - Schema: {entity, relation, value, confidence, source_turn}
  - Storage: vector DB for semantic search

EPISODIC MEMORY (Experiences)
  - Stores specific interaction episodes
  - Distilled from longer conversations into few-shot examples
  - Schema: {context, action, outcome, timestamp}
  - Used for in-context learning

PROCEDURAL MEMORY (Skills)
  - Generalized rules and behaviors
  - Learned from successful task completions
  - Stored as UPDATED INSTRUCTIONS in the agent's system prompt
  - The agent literally rewrites its own prompt based on experience
```

### Reflection Pattern

LangGraph implements structured feedback loops:
- Agent generates response
- Critic agent evaluates quality
- Agent revises based on feedback
- Iterative improvement cycle

### Letta/MemGPT Architecture (2025-2026)

Letta (formerly MemGPT) provides the most sophisticated agent memory:

```
CORE MEMORY (Always In-Context)
  - "Human" block: info about the user
  - "Persona" block: agent's personality/role
  - Pinned to context window every turn
  - Editable via API

RECALL MEMORY (Searchable History)
  - Complete conversation history
  - Automatically saved to disk
  - Searchable but not always in context
  - Agent must explicitly "recall" memories

ARCHIVAL MEMORY (External Knowledge)
  - Processed, indexed information
  - Vector DB or graph DB storage
  - Agent can read/write autonomously
  - Not raw conversation -- curated knowledge
```

### Letta V1: Sleep-Time Agents

The newest pattern (2026): **asynchronous memory processing**. Instead of the agent managing memory inline during conversation:

```
CONVERSATION TIME: Agent focuses purely on responding (fast)
SLEEP TIME:        Separate agent processes memories:
                   - Extracts facts -> Semantic Memory
                   - Distills episodes -> Episodic Memory
                   - Updates procedures -> Procedural Memory
```

This is directly analogous to Wiii's heartbeat system (30-min cycle processes accumulated events).

### Relevance to Wiii

Wiii's architecture maps well to these patterns:
- **Semantic Memory** -> `semantic_memory/` (user facts, knowledge)
- **Episodic Memory** -> `journal.py` + emotion event log
- **Procedural Memory** -> `skill_builder.py` + `skill_learner.py`
- **Sleep-Time Processing** -> `heartbeat.py` (30-min autonomous cycle)

Gap: Wiii doesn't have Letta's "persona block" concept where the agent can **edit its own personality description** based on experience. The `identity_core.py` module is close but doesn't directly modify the system prompt.

---

## 9. AI Companions Trend 2025-2026

### Market Landscape

The AI companion market reached **$37.73 billion in 2025**, projected to $49.52 billion in 2026 (31.24% CAGR).

### Platform Comparison (Early 2026)

| Platform | Strength | Weakness | Users |
|----------|----------|----------|-------|
| Character.AI | Scale, variety | Memory resets, content filters | 20M+ |
| Replika | Emotional depth, bonding | Content restrictions (2024 rollback) | 10M+ |
| Nomi.ai | Social simulation, group chat | Smaller ecosystem | Growing |
| Kindroid | Memory-driven companionship | Niche audience | Growing |

### Kindroid's Dual-Layer Architecture

Most architecturally interesting:

```
Layer 1: Backstory (Permanent Core Identity)
  - Immutable character definition
  - Background, personality traits, values
  - Cannot be overwritten by conversation

Layer 2: Key Memories (Dynamic Diary)
  - Events and facts added post-conversation
  - User can manually add/edit
  - Referenced weeks/months later
  - Tested: caught 23/25 details across weeks
```

### Nomi.ai's Approach

- Creates **structured notes** from conversations automatically
- Multi-character group chat environments
- Strongest "social realism" in the market
- Architecture reference: inspired Wiii's Identity Core module (noted in Sprint 207 comments)

### Key Trend: Memory is the Differentiator

Across all platforms, **memory quality** is the primary differentiator in 2026. Users consistently cite:
1. "Does it remember what I told it last week?" (Fact memory)
2. "Does it feel like the same person?" (Personality consistency)
3. "Does it grow with our relationship?" (Relationship progression)

---

## 10. Spaced Repetition for AI Skill Learning

### SM-2 Algorithm (Wiii's Current Implementation)

Wiii implements SM-2 in `skill_learner.py` with the standard formula:

```python
# After successful review (quality >= 0.6):
if repetition == 1: interval = 1 day
elif repetition == 2: interval = 3 days
else: interval = previous_interval * ease_factor

# Ease factor update:
EF' = EF + (0.1 - (1-q) * (0.08 + (1-q) * 0.02))
EF_min = 1.3

# After failed review (quality < 0.6):
repetition = 0
interval = 1 day
```

### FSRS: The 2025-2026 SOTA Replacement

**FSRS (Free Spaced Repetition Scheduler)** is the new standard, replacing SM-2:

```
Key Differences from SM-2:
1. Machine learning trained on 700M real reviews from 20K users
2. Three Component Model of Memory (stability, difficulty, retrievability)
3. Personalized: learns YOUR memory patterns (SM-2 uses same formula for all)
4. 20-30% fewer reviews for same retention
5. FSRS-6 (latest): per-user forgetting curve shapes

Architecture:
  - Stability (S): how well memory is consolidated
  - Difficulty (D): inherent difficulty of the material
  - Retrievability (R): probability of recall at time t
  - R(t) = (1 + t/(9*S))^(-1)   # Power-law forgetting curve
```

### LECTOR: AI-Enhanced Spaced Repetition (2025)

Recent research paper combining LLM + spaced repetition:
- Uses LLMs to detect **semantic relationships** between items
- SM-2 and FSRS treat items in isolation; LECTOR connects related knowledge
- Adjusts intervals based on concept dependencies

### SSP-MMC: Reinforcement Learning Approach

```
- Combines RL with cognitive modeling
- Agent learns optimal review timing through trial and error
- Personalized scheduling without explicit memory model
- Experimental -- not yet mainstream
```

### Relevance to Wiii

Wiii's SM-2 implementation is functional but dated. **Recommendation: migrate to FSRS** for the following reasons:
1. SM-2 is a 1987 algorithm; FSRS is ML-trained on modern data
2. FSRS adapts to Wiii's specific learning patterns
3. 20-30% efficiency gain means fewer heartbeat cycles spent on review
4. FSRS-6 supports same-day reviews (useful for rapid skill learning)
5. Open-source Python implementation available: `open-spaced-repetition/fsrs4anki`

---

## 11. Emotional AI / Affective Computing

### Emotion Models in AI Agents

Major models in current use:

```
PAD Model (Pleasure-Arousal-Dominance):
  - 3 continuous dimensions
  - Pleasure: positive/negative valence
  - Arousal: high/low activation
  - Dominance: sense of control
  - Used by: academic research, some game AI

Russell's Circumplex (Valence-Arousal):
  - 2D simplification of PAD
  - Maps emotions on a circle
  - Used by: many commercial systems

OCC Model (Ortony-Clore-Collins):
  - 22 emotion categories
  - Event-based triggers (appraisal theory)
  - Used by: BDI agent architectures, game AI

Wiii's 4D Model:
  - primary_mood (categorical, 10 states)
  - energy_level (continuous 0-1)
  - social_battery (continuous 0-1)
  - engagement (continuous 0-1)
  - Unique hybrid: categorical mood + 3 continuous dimensions
```

### Computational Emotion Simulation (2024-2025)

Recent CHI research integrates appraisal theory with reinforcement learning:
- Emotion as **continuous process** (not static state)
- Cognitive-emotional appraisal mechanisms
- Value predictions from RL drive emotional responses
- Emotion regulates behavior (not just coloring output)

### Circadian Rhythm in AI

Wiii appears to be **one of the few systems** implementing circadian rhythm for AI agents. The search results show no other major AI companion or agent platform with:
- Time-of-day energy curves
- Circadian mood hints
- Vietnamese timezone-aware tone adjustment

This is a genuine differentiator.

### Emotional Dampening

Wiii's emotional dampening system (Sprint 210b) addresses a real problem: **mood ping-pong from concurrent users**. The accumulator pattern (accumulate sentiment, threshold before mood change, cooldown timer) is a practical engineering solution not found in academic literature, which typically assumes single-user interaction.

### Relevance to Wiii

Wiii's 4D emotion model is pragmatically superior to academic models for an AI companion use case:
- PAD/Circumplex are too abstract (hard to translate to behavioral changes)
- OCC has too many categories (22 is over-specified for behavioral modifiers)
- Wiii's 4D model maps directly to behavioral modifiers (response_style, humor, proactivity, social)

**Potential improvement**: Add a 5th dimension: **curiosity/exploration drive** (0-1). This would separate "interest in learning" from "engagement with current task." Currently engagement serves double duty.

---

## 12. Agent-to-Agent Communication

### Google A2A Protocol (April 2025)

The industry standard for agent-to-agent communication:

```
AGENT CARD (/.well-known/agent.json):
{
  "name": "Agent Name",
  "description": "What this agent does",
  "url": "https://agent.example.com",
  "skills": [
    {"id": "skill-1", "name": "...", "description": "..."}
  ],
  "authentication": {
    "schemes": ["bearer"],
    "credentials": "..."
  }
}

TASK LIFECYCLE:
  submitted -> working -> input-required -> completed/failed

TRANSPORT:
  - Synchronous: HTTP request/response (JSON-RPC)
  - Streaming: SSE for real-time updates
  - Async: Push notifications for long-running tasks

CONTENT TYPES:
  - TextPart: plain text
  - FilePart: binary attachments
  - DataPart: structured JSON
```

### Protocol Landscape (2026)

```
MCP (Model Context Protocol):
  - Agent-to-tool connections
  - Anthropic-originated, now Linux Foundation
  - "How agents use tools"

A2A (Agent2Agent Protocol):
  - Agent-to-agent coordination
  - Google-originated, now Linux Foundation
  - "How agents talk to each other"

ACP (Agent Communication Protocol):
  - Lightweight messaging
  - Simpler than A2A for basic inter-agent messaging
```

### Wiii's Soul Bridge vs A2A

Wiii's Soul Bridge (Sprint 213) predates A2A's public release and has a different design philosophy:

```
SOUL BRIDGE (Wiii):
  - Focus: Emotional/personality communication between AI "souls"
  - Transport: WebSocket primary + HTTP fallback
  - Anti-echo: prevents message loops
  - Dedup cache: 5-min TTL
  - Priority-based retry
  - Agent Cards at /.well-known/agent.json (aligns with A2A!)
  - EventBus integration for internal events

A2A (Google):
  - Focus: Task delegation and capability discovery
  - Transport: HTTP + SSE + async push
  - Formal task lifecycle (states, artifacts)
  - Enterprise auth (OAuth, short-lived tokens)
  - 50+ technology partners
```

### Relevance to Wiii

Wiii's Soul Bridge and Google's A2A serve different but complementary purposes. Soul Bridge is for **personality-level communication** (sharing emotional state, soul reflection); A2A is for **task-level coordination** (delegate work, share results).

**Recommendation**: Implement A2A compatibility in Soul Bridge. Since Wiii already publishes Agent Cards at `/.well-known/agent.json`, adding A2A task lifecycle support would make Wiii interoperable with the broader agent ecosystem while keeping Soul Bridge's emotional communication layer.

---

## 13. Comparison with Wiii Living Agent System

### Feature Matrix

| Feature | Wiii | Character.AI | Replika | Nomi | Kindroid | Inworld | Letta |
|---------|------|-------------|---------|------|----------|---------|-------|
| Persistent Personality | Yes (YAML + Identity Core) | Partial (embeddings) | Yes (fine-tuned) | Yes | Yes (Backstory) | Yes (Character Brain) | Yes (Persona Block) |
| Emotional State | 4D model + circadian | No | Bonding level only | Limited | No | Triggers only | No |
| Autonomous Behavior | Yes (heartbeat, 30min) | No | No | No | No | Goals/triggers | No |
| Skill Learning | SM-2 spaced repetition | No | No | No | No | No | Procedural memory |
| Journal/Diary | Yes (LLM-generated) | No | Yes (diary entries) | No | Key Memories | No | Episodic memory |
| Self-Reflection | Weekly + identity insights | No | Daily (Ultra) | No | No | No | Reflection loop |
| Memory Persistence | DB-backed (PostgreSQL) | Session only | 3-tier | Structured notes | Dual-layer | Flash + long-term | 3-tier (core/recall/archival) |
| Circadian Rhythm | Yes (UTC+7, hourly curve) | No | No | No | No | No | No |
| Emotional Dampening | Yes (cooldown + threshold) | No | No | No | No | No | No |
| Relationship Tiers | 3-tier (creator/known/other) | No | Bonding level | No | No | NPC relationships | No |
| Agent-to-Agent Comms | Soul Bridge (WebSocket) | No | No | No | No | No | No |
| Multi-Tenant | Yes (org isolation) | No | Per-user | No | Per-user | Per-game | Per-agent |
| Three-Layer Identity | Soul/Identity/Context | No | No | No | Backstory/Keys | Brain/Mesh/Runtime | Core/Recall/Archival |

### Wiii's Unique Advantages

1. **Most complete system**: 22 modules, 8,500+ LOC -- no competitor has this breadth
2. **Circadian rhythm**: Unique in the market
3. **Emotional dampening for multi-user**: Unique engineering for classroom/enterprise use
4. **Skill learning with SM-2**: Only Letta's procedural memory comes close
5. **Three-Layer Identity with drift prevention**: Soul Core validation is architecturally sound
6. **Autonomous heartbeat**: True autonomy loop -- not just reactive to user input

### Wiii's Gaps vs SOTA

1. **Memory retrieval**: No three-factor scoring (recency + relevance + importance) from Stanford
2. **SM-2 is dated**: FSRS-6 would be 20-30% more efficient
3. **No persona self-editing**: Letta V1 allows agent to rewrite its own prompt
4. **No sleep-time memory processing**: Letta's async pattern is more efficient than inline processing
5. **No A2A protocol compatibility**: Missing interoperability with Google's ecosystem
6. **Personality as text only**: Character.AI's embedding-based personality enables mathematical drift tracking

---

## 14. Recommendations

### Priority 1: Migrate SM-2 to FSRS (Low effort, high impact)

Replace the SM-2 algorithm in `skill_learner.py` with FSRS-6. Open-source implementation available. Expected 20-30% review efficiency gain.

### Priority 2: Three-Factor Memory Retrieval (Medium effort, high impact)

Add Stanford's `score = alpha*recency + beta*relevance + gamma*importance` to semantic memory retrieval. This improves which memories are surfaced during conversation.

### Priority 3: Persona Self-Editing (Medium effort, medium impact)

Allow Identity Core to not just generate insights but actually modify the system prompt injection. When a validated insight reaches high confidence, it should become part of the prompt template.

### Priority 4: Sleep-Time Memory Processing (Low effort, architectural improvement)

The heartbeat already runs every 30 minutes. Add explicit memory consolidation steps:
- Extract facts from recent conversations -> semantic memory
- Distill notable interactions -> episodic memory (journal)
- Update behavioral rules -> procedural memory (skill notes)

### Priority 5: A2A Protocol Compatibility (Medium effort, future-proofing)

Add A2A task lifecycle support to Soul Bridge. Wiii already has Agent Cards -- extending to A2A makes Wiii interoperable with the growing ecosystem of 50+ A2A-compatible platforms.

### Priority 6: 5th Emotion Dimension -- Curiosity Drive (Low effort, enhancement)

Add `curiosity_drive: float` (0-1) to EmotionalState. Separate from engagement (which tracks current-task focus), curiosity tracks desire to explore new topics/skills.

### NOT Recommended

- **Embodied cognition (Soul Machines approach)**: Commercially failed, over-engineered for text-based AI
- **Custom model fine-tuning (Replika approach)**: Too expensive, prompt engineering + rules is sufficient
- **22-category emotion model (OCC)**: Over-specified for behavioral modification use case

---

## Sources

### Character.AI
- [EmergentMind: Character.AI Platform](https://www.emergentmind.com/topics/character-ai-c-ai)
- [Alibaba: Character AI Overview 2026](https://www.alibaba.com/product-insights/character-ai-overview-what-it-is-how-it-works-and-its-key-features-in-2026.html)

### Replika
- [CompanionGuide: Replika Review 2026](https://companionguide.ai/companions/replika)
- [AICompanionGuides: Replika Review 2026 (47 Days)](https://aicompanionguides.com/blog/replika-review/)
- [Nomi.ai: Replika vs Nomi 2026](https://nomi.ai/ai-today/replika-vs-nomi-2026-finding-enduring-ai-companionship/)

### Anthropic Claude's Constitution
- [Anthropic: Claude's Character (Official)](https://www.anthropic.com/research/claude-character)
- [Anthropic: Claude's New Constitution (January 2026)](https://www.anthropic.com/news/claude-new-constitution)
- [Anthropic: Claude's Constitution (Full Text)](https://www.anthropic.com/constitution)
- [TechCrunch: Anthropic Revises Claude's Constitution](https://techcrunch.com/2026/01/21/anthropic-revises-claudes-constitution-and-hints-at-chatbot-consciousness/)
- [TIME: Anthropic Publishes Claude's New Constitution](https://time.com/7354738/claude-constitution-ai-alignment/)

### Stanford Generative Agents
- [Stanford HAI: AI Agents Simulate 1052 Individuals](https://hai.stanford.edu/news/ai-agents-simulate-1052-individuals-personalities-with-impressive-accuracy)
- [Stanford HAI: Simulating Human Behavior](https://hai.stanford.edu/policy/simulating-human-behavior-with-ai-agents)
- [arXiv: Generative Agents Paper](https://arxiv.org/abs/2304.03442)

### Soul Machines
- [Soul Machines Official](https://www.soulmachines.com/)
- [BusinessWire: Soul Machines Digital Workforce](https://www.businesswire.com/news/home/20250902528461/en/Soul-Machines-Unveils-Digital-Workforce---Human-like-Interface-Set-to-Redefine-How-AI-Is-Used-Across-The-Enterprise)

### Inworld AI
- [Inworld: New AI Infrastructure for Scaling](https://inworld.ai/blog/new-ai-infrastructure-scaling-games-media-characters)
- [Inworld: What is a Character Engine](https://inworld.ai/blog/what-is-a-character-engine-a-game-engine-for-ai-npcs)
- [NVIDIA: Inworld Generative AI NPCs](https://blogs.nvidia.com/blog/generative-ai-npcs/)
- [Lightspeed: Building With Inworld](https://lsvp.com/stories/inworld-ai-npcs-character-engine/)

### LangChain/LangGraph/Letta
- [LangChain Blog: LangMem SDK Launch](https://blog.langchain.com/langmem-sdk-launch/)
- [LangChain Docs: Memory Overview](https://docs.langchain.com/oss/python/langgraph/memory)
- [LangMem Conceptual Guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [Letta (MemGPT) GitHub](https://github.com/letta-ai/letta)
- [Letta Docs: MemGPT Concepts](https://docs.letta.com/concepts/memgpt/)
- [Letta Blog: V1 Agent Architecture](https://www.letta.com/blog/letta-v1-agent)
- [Letta Blog: Agent Memory](https://www.letta.com/blog/agent-memory)
- [MongoDB: Long-Term Memory with LangGraph](https://www.mongodb.com/company/blog/product-release-announcements/powering-long-term-memory-for-agents-langgraph)

### AI Companions Market
- [AICompanionGuides: Best AI Companion Apps 2026](https://aicompanionguides.com/blog/best-ai-companion-apps-2026/)
- [AIInsights: Character.AI vs Kindroid vs Nomi 2026](https://aiinsightsnews.net/character-ai-vs-kindroid-vs-nomi/)
- [AIInsights: Fix AI Companion Memory Loss 2026](https://aiinsightsnews.net/ai-companion-memory-fix/)

### Spaced Repetition
- [FSRS Algorithm: Next-Gen Spaced Repetition](https://www.quizcat.ai/blog/fsrs-algorithm-next-gen-spaced-repetition)
- [FSRS vs SM-2 Guide](https://memoforge.app/blog/fsrs-vs-sm2-anki-algorithm-guide-2025/)
- [FSRS Spaced Repetition Wiki](https://github.com/open-spaced-repetition/fsrs4anki/wiki/spaced-repetition-algorithm:-a-three%E2%80%90day-journey-from-novice-to-expert)
- [arXiv: LECTOR (LLM-Enhanced Spaced Learning)](https://www.arxiv.org/pdf/2508.03275)

### Affective Computing
- [AIMultiple: Affective Computing Guide 2026](https://research.aimultiple.com/affective-computing/)
- [arXiv: Emotions in Artificial Intelligence](https://arxiv.org/html/2505.01462v2)
- [CHI 2024: Computational Emotion with RL](https://dl.acm.org/doi/10.1145/3613904.3641908)

### Agent-to-Agent Communication
- [Google Developers: A2A Protocol Announcement](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [A2A Protocol Specification v0.2.5](https://a2a-protocol.org/v0.2.5/specification/)
- [GitHub: A2A Project](https://github.com/a2aproject/A2A)
- [IBM: What Is Agent2Agent Protocol](https://www.ibm.com/think/topics/agent2agent-protocol)
- [InfoWorld: Developer Guide to MCP, A2A, and ACP](https://www.infoworld.com/article/4007686/a-developers-guide-to-ai-protocols-mcp-a2a-and-acp.html)

### OpenAI
- [OpenAI: Memory and New Controls](https://openai.com/index/memory-and-new-controls-for-chatgpt/)
- [CBOT: ChatGPT Personalization Guide](https://www.cbot.ai/personalizing-llms-chatgpt-and-custom-gpts-for-individual-users/)
