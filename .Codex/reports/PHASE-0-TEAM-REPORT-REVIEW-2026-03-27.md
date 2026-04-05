# Phase 0 Team Report Review — Wiii Thinking Root Cause Audit

> Date: 2026-03-27
> Reviewer: Codex (Leader)
> Scope: Review team report about Phase 0 cleanup, compare against current local code, historical `LMS_AI` git history, and official product patterns from Anthropic / Google Gemini / Kimi.

---

## Executive Verdict

The team report is directionally right about one thing:

- pipeline `status` leakage was a real problem
- hiding runtime/status-only events is necessary
- Wiii thinking quality does improve when a stronger Gemini path is available

But the report is still **misdiagnosing the deepest cause**.

The main problem is **not primarily provider quality**.
The deeper problem is that the current architecture still treats visible thinking as a **secondary narrated product** generated on top of agent execution, instead of a **single coherent thinking surface** owned by one reasoning lane.

### Final verdict

- `Phase 0 cleanup as status-leak reduction`: **partly valid**
- `Phase 0 as thinking-quality fix`: **not valid yet**
- `Switch back to Gemini preview and quality will recover`: **not sufficient and not currently provable**

---

## Key Findings

### [P0] Current design still duplicates thinking by architecture

The biggest issue is not wording alone.
It is the current event shape:

1. Supervisor emits visible thinking
2. Direct / tutor / rag / code node emits another visible thinking beat
3. `thinking_start.summary` is emitted
4. the same summary is often sent again as `thinking_delta`
5. then another beat is synthesized for `synthesize` or tool transition

This creates gray rail content that feels:

- repetitive
- meta
- narrated-from-above
- less like Wiii actually thinking in one continuous voice

### Evidence in current code

- `_render_reasoning_fast()` is no longer “fast local only”; it now calls the LLM narrator directly:
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:545)
- direct lane opens a thinking block and immediately re-sends the same summary as delta:
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:3249)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:3257)
- the same duplication pattern appears again in direct synthesis:
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:3564)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:3571)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:3587)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:3594)
- rag/tutor/search adapters still synthesize opening thinking and then emit more thinking later:
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:6539)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:6546)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:6629)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:6636)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:6712)
  - [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:6719)

This is a design-level duplication, not just a prompt problem.

---

### [P0] The report says “thinking thật = agent node astream tokens”, but current code contradicts that

The report claims:

> Thinking thật = agent node's astream() tokens

That is not fully true in the current implementation.

For many lanes, visible thinking is still synthesized by narrator calls before or around execution, not purely by native agent stream tokens.

### Evidence

- `graph_streaming.py` still calls narrator LLM for fallback narration after node completion:
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:376)
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:380)
- direct / rag / tutor / memory / code studio branches still emit narrator-based `thinking_start` around node outputs:
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:1200)
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:1310)
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:1422)
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:1485)
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:1653)
  - [graph_streaming.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py:1706)

So the system is still doing:

- execution
- then narrator about execution
- then UI rendering of narrator

instead of one unified stream of visible thought.

---

### [P0] “LLM-first, no grammar cứng” is being interpreted too loosely

The philosophical intention is good:

- Wiii should not sound templated
- thinking should not be rigidly boxed into option arrays

But the current implementation risks overcorrecting into:

- no stable acceptance criteria
- no hard distinction between valid inner voice and generic meta voice
- no protection against duplicated semantic beats

For Wiii, “LLM-first” should mean:

- the model chooses the exact words
- but the architecture still enforces **surface invariants**

It should **not** mean:

- every layer is free to narrate
- duplicated narrated beats are acceptable if they are model-written

This distinction matters.

---

### [P1] Forcing house routing to `settings.llm_provider` is operationally brittle

The new `_resolve_house_routing_provider()` returns the configured provider directly:

- [supervisor.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py:1013)

And `_get_effective_provider()` then propagates that house choice into agent nodes:

- [graph.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:488)

This means when `settings.llm_provider=google` but Google is busy, local dev can degrade into:

- immediate stream errors
- sync `503`
- or no meaningful thinking at all

I confirmed live today:

- `/api/v1/chat` with `provider=google` returned `503`
- `/api/v1/chat/stream/v3` with `provider=google` returned:
  - `Provider tam thoi ban hoac da cham gioi han.`

So the report’s architecture path:

> supervisor house provider -> agent nodes use Google -> no fallback Zhipu

is not just a theoretical simplification.
It is a real availability regression for local debugging and for any rollout where Google is under pressure.

---

### [P1] Current narrator prompt is still too meta and too self-conscious

The narrator prompt has good intentions:

- Soul-First Rule
- Adaptive Depth
- Deletion Test
- Core Identity

But the prompt is still structured as an instruction manual about thinking.
That creates a common failure mode:

- the model writes “about how it is thinking”
- instead of simply sounding like Wiii thinking

### Evidence

- [reasoning_narrator.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\reasoning_narrator.py:289)
- [reasoning_narrator.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\reasoning_narrator.py:296)
- [reasoning_narrator.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\reasoning_narrator.py:311)
- [reasoning_narrator.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\reasoning_narrator.py:397)
- [reasoning_narrator.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\reasoning_narrator.py:404)

This is one reason current thinking often lands in phrases like:

- “Mình đang nghe kỹ câu này trước đã...”
- “Mình muốn đứng lại với câu này thêm một nhịp...”
- “Mình đang chắt lấy điều cốt lõi...”

These are not terrible sentences.
But at scale, they become a recurrent narrator dialect, not Wiii’s lived inner surface.

---

## Live Runtime Check

I verified current runtime behavior on local server:

- `GET /api/v1/health/live` -> alive
- `POST /api/v1/chat` with `provider=google` -> `503`
- `POST /api/v1/chat/stream/v3` with `provider=google` -> busy error
- `POST /api/v1/chat` with `provider=zhipu` -> returns thinking, but still generic and meta
- `POST /api/v1/chat/stream/v3` with `provider=zhipu` -> shows duplicated supervisor + direct thought beats

### Example observed for `Buồn quá` with Zhipu

The stream currently does this:

1. supervisor thinking block
2. same thought repeated as supervisor delta
3. same supervisor thought repeated again
4. direct thinking block
5. direct summary emitted again as delta
6. second direct rephrasing
7. answer starts

So even if the wording improves, the **surface choreography** is still wrong.

---

## What The Old Git History Gets Right

The most useful comparison is not the current snapshot of `main`, but specific historical commits in `LMS_AI`.

Important commits:

- `f130852` — `Hide tool_think from UI — raw LLM planning is not for users`
- `3cdfe85` — `Fix E2E streaming: session merge + progressive chunks + hide duplicates`
- `11b7ac8` — `Hybrid 3-tier thinking labels: short headers, full body, Wiii voice`
- `a5d0e68` — `Chat streaming UX polish Phase 2: fix thinking leak, visual clipping, shimmer labels`
- `3bb6438` — `Answer first, sources second`

These commit messages matter because they show the earlier successful direction:

1. hide raw planning from user
2. hide duplicates aggressively
3. let Wiii voice sit in the body, not in technical trace
4. keep answer/artifact central

That is much closer to what the user has been asking for.

---

## Comparison With Major Systems

### Anthropic / Claude

Anthropic’s official docs for extended thinking and streaming emphasize:

- thinking and text arrive as distinct content blocks
- tool use and thinking must be handled separately
- clients should be prepared for interleaving, but not flatten everything into one undifferentiated blob

Sources:

- [Anthropic Extended Thinking](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking)
- [Anthropic API release notes](https://docs.anthropic.com/en/release-notes/api)

The key lesson is:

> typed separation is necessary

Claude does **not** imply:

> every orchestration layer should produce its own visible mini-monologue

### Kimi / Moonshot

Moonshot’s official posts around tool use and Kimi platform updates point in a similar direction:

- direct tool behavior is often preferred by default
- returning full thinking is a product choice to enable selectively
- the platform emphasizes streaming output support, not “surface every internal step”

Sources:

- [Kimi API update — tool use defaults to direct tool behavior](https://platform.moonshot.ai/blog/posts/kimi-api-update-amazon-cloud-china-summit)
- [Kimi Open Platform changelog — streaming output support](https://platform.moonshot.ai/blog/posts/changelog)

The lesson here is:

> more reasoning capability does not mean more layers of visible reasoning should be surfaced

### Google Gemini

Google’s official docs clearly note:

- preview models may have more restrictive rate limits
- production apps should prefer stable, pinned models when possible

Sources:

- [Gemini models](https://ai.google.dev/gemini-api/docs/models/gemini)
- [Gemini pricing](https://ai.google.dev/pricing)
- [Gemini quota docs](https://ai.google.dev/gemini-api/docs/quota)

So the report is right to worry about preview rate limits.
But model stability is a deployment concern, not the root explanation for duplicated or meta thinking.

---

## What I Agree With In The Team Report

These choices are good:

- tagging pipeline statuses as `status_only`
- removing old hardcoded template arrays in supervisor
- keeping Phase 0 focused on surface before memory/living rollout
- recognizing Google preview rate limits as a real ops concern

---

## What I Do Not Approve Yet

### 1. Replacing local/fallback narration with LLM narrator everywhere

This makes visible thinking:

- slower
- more provider-dependent
- more meta
- more repetitive if multiple nodes narrate

It improves richness in the best case, but worsens coherence in the common case.

### 2. Treating Gemini availability as the main path to good thinking

It may improve quality, but it does not solve:

- duplicate beat emission
- summary-delta echo
- supervisor/direct double narration
- over-narrated orchestration

### 3. Declaring current architecture “thinking thật”

That phrase is too strong for the current implementation.
It is still a hybrid of:

- orchestrator narration
- agent-node narration
- native token stream

and the UX still feels stitched.

---

## Recommended Direction

### Immediate

1. Keep `status_only` cleanup
2. Do **not** let every phase call LLM narrator
3. Restrict visible narrated thinking to exactly one owner per turn-stage
4. Stop emitting `summary` as both `thinking_start` body and first `thinking_delta`
5. Let `thinking_delta` carry incremental content only

### For direct/emotional/identity turns

Use one simple rule:

- either supervisor attunes visibly
- or direct attunes visibly
- not both

For most short turns, direct should own visible thinking.
Supervisor should remain hidden or status-only.

### For knowledge / visual turns

Use:

- one opening thought
- compact action bridge if needed
- then native answer/artifact progression

Not:

- opening thought
- duplicate delta
- round thought
- tool reflection
- synthesis thought
- all surfaced as if they are the same inner monologue

---

## Suggested Team Decision

I recommend marking the team report as:

- `useful but incomplete`
- `accepted for status-leak cleanup`
- `not accepted as final explanation of thinking quality`

### Best short phrasing

> Phase 0 improved the hygiene of the gray rail, but did not yet restore Wiii’s true thinking surface.

That is the most accurate summary of the current state.

