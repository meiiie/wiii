# Thinking Tutor Parity Fix - 2026-03-30

## Goal

Fix the tutor-lane parity bug where:

- `/api/v1/chat/stream/v3` showed rich public thinking
- `/api/v1/chat` often returned empty `thinking_content`

for the same tutoring turn.

## Root Cause

`TutorAgentNode._react_loop()` had two different thinking sources:

1. **Stream path**
   - emitted `thinking_start` / `thinking_delta` from `_iteration_beat.summary`
   - emitted more public thinking through `tool_acknowledgment` and `tool_report_progress`

2. **Sync/final state path**
   - only relied on `llm_thinking` and `rag_thinking`
   - ignored the public fragments already produced during tool-phase reasoning

This meant tutor turns with active tool-flow could look thoughtful on stream while ending with empty sync `thinking_content`.

## Patch

Changed [tutor_node.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py):

- added a local `public_tutor_fragments` collector inside `_react_loop()`
- changed `_push_public_tutor_thinking(...)` to:
  - sanitize + dedupe visible tutor fragments
  - keep those fragments locally even when there is no event bus
  - still stream the same fragments when an event bus exists
- made final `combined_thinking` prefer these collected public fragments before falling back to `rag_thinking` / `llm_thinking`

## Tests

Updated [test_tutor_agent_node.py](E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py):

- added a contract test proving sync tool-flow now returns non-empty `thinking`
- updated the no-tool streaming test to reflect the new source-of-truth contract

Result:

- `25 passed`

## Live Verification

Artifacts:

- [thinking-tutor-parity-fix-sync-2026-03-30-050548.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-parity-fix-sync-2026-03-30-050548.json)
- [thinking-tutor-parity-fix-stream-2026-03-30-050548.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-parity-fix-stream-2026-03-30-050548.json)

### Before

`Giải thích Rule 15 là gì và chỗ nào dễ nhầm với Rule 13?`

- stream had many `thinking_start` / `thinking_delta`
- sync `thinking_content` could be empty

### After

The same tutor turn now returns non-empty sync `thinking_content`.

Sync example:

- `Người dùng đang bối rối giữa hai tình huống cơ động phổ biến nhất trên biển...`

Stream metadata also continues to carry tutor public thinking.

## Status

Closed:

- tutor sync/stream public-thinking parity bug

Still open in the broader thinking backlog:

- direct emotional lane duplicates the same thinking block on stream
- tutor answer tone is still more companion-heavy than ideal
- simple social turns still use the old generic scaffold
