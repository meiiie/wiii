# Thinking Step 3: Tutor Live Path Cleanup

Date: 2026-03-30

## Focus
- Fix tutor live path so runtime metadata no longer surfaces stale/raw tutor thinking ahead of curated thinking.
- Push tutor opening closer to `Nguoi dung/Cau hoi nay...` instead of forced pivots like `Khoan da...`.
- Remove decorative aside noise and reduce repeated paragraph blocks.

## Code Changes
- [public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_draft_service.py)
  - stronger beat-1 pressure toward user/question framing
  - beat-first over summary when duplicate
  - explicit opening promotion for tutor drafts
  - Vietnamese accent-safe normalization for `đ`
- [public_thinking_renderer.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/public_thinking_renderer.py)
  - final tutor sanitizer now:
    - strips decorative asides
    - promotes later `Nguoi dung/Nguoi hoc...` paragraphs above generic openings
    - dedupes near-repeat user-facing tutor paragraphs
- [tutor_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py)
  - sync tutor thinking authority now prefers curated tutor thinking
  - final `combined_thinking` passes through tutor sanitizer before return

## Verify
- [test_public_thinking_draft_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_public_thinking_draft_service.py): `9 passed`
- [test_public_thinking_renderer.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_public_thinking_renderer.py): `16 passed`
- [test_tutor_agent_node.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_tutor_agent_node.py): included in focused batch, total `50 passed` with renderer batch

## Live Probe
- Artifact: [thinking-step3h-rule15-sync-2026-03-30.json](E:/Sach/Sua/AI_v1/.Codex/reports/thinking-step3h-rule15-sync-2026-03-30.json)
- Prompt: `Giải thích Quy tắc 15 COLREGs`

Current live `thinking_content` now opens with:

> Người dùng đang hỏi về Quy tắc 15...

instead of older openings like:

> Khoan đã...

or purely generic:

> Nhịp này không cần kéo dài quá tay...

## Current Truth
- Tutor thinking is materially better on the live path.
- The opening now anchors to the user and the learning need.
- `Khoan da` has been pushed out of this probe.
- Decorative kaomoji no longer leaked into this probe.

## Remaining Issue
- The live tutor thinking is still a bit long and can retain one extra paragraph that feels semantically close to an earlier paragraph.
- Visual follow-up continuity is still not fixed yet; `tạo visual cho mình xem được chứ?` remains vulnerable to `direct` after domain validation.

## Next Best Step
- Fix visual follow-up continuity so the same tutor line can keep thinking quality across multi-turn learning threads.
