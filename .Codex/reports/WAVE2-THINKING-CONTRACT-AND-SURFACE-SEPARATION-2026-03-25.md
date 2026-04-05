# Wave 2: Thinking Contract And Surface Separation

Date: 2026-03-25  
Workspace: `E:\Sach\Sua\AI_v1`

## Why this wave exists

The failure mode was not mainly latency. The deeper issue was that Wiii's visible thinking had started to feel like a planner/debug console instead of a living companion:

- raw user phrasing leaked into visible reasoning
- routing/planner jargon such as `lane` and `tool_*` surfaced in user-facing text
- supervisor opening beat, heartbeat, and completion line sounded like different speakers
- visual and code lanes risked leaking operational traces into the main chat surface

This wave focused on restoring a clean contract:

1. `living_thought` should sound like Wiii
2. `status/action/debug` should not masquerade as inner life
3. raw code must not spill into the answer rail
4. visual prompts should stay visually-oriented

## Research alignment

The direction matches the strongest public patterns available as of 2026-03-25:

- Anthropic separates stream events semantically instead of dumping one mixed reasoning blob:
  - [Claude streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)
  - [Claude fine-grained tool streaming](https://platform.claude.com/docs/en/agents-and-tools/tool-use/fine-grained-tool-streaming)
- OpenAI's background/stream patterns also treat operational progress as typed events, not user-facing prose:
  - [OpenAI background mode](https://developers.openai.com/api/docs/guides/background)
- AIRI's companion direction supports presence and continuity, but not leaking planner logs into the main persona surface:
  - [Project AIRI README](https://github.com/moeru-ai/airi)

The takeaway is simple: "alive" does not mean "show internal logs." It means the visible surface feels continuous, intentional, and human-legible.

## Changes implemented

### 1. Supervisor opening beat is now house-owned

File:
- `maritime-ai-service/app/engine/multi_agent/supervisor.py`

Changes:
- added `_pick_house_line(...)`
- added `_build_supervisor_opening_line(...)`
- stopped opening the supervisor thinking rail with the old narrator-generated route prelude
- opening thought is now a short, Wiii-owned line that:
  - does not echo the raw query
  - does not say `lane`, `route`, `tool_*`
  - keeps the same voice family as the heartbeat

### 2. Supervisor heartbeat wording is shorter and less robotic

File:
- `maritime-ai-service/app/engine/multi_agent/supervisor.py`

Changes:
- rewrote `_build_supervisor_heartbeat_text(...)`
- removed explicit planner jargon from user-facing heartbeat text
- removed raw-query mirroring from heartbeat variants
- split heartbeat wording by high-level shape:
  - social / reaction / vague short turns
  - search / explanation turns
  - chart-runtime visual turns
  - code-studio / simulation turns

### 3. Supervisor completion line no longer replays the user's exact phrasing

File:
- `maritime-ai-service/app/engine/multi_agent/supervisor.py`

Changes:
- rewrote `_build_supervisor_completion_line(...)`
- kept it meaningful, but generic enough to avoid prompt-log feel
- removed direct dependency on quoting the user's exact query for visual/code turns

### 4. Code Studio no longer dumps raw code into the main answer rail

Files:
- `maritime-ai-service/app/engine/multi_agent/graph.py`
- `maritime-ai-service/tests/unit/test_graph_routing.py`
- `maritime-ai-service/tests/unit/test_sprint154_tech_debt.py`

Changes:
- suppressed raw code spill into `answer_delta` for `code_studio_agent`
- collapsed post-tool code dumps into short delivery prose
- kept code in the code/visual surface instead of the main conversational answer

## Tests and verification

Targeted tests passing:

- `test_supervisor_agent.py::TestSupervisorVisibleReasoningContract`
- `test_supervisor_agent.py::TestSupervisorProcess::test_process_streams_visible_supervisor_reasoning`
- `test_graph_routing.py::TestCodeStudioProgressHeartbeat::test_stream_answer_suppresses_raw_code_dump_for_code_studio_lane`
- `test_sprint154_tech_debt.py::TestCodeStudioWave002::test_sanitize_code_studio_response_collapses_visual_code_dump_without_session_context`
- `test_sprint154_tech_debt.py::TestExecuteDirectToolRounds::test_visual_intent_keeps_forcing_followup_until_visual_tool_emits`
- `test_supervisor_routing_reasoning.py::test_supervisor_completion_line_uses_generic_goal_reference_for_visual_request`

Result:
- `7 passed`

Additional checks:
- `py_compile` passed for touched backend files
- local web UI reachable at `http://localhost:1420`
- backend health reachable at `http://localhost:8000/health`

## What improved

For prompts like:

- `Visual cho mình xem thống kê dữ liệu hiện tại giá dầu mấy ngày gần đây`
- `mô phỏng cảnh Thúy Kiều ở lầu Ngưng Bích cho mình được chứ ?`

the intended improvement is:

- no raw replay of the user query in the visible supervisor opening beat
- no user-facing `lane/tool/route` wording in opening beat or heartbeat
- no raw code dump in the main chat answer when Code Studio is active

## What is still not fully done

Wave 2 is materially better, but not finished forever.

Remaining debt:

- some downstream node-specific phrases can still feel more operational than soulful
- visual/chart turns still need stricter end-to-end intent preservation so they always conclude as visual-or-clarify, not "search-only"
- frontend inspector vs main rail separation can still be tightened further for debug/tool evidence

## Recommended next wave

Wave 3 should focus on:

1. sticky `visual_intent` through completion
2. one active visual session per turn
3. stricter separation of:
   - living thought
   - action preamble
   - evidence/debug/tool trace
4. house-voice parity across:
   - supervisor
   - direct/chat lane
   - code-studio delivery
