# Thinking Step 2: Opening + Sync Authority

Date: 2026-03-30

## Goal
- Reduce forced, fake-feeling tutor thinking.
- Pull the opening toward user/question need instead of stock rhetorical pivots.
- Stop raw `llm_thinking` from overriding curated tutor thinking in sync metadata.

## Changes
- Softened tutor draft prompt in [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py):
  - removed explicit encouragement of `Khoan da`
  - pushed beat 1 toward `nguoi dung/cau hoi dang can gi`
  - added stronger anti-motif guidance for repetitive interjections
- Added context-anchor scoring and repair pressure in the same draft service.
- Fixed a subtle draft bug:
  - first beat could be dropped if it looked too similar to `header_summary`
  - now beat-first authority is preserved and summary is demoted when duplicate
- Updated tutor sync authority in [tutor_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py):
  - priority now is:
    1. streamed tutor fragments
    2. curated sync tutor thinking
    3. sanitized raw RAG/LLM thinking only as fallback

## Verify
- [test_public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_public_thinking_draft_service.py): `7 passed`
- [test_public_thinking_renderer.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_public_thinking_renderer.py) + [test_tutor_agent_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_tutor_agent_node.py): `55 passed`

## Live Probe
Artifact:
- [thinking-step3b-sync-2026-03-30.json](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-step3b-sync-2026-03-30.json)

Prompt:
- `Giải thích Quy tắc 15 COLREGs`

Current tutor `thinking_content` now opens like:

> Nút thắt nằm ở việc xác định ai là người phải nhường đường...

and later includes:

> Người dùng đang hỏi về Quy tắc 15, nhưng mình cảm nhận được họ không muốn một bản dịch luật...

This is materially better than the old `Khoan da...` openings and better aligned with a living, user-aware tutor mind.

## Remaining Issues
- The `visual follow-up` prompt `tạo visual cho mình xem được chứ?` still lands in `direct` due domain-validation override, even when `llm_reasoning` prefers tutor.
- Tutor thinking is improved, but beat 1 still sometimes opens from a conceptual bottleneck (`Nút thắt...`) rather than directly from the user's intent (`Người dùng đang muốn...`).

## Recommended Next Step
- Fix `visual follow-up` continuity in supervisor/domain validation.
- Then keep tuning tutor beat 1 toward:
  - user-need first
  - confusion/tension second
  - strategy after that
