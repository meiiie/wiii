# Wiii Golden Eval Checkpoint

Date: 2026-04-01
Owner: Codex LEADER

## Goal

Build a stable golden-eval harness for Wiii so future prompt/runtime changes can be judged against the same living baseline instead of ad-hoc spot checks.

This checkpoint follows the same high-level pattern used by major labs in 2026:
- fixed eval tasks instead of one-off demos
- transport-aware scoring instead of only final-answer scoring
- regression artifacts that humans can inspect quickly
- multi-turn continuity checks, not just single-prompt grading

Reference direction:
- Anthropic: prompt/test iteration and model-written eval discipline
- Google Gemini: thinking-aware evaluation should look at process traces, not only final answer
- OpenAI: evals should be repeatable, scoped, and tied to concrete pass/fail criteria

## Deliverables

- Golden eval manifest:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\data\wiii_golden_eval_manifest.json`
- Golden eval runner:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_wiii_golden_eval.py`
- Regression HTML renderer:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\render_thinking_probe_html.py`
- Harness tests:
  - `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_wiii_golden_eval_scripts.py`

## Manifest Shape

Profiles:
- `core`: fast regression for soul, thinking, continuity, and answer authority
- `extended`: deeper regression for search, product search, code studio, and lookup-grounded flows

Current session coverage:
- `tutor_rule15_visual`
- `direct_origin_bong`
- `memory_name_roundtrip`
- `emotion_direct`
- `hard_math_direct`
- `search_current_events`
- `product_search_audio`
- `code_studio_rule15_sim`
- `lookup_grounded_rule15`
- `casual_followup_micro`

Coverage tags used today:
- `tutor`
- `visual`
- `continuity`
- `teaching`
- `direct`
- `selfhood`
- `living`
- `memory`
- `relationship`
- `name-recall`
- `emotional`
- `warmth`
- `deep-thinking`
- `analytical`
- `search`
- `tools`
- `current-events`
- `product_search`
- `comparison`
- `code_studio`
- `artifact`
- `interactive`
- `lookup`
- `grounded`
- `micro-social`

## Evaluation Contract

Per turn, per transport (`sync` and `stream`), the harness currently checks:
- answer exists
- visible thinking exists when required
- tool trace exists when required
- duplicate stream answer tail does not occur
- routed agent is in an allowed set
- answer language and thinking language are recorded for review

Important design choice:
- the runner canonicalizes agent aliases such as `tutor_agent -> tutor` and `memory_agent -> memory`
- this avoids false negatives from naming differences that do not matter to product quality

## Artifacts

Latest core regression JSON:
- `E:\Sach\Sua\AI_v1\.Codex\reports\wiii-golden-eval-2026-04-01-012125.json`

Latest review HTML:
- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest.html`

## Current Core Run

After recalibrating alias handling and expectation shape:

- session count: `5`
- turn count: `8`
- transport count: `16`
- passed transports: `14`
- failed transports: `2`
- stream duplicate-answer count: `0`
- stream visible-thinking turns: `7`
- stream tool-trace turns: `2`

## Real Failures Remaining

Only 2 failures remain in the current `core` run:

1. `tutor_rule15_visual :: rule15_explain :: sync`
   - failure: `missing_visible_thinking`
   - meaning: sync tutor answer is present, but sync metadata still does not surface visible thought for this turn

2. `hard_math_direct :: hilbert_operator :: stream`
   - failure: `missing_visible_thinking`
   - meaning: direct stream answer is good, but stream thought is still unstable for this deep analytical turn

These are useful failures, not harness noise.

## What This Harness Protects Now

Already protected:
- no duplicate stream-answer tail in current `core` run
- visible stream thinking in most important lanes
- origin/selfhood continuity for Wiii and Bông
- name memory roundtrip
- emotional direct turns no longer depend on obvious old templates
- tutor follow-up visual continuity

Not fully protected yet:
- sync visible-thinking parity
- deep analytical stream thought stability
- broad coverage for RAG/product/code/search in a live run

## Recommended Next Wave

Phase 1:
- keep `core` as the daily baseline
- fix the 2 remaining real failures above

Phase 2:
- run `extended` profile live and publish a second checkpoint
- confirm product search, code studio, lookup-grounded, and current-events flows

Phase 3:
- add richer semantic checks for Wiii-specific quality:
  - The Wiii Lab / Bông selfhood continuity
  - anti-template emotional turns
  - stream thought language alignment
  - tool trace visibility quality

Phase 4:
- optionally add rubric-style grading for:
  - soul consistency
  - pedagogy quality
  - research transparency
  - answer authority parity between sync and stream

## Notes

This harness is intentionally not a leaderboard benchmark. It is a product-regression harness for Wiii.

The main value is:
- stable prompts
- stable flows
- inspectable artifacts
- faster iteration without losing Wiii's living identity
