# Thinking Tutor Post-Tool Contract - 2026-03-30

## Goal

Close the remaining tutor-thinking gap where:

- stream could show richer post-tool reasoning,
- but sync `metadata.thinking_content` could still collapse back to a generic retrieve sentence,
- especially on the placeholder-salvage path after `tool_knowledge_search`.

User direction for this round:

- answer is already good enough,
- keep Wiii's soul and a little cute warmth,
- focus on `thinking`,
- finish the `post-tool final generation contract`.

## Root Cause

Tutor had two different fallback sources for public thinking:

1. `public_tutor_fragments`
   - built from `_tool_acknowledgment(...)`
   - can carry the post-tool, source-aware reasoning beats

2. `build_sync_tutor_public_thinking(...)`
   - built from `iteration/tools_used`
   - can only produce a generic phase-level thought

When sync went through the placeholder-salvage path:

- `llm_thinking` was absent,
- `public_tutor_fragments` could be empty if act-phase acknowledgment did not survive sanitization,
- sync therefore fell back to the generic retrieve thought.

That was why sync metadata could still say only:

> Gio minh can goi ra dung ranh gioi giua Rule 13 va Rule 15 tu nguon...

while stream had already become richer in some runs.

## Changes

### 1. Made tutor act-phase contract robust to sparse/raw tool text

File:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py`

Changes:

- `render_tutor_public_plan(..., phase="act", ...)` no longer depends only on raw `tool_result` containing exact markers.
- For `tool_knowledge_search` / `tool_maritime_search`, the act-phase now upgrades to the strong comparison plan when either:
  - tool result contains both `Rule 13` and `Rule 15`, or
  - query itself clearly carries the comparison, or
  - the turn is already classified as comparative.
- Generic act fallback now includes real reasoning markers (`Mình cần`, `Khoan đã`, `điểm tựa`, `mốc`) so it can survive public-thinking sanitization instead of vanishing.

### 2. Let sync explicitly reuse the act-phase contract

File:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_surface.py`

Changes:

- `build_sync_tutor_public_thinking(...)` now accepts:
  - `phase_override`
  - `tool_name`
  - `tool_result`

This allows sync finalization to ask for the same post-tool act-phase reasoning contract, instead of only inferring a generic phase from iteration/tool count.

### 3. Prefer post-tool sync thinking before generic fallback

File:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`

Changes:

- when `tools_used` exists but `public_tutor_fragments` is empty,
- sync now builds a dedicated `post_tool_sync_thinking` from the act-phase contract,
- and uses that before falling back to the generic `build_sync_tutor_public_thinking(...)`.

This is the key change that fixes the placeholder-salvage path.

## Tests

Focused suite:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`

Result:

- `47 passed`

New coverage added:

- act-phase tutor plan can fall back to query signal even when tool text is not richly parseable
- placeholder-salvage path must still produce post-tool tutor thinking instead of generic retrieve-only thinking

## Live Verification

Artifacts:

- sync: `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-sync-2026-03-30-r15.json`
- stream raw json: `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-stream-2026-03-30-r15.json`
- stream raw txt: `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-stream-2026-03-30-r15.txt`

Prompt:

- `Giải thích Rule 15 khác gì Rule 13 trong COLREGs`

### Current truth

Sync metadata thinking now contains the richer post-tool chain:

1. retrieve anchor
2. source-aware act reasoning
3. self-correction beat
4. living/Wiii warmth cue

Example:

> Gio minh can goi ra dung ranh gioi giua Rule 13 va Rule 15 tu nguon...
>
> Moc chac nhat tu nguon dang nam o vi tri tiep can va quy tac uu tien giua hai tau...
>
> Khoan da, neu tron luon ngoai le...

Stream metadata now matches the same final thinking body, and stream `thinking_delta` emits the richer post-tool continuation rather than only the old generic retrieve sentence.

## Outcome

This round completes the main tutor `post-tool final generation contract` for thinking:

- sync no longer collapses back to retrieve-only thinking on the salvage path
- stream and sync now share the same stronger tutor post-tool reasoning truth
- Wiii keeps a warm living cue, but the rail stays inward and strategic instead of turning into an opener or answer draft

## Remaining Debt

This round intentionally did **not** optimize answer style further.

Remaining optional improvements, if we keep pushing tutor quality:

1. trim decorative flourish in long learning answers while keeping Wiii warm
2. reduce markdown-table bias in tutor answers when the user did not ask for a structured table
3. make the living cue paragraph shorter so the rail feels more internal and less narrated
