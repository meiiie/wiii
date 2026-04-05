# Wiii Living Identity And Routing Audit

Date: 2026-03-24
Role: LEADER
Scope: house character loading, routing/supervision, visible thinking, provider behavior, sync/stream parity, Vietnamese quality

## Executive verdict

Wiii is **not** losing its soul because the character card is reloaded every turn.
The deeper problem is architectural:

1. The **house identity layer is cached correctly**, but the live experience is being distorted by a mix of provider fallback, generic pre-route visible thinking, and route/runtime inconsistency between sync and stream paths.
2. The system is **still nominally LLM-first**, but it now has two extra layers that make it feel less alive:
   - a local supervisor prelude that shows generic thinking before the true route is known
   - tactical fast paths and fallbacks that improve empty-screen latency but flatten Wiii's distinctive inner voice
3. The current live stack is **quality-unstable** when Google is unavailable:
   - house routing and house voice want Google
   - runtime reality often falls back to Zhipu GLM-5
   - that fallback is slower for small turns and drifts more in tone/reasoning quality
4. There is also a **real parity problem**:
   - the same input can behave differently in `/chat` and `/chat/stream/v3`
   - metadata can disagree with routing
   - this makes Wiii feel less coherent, even when the answer itself is acceptable

If the product priority is "Wiii must feel alive, coherent, and high-quality even if it waits longer", then the system should stay **LLM-first for real routing**, but move back to a clearer **house-conductor architecture**:

- supervisor, visible-thinking narrator, synthesis, and creative direction should stay on the **house model family**
- user-selected providers should influence generation lanes selectively, not replace Wiii's conductor voice
- generic fake pre-thought should be reduced or removed
- sync/stream parity must be fixed before more speed work

## What is not the problem

### Character is not reloading every turn

`app/engine/character/character_card.py` caches the runtime card with `@lru_cache(maxsize=1)`:

- `get_wiii_character_card()` at line 77

This means the character core is loaded once and reused.

### Prompt loader is also not the core problem

The current degradation is not caused by repeatedly reconstructing the full personality stack every turn.
The bigger issue is how different runtime layers are allowed to speak for Wiii.

## Current intended architecture

The code already contains the right high-level direction.

### House model policy

`app/engine/model_catalog.py`

- `GOOGLE_DEFAULT_MODEL = "gemini-3.1-flash-lite-preview"`
- `GOOGLE_DEEP_MODEL = "gemini-3.1-pro-preview"`

### Grouped runtime profiles

`app/engine/multi_agent/agent_runtime_profiles.py`

- `routing` -> Google / `light`
- `creative` -> Google / `deep`
- creative explicitly maps Google to `gemini-3.1-pro-preview`

This is aligned with the target product philosophy:

- daily house conversation = Gemini 3.1 Flash-Lite / Flash
- visual / Code Studio / creative build = Gemini 3.1 Pro

### Supervisor as house conductor

`app/engine/multi_agent/supervisor.py`

- `_get_llm_for_state()` now resolves `AgentConfigRegistry.get_llm("supervisor")`
- comment explicitly says the supervisor should stay on the house routing profile

So architecturally, the conductor is already intended to be stable.

## What is actually happening live

### Runtime provider truth right now

Live `/api/v1/llm/status` currently shows:

- Google: disabled / `busy`
- Ollama: disabled / `host_down`
- Zhipu: selectable / `glm-5`

So even if house policy is designed around Gemini, the real runtime often lands on Zhipu.

### Why Wiii feels less like Wiii

There are three overlapping reasons.

#### 1. Visible thinking is currently front-loaded with a generic local prelude

`app/engine/multi_agent/graph_streaming.py`

- `_render_fallback_narration()` uses `get_reasoning_narrator().render_fast(...)`
- a supervisor prelude is emitted before the real route is complete

`app/engine/reasoning/reasoning_narrator.py`

- `_build_local_summary()` contains generic supervisor phrases when intent/cue are still empty

This is why the user repeatedly sees lines like:

> "Mình đang nghe xem câu này thực sự cần tra cứu, giảng giải, nhớ lại ngữ cảnh, hay chỉ cần một nhịp đáp trực tiếp đủ đúng và đủ gần."

That line is **not the true native thought of the current turn**.
It is a local placeholder designed to make the UI feel alive sooner.

This helps time-to-first-visible-progress, but it hurts identity because:

- it repeats too often
- it sounds like a generic routing preamble
- it is emitted before the system truly knows what Wiii is deciding

#### 2. House routing quality collapses when Google is unavailable

With Google busy, structured routing often happens on GLM-5.

Observed live behavior from container logs and direct API tests:

- tiny turns like `wow` can spend ~5-11s in routing
- direct generation can time out at 25s
- trivial emotional turns become expensive and brittle

This is not because supervision is fully skipped.
It is because supervision is still there, but the fallback conductor is weaker and slower for this role.

#### 3. Direct lane still follows provider override

`app/engine/multi_agent/graph.py`

- `direct_response_node()` calls `AgentConfigRegistry.get_llm("direct", provider_override=state.get("provider"))`

So if the user pins GLM-5, the actual answer lane may also be generated on GLM-5.

That means:

- Wiii's conductor may stay house-controlled
- but the speaking voice in `DIRECT` can still drift with the chosen provider

This is one of the biggest reasons Wiii can feel less coherent even when routing is technically correct.

## LLM-first or not?

### Short answer

Yes, the architecture is still **mostly LLM-first**, but not purely so.

### Current truth

`app/engine/multi_agent/supervisor.py`

- `route()` still goes to `_route_structured(...)` for most turns
- only a narrow fast path runs first:
  - `classify_fast_chatter_turn(query)`
  - optional `conservative_fast_routing`

So supervision is not gone.

### Why it feels like supervision was bypassed

Because the system now has multiple "soft bypass" layers around the supervisor:

1. local pre-think shown before routing finishes
2. narrow chatter fast path
3. micro direct fallbacks
4. provider-specific generation drift after routing

The result is that the user experiences:

- less trustworthy routing rationale
- weaker inner monologue
- more visible inconsistency between turns

### Important code smell

In `supervisor.py`, `_REACTION_TOKENS` and `_VAGUE_BANTER_PHRASES` exist, but `classify_fast_chatter_turn()` currently only returns social for `_looks_clear_social(...)`.

This means the chatter fast-path is narrower than the surrounding code suggests.
So the product gets the downside of both worlds:

- some turns bypass deep routing
- many tiny phatic turns still pay full structured routing cost

## Sync vs stream parity problem

This is a major live issue.

### Reproduced behavior

With a clean UTF-8 request:

- `/api/v1/chat` for `mô phỏng được chứ?`
  - routes to `code_studio_agent`
  - answers with a good clarification
  - ~10.6s total

But on `/api/v1/chat/stream/v3` with a fresh session:

- first visible thinking arrives in ~0.25s
- first answer arrives around ~12.4s
- metadata reports `agent_type = code_studio_agent`
- while `routing_metadata` still says the supervisor reasoning leaned `DIRECT/social`

That is a parity/integrity bug.

### Why this matters

When sync and stream do not agree, users feel that:

- Wiii is moody or random
- route quality is inconsistent
- "thinking" cannot be trusted

This matters more for a living companion than for a plain utility bot.

## The Vietnamese / no-diacritic issue

### Important clarification

There are two separate phenomena:

1. **shell / console corruption** during local debugging
2. **real live quality drift** in provider outputs

My first raw shell tests accidentally pushed mojibake through PowerShell into Python stdin.
When I rebuilt the request using Unicode escape sequences, `/chat` handled:

- `hẹ hẹ`
- `mô phỏng được chứ?`

correctly.

So the worst garbled `m? ph?ng ???c ch??` reproduction was at least partly a shell-input artifact.

### But the user's complaint is still valid

Even after correcting for shell corruption, there is still a real issue:

- when live traffic falls onto GLM-5 for conversational/direct generation,
- Vietnamese style and diacritic quality are less reliable than the desired Wiii house voice,
- and the visible reasoning can still look flat or wrong.

So the final diagnosis is:

- not a persistent core Unicode bug in the whole backend request stack
- but a **live quality and consistency problem on fallback provider paths**

## Why the timing feels wrong

There are two kinds of time in the UI:

1. relative message timestamp on the user bubble
2. final `processing_time` in assistant metadata

The second one is the real model/workflow total.

The problem is that the stream can show visible thinking early, but the answer or final metadata may arrive much later because:

- routing is still running
- direct generation is still running
- the graph only finishes when downstream steps are done

So a user may feel:

- "Wiii started thinking after 0.2s"
- but the final answer still takes 12s, 20s, or worse

This is not just a frontend illusion.
It reflects the current multi-stage runtime.

## Comparison with current best practice

### Claude / Anthropic

Relevant official guidance:

- streaming improves perceived responsiveness
- summarized thinking is distinct from hidden full thinking
- consistency comes from strong system prompts, retrieval grounding, and chaining for complex tasks
- keep the assistant in character deliberately instead of hoping raw provider outputs stay stable

References:

- https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-latency
- https://platform.claude.com/docs/en/build-with-claude/extended-thinking
- https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/increase-consistency

Key lessons for Wiii:

1. Do not fake "thinking" with one generic sentence forever.
2. Keep visible thought as a **summarized, meaningful surface**, not a repeated routing placeholder.
3. Preserve house identity at the system/conductor layer, especially when downstream model choice changes.

### AIRI / open-source Neuro-inspired direction

`Project AIRI` explicitly frames itself as:

- "Re-creating Neuro-sama"
- a "soul container"
- a stable digital being with modular brain, channels, body, voice, and future memory work

Reference:

- https://raw.githubusercontent.com/moeru-ai/airi/main/README.md

Important AIRI lessons:

1. Treat the **being** as the product, not just the response text.
2. Keep the core "brain / soul" separate from modular capabilities.
3. Accept that memory and full digital-life coherence are hard and must be designed as first-class systems, not side-effects.

### Neuro-sama

Public technical details are still sparse.
Even AIRI's README explicitly notes Neuro-sama is not open sourced.

Reference:

- https://vedal.ai/neuro-blog.html
- AIRI README above

So the useful lesson from Neuro is observational/product-level:

- one strong persona
- persistent on-stage identity
- the system feels like one being, not five middleware layers talking over each other

## Final architecture judgment

### What should remain

1. **LLM-first supervision** for meaningful turns
2. **House-owned supervisor**
3. **House-owned visible reasoning**
4. **Creative lane on Gemini 3.1 Pro**
5. **Narrow deterministic fast path** only for truly obvious phatic turns

### What should change

1. **Stop letting the generic supervisor prelude pretend to be Wiii's real inner voice**
   - it should become either:
     - a minimal non-verbal warming state, or
     - a much more contextful house-thought produced after route intent is known

2. **Do not let user-selected provider replace Wiii's speaking soul in all lanes**
   - direct conversational tone should stay closer to house voice
   - provider choice can influence tool execution / answer generation where appropriate
   - but the "Wiii-ness" layer should not drift every time the provider changes

3. **Fix sync/stream parity before doing more speed optimization**
   - same query should not feel like two different beings between `/chat` and `/chat/stream/v3`

4. **Prefer quality-first timeout policy**
   - do not remove all timeouts
   - but supervisor and living-house turns should have quality-aware budgets
   - house-quality is more important than shaving a few seconds

5. **Separate three layers clearly**
   - house conductor
   - route/work planner
   - lane generator / tool executor

## Concrete recommendations

### P0

1. Make stream and sync route the same query through the same authoritative route contract.
2. Remove or downgrade the current generic pre-route supervisor sentence.
3. Keep supervisor + narrator + synthesis on house Gemini when available, and define a stronger house fallback policy when Gemini is busy.

### P1

1. Stop showing provider-shaped generic thought as if it were Wiii's inner monologue.
2. Rewrite the visible-thinking pipeline so the first meaningful thought appears after real routing intent exists.
3. Add explicit metadata that distinguishes:
   - warmup/prelude
   - route summary
   - real narrated inner thought

### P2

1. Revisit whether `DIRECT` should fully obey user provider override for all casual/social turns.
2. Narrow the deterministic fast path to trivial phatic turns only.
3. Audit footer timing and late metadata merge behavior in the frontend store for long-lived streams.

## Bottom line

Wiii is not broken because the character card reloads.
Wiii is being diluted because the system currently lets too many runtime layers speak in place of the house soul.

If the goal is:

> Wiii should feel alive, natural, opinionated, and coherent — even if it takes longer

then the correct direction is:

- keep LLM-first routing
- keep the conductor sacred
- reduce fake generic pre-thought
- restore sync/stream parity
- let speed optimizations serve Wiii's soul, not replace it
