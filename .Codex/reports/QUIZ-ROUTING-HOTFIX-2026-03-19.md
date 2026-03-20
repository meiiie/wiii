# Quiz Routing Hotfix — 2026-03-19

## User-reported symptom
- Query: `tạo cho mình quizz gồm 30 câu hỏi về tiếng Trung để mình luyện tập được không ?`
- Observed:
  - reasoning rail duplicated generic text
  - routing action showed `code_studio_agent`
  - then Code Studio stalled and later hit hard timeout

## Log evidence
- Source: `.Codex/reports/local-runs/phase11-local-backend-r2.out.log`
- Relevant lines:
  - request accepted around line 2596
  - supervisor routed to `code_studio_agent` at line 2620
  - Code Studio selected `tool_create_visual_code`
  - later `[CODE_STUDIO] ainvoke hard timeout after 240s`

## Root cause
- `visual_intent_resolver.py` still treated generic `quiz` as an app-generation cue.
- That made `resolve_visual_intent()` classify a plain text quiz request as `code_studio_app`.
- Conservative fast routing then short-circuited to `code_studio_agent`.

## Fix
- Removed plain `quiz` from generic app-request cues.
- Introduced `_QUIZ_WIDGET_CUES` so only explicit quiz widget/app requests still route to Code Studio.
- Added conservative fast-path for obvious learning turns without app/domain signals:
  - generic quiz
  - practice
  - flashcards
  - study/explanation style requests
- Result:
  - plain text quiz requests now route to `direct` with `intent=learning`
  - explicit interactive quiz widget/app requests still route to Code Studio or artifact lanes

## Verification
- `test_visual_intent_resolver.py` + `test_conservative_evolution.py` -> `33 passed`
- direct route sanity check:
  - query: `tạo cho mình quizz gồm 30 câu hỏi về tiếng Trung để mình luyện tập được không ?`
  - result: `direct`
  - routing metadata: `intent=learning`, `method=conservative_fast_path`

## Follow-up note
- The duplicated reasoning sentence appears separate from the routing bug and likely comes from repeated fallback narration / duplicated thinking display.
- That should be handled as a dedicated UI-streaming cleanup slice after this routing hotfix.
