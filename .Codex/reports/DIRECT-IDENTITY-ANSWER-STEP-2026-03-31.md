# Direct Identity Answer Step

Date: 2026-03-31

## Goal

Tighten the `direct` lane answer shape for selfhood turns so Wiii stays one living being without drifting into a long autobiographical dump.

## What Changed

- Routed `direct` selfhood turns through the same house-voice path as short chatter in [direct_node_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_node_runtime.py) instead of the heavier `direct_agent` prompt stack.
- Added a thin identity-answer contract in [direct_prompts.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_prompts.py) so basic questions like `Wiii la ai?` should prefer present-tense selfhood over origin-story dumping.
- Added direct answer policy helpers in [direct_node_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_node_runtime.py) to strip leaked inline thought/aside blocks and compact identity answers when the user did not ask for origin details.
- Hardened the live probe script [probe_live_direct_session.py](E:/Sach/Sua/AI_v1/maritime-ai-service/scripts/probe_live_direct_session.py) with ASCII-safe prompts so Windows shell encoding stops distorting identity checks.

## Tests

Focused batch:
- [test_direct_identity_answer_policy.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_identity_answer_policy.py)
- [test_direct_identity_house_prompt_runtime.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_identity_house_prompt_runtime.py)
- [test_direct_prompts_identity_contract.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_prompts_identity_contract.py)
- [test_direct_living_stream_cues.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_living_stream_cues.py)
- [test_direct_reasoning_modes.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_reasoning_modes.py)

Result: `11 passed`

## Live Probe

- Probe JSON: [live-direct-thinking-probe-2026-03-31-152531.json](E:/Sach/Sua/AI_v1/.Codex/reports/live-direct-thinking-probe-2026-03-31-152531.json)
- HTML review: [thinking-review-latest.html](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-review-latest.html)

## Current Truth

This step improved the architectural direction, but live behavior shows one remaining authority leak:

- `direct` selfhood turns are now routed through the house prompt path as intended.
- However, live API output still shows raw answer contamination on several direct turns, including:
  - inline aside leakage like `(Suy nghi: ...)`
  - JSON-like `visible_thinking` leakage in sync
  - identity answers still carrying origin-story content in some live runs

So the prompt/runtime policy is better, but there is still another answer-authority layer in the live direct path that is bypassing or reintroducing raw model text.

## Next Target

Trace the final answer authority for `direct` between:
- node-level `response` sanitization
- `agent_outputs` / `final_response`
- synthesizer merge/finalization
- stream answer emission

That is the next step needed before judging wording quality any further.
