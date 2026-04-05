# Direct Effort Taxonomy Step - 2026-03-31

## Why this step

Direct lane was mixing two different concepts:

- provider/model tier: `light | moderate | deep`
- per-turn reasoning effort: `low | medium | high | max`

Inside `direct_node_runtime.py`, short chatter and identity turns were still assigning:

- `thinking_effort = "light"`
- `thinking_effort = "moderate"`

But `AgentState.thinking_effort` is canonically documented as:

- `low | medium | high | max`

And `llm_pool._effort_to_tier()` only maps those canonical values. So those legacy direct values silently fell back to the agent default tier instead of expressing the intended reasoning floor.

## External research used

Official docs checked on 2026-03-31:

- Anthropic extended thinking: native model reasoning should stay model-authored, with light orchestration rather than post-hoc authored chains.
- Google Gemini thinking docs: Gemini 3 uses `thinkingLevel` (`minimal | low | medium | high`), while Gemini 2.5 uses `thinkingBudget`. This is a turn-level reasoning control, separate from model identity.
- OpenAI GPT-5.4 guide: `reasoning.effort` is a request-level control, separate from model choice.
- Z.AI / GLM deep thinking docs: `thinking.type` (`enabled` / `disabled`) is again a runtime reasoning control, separate from model choice.

Design conclusion:

- Wiii should keep one internal canonical reasoning-effort contract.
- Provider/tier mapping should stay separate and provider-specific.
- Direct lane should normalize to the canonical effort contract before asking the pool for an LLM.

## Code changes

### 1. Canonicalized direct effort values

Updated:

- `maritime-ai-service/app/engine/multi_agent/direct_node_runtime.py`

Added:

- `_canonicalize_direct_thinking_effort()`
- `_resolve_direct_thinking_effort()`

Behavior now:

- legacy `light` -> `low`
- legacy `moderate` -> `medium`
- legacy `deep` -> `high`

### 2. Added stronger reasoning floor for hard direct turns

If direct turn is:

- short house chatter -> `low`
- identity/selfhood -> `medium`
- identity origin / creation / birth queries -> `high`
- analytical direct turns (`analytical_market`, `analytical_math`, `analytical_general`) -> `high`

This keeps the internal effort taxonomy clean while still letting the pool/provider map that effort to the best available runtime tier.

## Tests

Added:

- `maritime-ai-service/tests/unit/test_direct_reasoning_effort.py`

Focused tests passing:

- `test_direct_reasoning_effort.py`
- `test_direct_prompts_identity_contract.py`
- `test_direct_prompts_analytical_contract.py`
- `test_direct_reasoning_modes.py`
- `test_direct_identity_answer_policy.py`

Result:

- 23 passing focused tests after the patch

## Live probe results

Probe:

- `.Codex/reports/live-origin-math-probe-2026-03-31-195031.json`

### Wiii origin

- sync answer: good Wiii voice
- stream answer: good Wiii voice
- visible thinking block: still empty in this run

Interpretation:

- selfhood/origin is currently expressing thought mainly by weaving it into the answer, not by surfacing a separate visible thinking block

### Hard math

- stream visible thinking: present and on-topic
- no fallback drift into unrelated template content
- answer remained strong and domain-correct

Interpretation:

- the heavier reasoning floor is helping where it matters most: hard analytical direct turns

## Current truth

This step improved the architecture and the hard-task behavior, but did not fully solve direct visible thinking for selfhood turns.

What is now true:

- direct no longer mixes tier labels into `thinking_effort`
- hard analytical turns get a stronger, canonical reasoning floor
- provider diversity is preserved because the internal effort contract stays provider-agnostic
- selfhood turns on `direct_chatter_agent` now receive `living_context_prompt` as well, so identity/origin prompts no longer lose the living bridge purely because they route through the chatter-style shell

What is still true:

- selfhood/origin direct turns often surface their "thinking" by blending it into the answer instead of emitting a separate visible thought block
- that part likely needs a separate decision about whether selfhood should stay on the chatter-style prompt path or move onto a stronger selfhood-specific direct runtime path
- on Google specifically, higher effort currently increases the reasoning budget but does not automatically switch to a deeper Gemini model. `GeminiProvider` still defaults to `settings.google_model` across tiers unless a model override is provided. So `high` effort is not yet equivalent to "deep model" the way it more closely is for OpenAI/Zhipu.
