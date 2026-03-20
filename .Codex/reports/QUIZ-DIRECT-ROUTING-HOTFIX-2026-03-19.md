# Quiz Direct Routing Hotfix — 2026-03-19

## Summary
- Plain quiz/study prompts were no longer being routed by the supervisor into `code_studio_agent`, but the `direct` lane still got forced into tool use.
- Root cause was twofold:
  - `_needs_lms_query()` treated generic `quiz`/`kiem tra` language as an LMS data request.
  - `direct` still kept visual codegen tools available for plain quiz practice turns, which let the model drift into `tool_create_visual_code`.

## Changes
- Refined LMS intent detection in [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py):
  - generic `quiz` is no longer enough to trigger LMS tools
  - assessment terms now require LMS context hints like grades/course/progress/deadline
- Added `_should_strip_visual_tools_from_direct()` in [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py):
  - plain quiz/study turns keep `direct`
  - `tool_create_visual_code`, `tool_generate_visual`, `tool_generate_mermaid`, and `tool_generate_interactive_chart` are stripped from the direct tool list unless the user explicitly asks for an app/widget/html/interactive visual

## Verification
- Unit tests:
  - `test_graph_routing.py` -> `35 passed`
  - `test_sprint175_lms_integration.py` -> `70 passed`
  - `test_conservative_evolution.py` -> `7 passed`
- Fresh backend smoke with all local phase flags enabled:
  - prompt: `tạo cho mình quizz gồm 30 câu hỏi về tiếng Trung để mình luyện tập được không ?`
  - result:
    - routed to `direct`
    - `force_tools=false`
    - no `tool_create_visual_code`
    - total processing time dropped from ~118-177s down to ~32s

## Notes
- The frontend fallback `Khong the hien thi noi dung (visual)` had a separate root cause and was already fixed locally in [VisualBlock.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/VisualBlock.tsx).
- Current quiz smoke emits normal `answer` chunks, not `answer_delta`; this matches the current stream contract and is not itself an error.
