# Thinking Architecture Pivot

Date: 2026-03-30

## Executive Verdict

The external expert is broadly correct about the core problem:

- Wiii currently mixes **native model-authored thinking** and **simulated post-authored public thinking**.
- That split is the main reason tutor/direct gray rail still feels forced, repetitive, and "written about thinking" rather than thought in the moment.

However, the exact recommendation "surface raw native thinking directly to users and delete all curation" is too blunt for Wiii.

For Wiii, the right 2026 architecture is:

1. **Native model-authored thought becomes the primary thinking authority**
2. **Prompt personality/soul comes from the same YAML + character backbone as answer generation**
3. **Post-processing remains, but only as lightweight safety/curation**
4. **Draft/repair LLM rewriting is sunset**

In short:

- Do **not** keep `public_thinking_draft_service.py` as the long-term author of gray rail
- Do **not** jump to "render raw thought blocks unfiltered forever"
- Move to **single-generation, native-thinking-first, curated-display-second**

## Evidence From This Repo

### 1. The repo already supports native thinking

Files:
- [llm_factory.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_factory.py)
- [gemini_provider.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/llm_providers/gemini_provider.py)
- [thinking_post_processor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/thinking_post_processor.py)

Observed facts:
- Gemini is created with `thinking_budget` and optional `include_thoughts=True`
- `thinking_post_processor.py` already treats Gemini native thought blocks as **priority 1**
- `<thinking>...</thinking>` tags are already treated as fallback

That means the platform is **not blocked by provider capability**.
The capability exists today.

### 2. PromptLoader already points toward this architecture

File:
- [base/_shared.yaml](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/base/_shared.yaml)

Important repo truth:
- comment says `Gemini native thinking API is PRIMARY`
- `<thinking>` tags are explicitly described as fallback
- shared prompt already includes a unified `thinking` section

This is important because it means the repo's own prompt layer had already intended to go native-first.

### 3. The current anti-pattern is the extra authoring layer

File:
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)

This service currently:
- asks another LLM call to write public gray-rail prose
- scores it against handcrafted heuristics
- may run a repair pass
- then passes that rewritten prose into the visible thinking surface

That is the exact place where:
- latency increases
- token cost increases
- style becomes self-conscious
- "thinking" can drift away from the actual answer-generation flow

## Comparison Against 2026 Vendor Direction

### Anthropic

Official docs indicate:
- interleaved/extended thinking is model-owned and can happen between tool calls
- Opus 4.6 uses adaptive thinking by default
- Anthropic recommends preferring **general instructions over prescriptive step-by-step reasoning plans**

Sources:
- [Anthropic Extended Thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)
- [Anthropic Prompting Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)

### Google Gemini

Official docs indicate:
- Gemini thinking is a native internal process
- APIs can return **thought summaries**
- models support dynamic/adaptive thinking and thought signatures
- thinking can be reviewed and debugged without inventing a second authoring model

Sources:
- [Gemini Thinking](https://ai.google.dev/gemini-api/docs/thinking)
- [Gemini Thought Signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)

## What The Expert Got Right

### Correct
- `draft + repair` is not the end-state architecture
- over-steering makes thinking fake
- few-shot style guidance is better than a growing pile of behavioral rules
- native model thinking should lead answer generation, not trail it

### Only Partly Correct
- "Delete all curation and just render raw `<thinking>`"

That is too simple for Wiii because Wiii is:
- multi-lane
- multi-agent
- public-facing
- living/persona-rich
- sometimes retrieval-based, sometimes tutoring, sometimes memory/social

So Wiii still needs a **public-thinking safety boundary**.

But that boundary should be:
- sanitize
- redact
- suppress
- dedupe
- present

It should **not**:
- re-author
- rewrite into a fake reasoning script
- grade style with a second LLM pass on every turn

## Target Architecture

### Authority Model

#### Answer authority
- final answer remains the canonical answer output of the main generation path

#### Thinking authority
- primary source: model-authored native thought summary / `<thinking>` content produced in the same generation stream
- secondary source: lane-owned fallback only when native thinking is unavailable

### Prompt Architecture

One thinking architecture, not four competing layers:

1. **Character/Soul YAML**
   - Wiii identity
   - Wiii soul
   - tone/relationship/continuity

2. **Shared thinking instruction**
   - short
   - lane-aware
   - not over-prescriptive

3. **Few-shot behavioral examples**
   - high quality
   - diverse
   - by lane
   - a few only

4. **Native generation**
   - model thinks before answering
   - same stream, same cognition, same turn

5. **Lightweight curator**
   - strip meta
   - strip answer-draft leakage
   - strip technical telemetry
   - dedupe obvious repeats
   - keep or suppress
   - never rewrite substance unless absolutely necessary

## Concrete Repo Pivot

### Keep
- [base/_shared.yaml](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/base/_shared.yaml)
- [thinking_post_processor.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/services/thinking_post_processor.py)
- [living_thinking_context.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/living_thinking_context.py)
- [public_thinking_renderer.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_renderer.py) as a sanitizer/presenter only

### Sunset
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)
  as an authoring service
- its repair prompt
- most beat-shape scoring heuristics

### Move into YAML/shared prompt
- Wiii public-thinking soul guidance
- 3-5 few-shot high-quality examples
- lane-specific behavioral examples for:
  - tutor
  - direct
  - memory
  - rag

## Recommended Migration Plan

### Phase 1: Native-First Tutor
- tutor prompt uses one unified `thinking` instruction from shared YAML + living persona
- if Gemini native thoughts are present, treat them as primary
- `public_thinking_draft_service` moves to shadow mode only
- renderer only sanitizes and suppresses leaks

### Phase 2: Remove Tutor Repair
- remove LLM repair pass
- keep only deterministic filtering/sanitization
- compare quality against user probes

### Phase 3: Expand to Direct
- same architecture for direct lane
- remove scaffold-like direct gray rail

### Phase 4: Lane-Specific Fallbacks
- only use handcrafted lane fallback when provider/native thought is absent
- fallback text must be minimal and clearly treated as degraded mode

### Phase 5: Retire Draft Service
- delete or archive `public_thinking_draft_service.py`
- replace with:
  - native extraction
  - few-shot prompting
  - light curation

## Design Principle For Wiii

Wiii is not Claude.
Wiii is a living agent.

So the goal is not:
- raw vendor-neutral thought exposure

The goal is:
- **native reasoning**
- **Wiii soul**
- **one cognition path**
- **public-safe presentation**

This means:
- the gray rail should feel like Wiii
- but it should still come from the same act of thinking that produced the answer
- not from a second model call pretending to be that thinking

## Final Recommendation

Adopt the expert's architectural direction, with one refinement:

> Replace "Simulated Thinking" with "Native Thinking + Light Curation", not with "Raw Unfiltered Thought Streaming".

That is the correct 2026 path for Wiii.
