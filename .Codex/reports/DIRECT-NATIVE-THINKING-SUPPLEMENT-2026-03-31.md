# Direct Native Thinking Supplement Step

Date: 2026-03-31

## What changed
- Added a direct-only visible thinking supplement in `app/engine/multi_agent/direct_prompts.py`.
- Applied it to both `direct_agent` and `direct_chatter_agent` without touching `_shared.yaml`.
- Added few-shot examples for selfhood, hard math, market analysis, and emotional/social turns.
- Kept the contract thin: no prompt/system/YAML leakage, no answer-draft, no editorial planner voice.

## Tests
- `tests/unit/test_direct_prompts_identity_contract.py`
- `tests/unit/test_direct_prompts_analytical_contract.py`
- Focused direct/thinking suite remained green (`55 passed`).

## Live probe truth
Probe file: `live-origin-math-probe-2026-03-31-192142.json`

- `sync_wiii_origin`: visible thinking reappeared and is strongly Wiii-coded (The Wiii Lab, Bông, living selfhood), but it is still too answer-like and theatrical.
- `stream_wiii_origin`: still empty on this run.
- `stream_hard_math`: visible thinking remained present and domain-correct, no pendulum drift.

## Interpretation
- The direct prompt supplement is working: native thought can now reappear on direct turns without reviving old templates.
- The result is still unstable across runs, especially on identity/social turns.
- This now looks less like a template problem and more like a stability / reasoning-floor problem for short selfhood turns.

## Important discovery (not patched yet)
- `direct_node_runtime.py` still sets `thinking_effort = "light"` and `"moderate"` for short chatter / identity turns.
- Elsewhere, direct state schemas and visual merge helpers expect `low|medium|high|max`.
- This cross-system naming mismatch may be weakening or bypassing the intended reasoning floor, but it needs a careful pass before changing because the provider layer also uses `light|moderate|deep` in some places.
