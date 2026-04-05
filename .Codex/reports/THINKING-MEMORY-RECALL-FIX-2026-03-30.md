# Thinking Memory Recall Fix - 2026-03-30

## Goal

Fix the centralized public-thinking bug where memory recall prompts such as `Mình tên gì nhỉ?` were misclassified as fresh name introductions, causing gray-rail output like:

- `gì vừa chủ động xưng tên...`
- `dùng gì như một điểm neo...`

## Root Cause

The central renderer in `app/engine/reasoning/public_thinking_renderer.py` treated any `mình tên ...` shape as a name introduction.

Two failures combined:

1. `extract_declared_name(...)` could capture interrogative tokens such as `gì` as if they were a declared name.
2. `looks_like_name_introduction(...)` had only a positive introduction heuristic and no explicit `recall` branch.

## Patch

### Central classifier

Added `classify_memory_name_turn(query)` with three explicit outcomes:

- `introduction`
- `recall`
- `other`

### Interrogative guard

`extract_declared_name(...)` now rejects normalized interrogative tokens such as:

- `gi`
- `nao`
- `sao`
- `ai`
- `chi`

### Renderer branching

`render_memory_public_plan(...)` now branches recall turns separately across:

- `retrieve`
- `existing`
- `extract`
- `new_fact`
- `synthesize`

Recall turns now produce memory-check reasoning instead of introduction reasoning.

## Files Changed

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\__init__.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`

## Verification

### Focused tests

- `test_public_thinking_renderer.py`
- `test_memory_agent_node.py`

Result:

- `21 passed`

### Live UTF-8 probe artifacts

- [thinking-memory-recall-fix-sync-2026-03-30-045812.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-memory-recall-fix-sync-2026-03-30-045812.json)
- [thinking-memory-recall-fix-stream-2026-03-30-045812.json](E:\Sach\Sua\AI_v1\.Codex\reports\thinking-memory-recall-fix-stream-2026-03-30-045812.json)

## Before

Recall prompts could produce public thinking shaped like:

- `gì vừa chủ động xưng tên...`
- `dùng gì như một điểm neo xưng hô...`

## After

Sync `thinking_content` for `Mình tên gì nhỉ?` now resolves to the correct recall-style reasoning:

1. `Trong memory đã có một điểm neo định danh đủ rõ để dựa vào...`
2. `Lượt này không đưa thêm dữ kiện mới; nó chỉ kiểm tra xem tên đã lưu còn được giữ đúng...`
3. `Khoan đã, mình không cần làm quá lên như vừa khám phá ra điều gì lớn...`

Stream headers now start with:

- `Rà soát điểm neo định danh`
- `Chọn cách gọi lại cho tự nhiên`

and no longer mention `xưng tên`.

## Status

Closed:

- memory recall misclassification

Still open from the broader probe suite:

- tutor sync/stream thinking parity
- emotional direct-lane duplicate thinking block
- simple social turns still using the old generic scaffold
