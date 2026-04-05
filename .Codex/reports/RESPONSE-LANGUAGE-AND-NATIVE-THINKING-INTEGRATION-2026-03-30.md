# Response Language + Native Thinking Integration

Date: 2026-03-30

## Goal

Apply the agreed flow into the main system:

- add `response_language` into the real request/session/prompt flow
- default to `vi`
- keep follow-up turns in the same session language unless user/host clearly switches
- treat short beats like `oke`, `hehe`, `hẹ hẹ` as Vietnamese by default
- stop using tutor authored `public render thinking` as the live authority
- let native model thought become the main tutor thinking source, with only light sanitization

## Code Changes

### Response language flow

- `app/prompts/prompt_context_utils.py`
  - added `build_response_language_instruction(...)`
  - added detection/resolution helpers for `vi` / `en`
- `app/services/input_processor.py`
  - `ChatContext.response_language`
- `app/services/input_processor_context_runtime.py`
  - initial context default for `response_language`
- `app/services/session_manager.py`
  - `SessionState.response_language`
  - `update_response_language(...)`
- `app/services/chat_orchestrator_runtime.py`
  - resolves turn language from:
    1. explicit user request
    2. message language
    3. session language
    4. host language
    5. user language
    6. fallback `vi`
- `app/services/chat_orchestrator_multi_agent.py`
  - injects `response_language` into graph context

### Prompt injection

- `app/prompts/prompt_loader.py`
  - `build_system_prompt(..., response_language=...)`
  - injects a turn-level language contract into the core prompt
- `app/prompts/prompt_section_builders.py`
  - changed static identity fallback from hard `always Vietnamese` to `default Vietnamese`
- `app/engine/multi_agent/direct_prompts.py`
  - direct chatter / analytical prompts now receive turn language
  - direct agent PromptLoader call now forwards `response_language`
- `app/engine/multi_agent/agents/tutor_surface.py`
  - tutor PromptLoader call now forwards `response_language`
- `app/engine/agentic_rag/answer_generator.py`
  - forwards `response_language` into PromptLoader
- `app/engine/agentic_rag/rag_agent.py`
  - pass-through plumbing for `response_language`
- `app/engine/multi_agent/agents/memory_agent.py`
  - memory answer prompt now respects turn language contract

### Native-thinking-first tutor path

- `app/engine/multi_agent/agents/tutor_surface.py`
  - `thinking_start` is now header/meta only
  - removed sync authored tutor-thinking body from live path
- `app/engine/multi_agent/agents/tutor_node.py`
  - removed handcrafted sync tutor-thinking fallback from final authority chain
  - final tutor thinking now prefers:
    1. native streamed tutor fragments
    2. sanitized raw RAG native thought
    3. sanitized raw tutor native thought
- `app/engine/reasoning/public_thinking_renderer.py`
  - tutor thinking sanitizer is now lighter:
    - keeps model-owned process prose
    - dedupes near-repeat paragraphs
    - strips decorative aside noise
    - drops private/meta markers like `system prompt`, `tool_call`, `routing_metadata`
    - no longer requires old renderer-style phrasing

## Verification

### Focused tests

Command:

```powershell
python -m pytest \
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_response_language_policy.py \
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py \
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py \
  -q -p no:capture --tb=short
```

Result:

- `57 passed`

### Internal prompt/path probes

#### Probe A: tutor native prompt path with `response_language=vi`

Prompt:

- `Giải thích Quy tắc 15 COLREGs`

Observed:

- prompt contains `response_language=vi`
- answer comes out in Vietnamese
- native thinking still came out in English

This means:

- flow plumbing is working
- answer language obeys the new contract
- Gemini native thought still does not reliably obey the language contract

#### Probe B: tutor follow-up prompt path

Prompt:

- `tạo visual cho mình xem được chứ?`

Observed:

- prompt still contains `response_language=vi`
- answer stays in Vietnamese
- native thinking still trends English in this internal prompt-only probe

### Internal tutor tool-loop probe

When probing `_react_loop(...)` directly with local env on 2026-03-30, tutor exposed another bug:

- tool path sometimes collapsed into a placeholder-like answer:
  - `Initiating Placeholder Generation...`

This appears separate from the response-language work and was observed alongside local DB/driver issues:

- `sqlalchemy.dialects:postgresql.psycopg` plugin missing in this probe environment

## Current Truth

What is fixed:

- `response_language` is now a first-class part of the real flow
- default `vi`
- ambiguous follow-up keeps session language
- prompt injection is centralized and clean, not ad-hoc
- tutor no longer invents renderer-authored public thinking on the live path
- tutor sync/stream authority now prefers native model thought

What is still not solved:

- Gemini native thought can still surface in English even when the turn is resolved to Vietnamese
- internal tutor tool-loop still has a separate placeholder/tool behavior bug under this local probe setup

## Recommended Next Step

If the target is:

- `answer` language follows session/user language
- `visible thinking` also follows session/user language
- but we do **not** go back to old handcrafted renderer prose

then the next correct step is:

1. keep native thought as source
2. add a very thin `public-thought language adaptation` layer only when native thought language mismatches the resolved turn language
3. keep it transformation-light:
   - no authored rewrite
   - no fake beats
   - just language alignment + sanitation + dedupe

That would preserve the new architecture while fixing the remaining mismatch the current probes revealed.
