# Thinking Round B - 2026-03-30

## Scope

This round focused on three concrete thinking issues after the earlier authority cleanup:

1. memory recall misclassification
2. tutor sync/stream parity
3. direct emotional duplicate thinking + stale simple-social scaffold

## 1. Memory recall misclassification

Fixed in:

- [public_thinking_renderer.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py)

What changed:

- memory turns are now explicitly classified as `introduction / recall / other`
- interrogatives like `gì` are no longer captured as if they were a declared name
- recall turns now get their own public-thinking plan

Result:

- `Mình tên gì nhỉ?` no longer produces:
  - `gì vừa chủ động xưng tên...`
  - `dùng gì như một điểm neo...`

Artifacts:

- [THINKING-MEMORY-RECALL-FIX-2026-03-30.md](E:\Sach\Sua\AI_v1\.Codex\reports\THINKING-MEMORY-RECALL-FIX-2026-03-30.md)
- [thinking-memory-recall-fix-sync-2026-03-30-045812.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-memory-recall-fix-sync-2026-03-30-045812.json)
- [thinking-memory-recall-fix-stream-2026-03-30-045812.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-memory-recall-fix-stream-2026-03-30-045812.json)

## 2. Tutor sync/stream parity

Fixed in:

- [tutor_node.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py)

What changed:

- tutor tool-phase public thinking is now collected locally inside `_react_loop()`
- final sync `thinking` / `thinking_content` can reuse the same public fragments that stream already surfaced

Result:

- tutor turns with tool-flow no longer have the old split:
  - stream: rich thinking
  - sync: empty `thinking_content`

Artifacts:

- [THINKING-TUTOR-PARITY-FIX-2026-03-30.md](E:\Sach\Sua\AI_v1\.Codex\reports\THINKING-TUTOR-PARITY-FIX-2026-03-30.md)
- [thinking-tutor-parity-fix-sync-2026-03-30-050548.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-parity-fix-sync-2026-03-30-050548.json)
- [thinking-tutor-parity-fix-stream-2026-03-30-050548.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-parity-fix-stream-2026-03-30-050548.json)

## 3. Direct emotional duplicate thinking

Fixed in:

- [direct_public_thinking_runtime.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_public_thinking_runtime.py)
- [direct_opening_runtime.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_opening_runtime.py)
- [direct_tool_rounds_runtime.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\direct_tool_rounds_runtime.py)

What changed:

- direct lane now remembers the last public thinking block emitted during opening
- if synthesis tries to emit the exact same chunk sequence again after tool rounds, it is suppressed

Result:

- emotional prompt `Hôm nay sếp chửi mình té tát, buồn quá`
  no longer streams the same 3-line thinking block twice

Artifact:

- [thinking-emotional-dedupe-stream-2026-03-30-051055.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-emotional-dedupe-stream-2026-03-30-051055.json)

Current truth:

- `thinking_start_count = 1`
- `thinking_delta_count = 3`

## 4. Simple-social scaffold refresh

Changed in:

- [reasoning_narrator_support.py](E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\reasoning_narrator_support.py)

What changed:

- replaced the old generic relational scaffold:
  - `Nhịp này không cần kéo dài quá tay...`
- with a more alive inner voice for short social taps

Result for `hehe`:

- gray rail now reads as a small social rhythm check, not a dead template

Artifact:

- [thinking-social-vibe-sync-2026-03-30-051353.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-social-vibe-sync-2026-03-30-051353.json)

## Verification

Focused tests passed:

- memory/public-thinking batch: `21 passed`
- tutor batch: `25 passed`
- direct-tool-rounds batch: `4 passed`
- reasoning narrator runtime batch: `15 passed`

## What is now closed

- memory recall classifier bug
- tutor sync/stream thinking parity bug
- direct emotional duplicate-thinking bug
- old generic `hehe` scaffold

## What remains open

- tutor answer tone is still too companion-heavy for many teaching turns
- tutor thinking is better synchronized now, but still not yet at the desired “instructional designer” quality bar
- direct emotional answers are still more soothing than strategically self-aware
- RAG lane still needs a higher-grade public-thinking voice, not just leak prevention
