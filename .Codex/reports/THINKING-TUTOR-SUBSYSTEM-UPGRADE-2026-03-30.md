# Thinking Tutor Subsystem Upgrade — 2026-03-30

## Scope

Round này tập trung vào `tutor lane` ở tầng `public thinking`, không sửa đại trà toàn bộ answer pipeline.

Mục tiêu:

1. Gom `tutor thinking` về renderer trung tâm thay vì để node/tool reflection tự viết prose rải rác.
2. Chặn raw `tool_think` leak ra gray rail.
3. Buộc `thinking_start.summary` giữ vai trò header/meta, còn body đi từ curated fragments.
4. Siết prompt answer của tutor theo hướng instructional hơn.

## Files changed

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\__init__.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_surface.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_tool_dispatch_runtime.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`

## What changed

### 1. Centralized tutor public plan

Thêm `render_tutor_public_plan(...)` trong `public_thinking_renderer.py`.

Plan này hiện định nghĩa các phase chính:

- `attune`
- `retrieve`
- `verify`
- `synthesize/explain`
- `act`

Nó trả về `ThinkingSurfacePlan` với:

- `header_label`
- `header_summary`
- `beats`
- `tone_mode=instructional_companion`

Tức là tutor gray rail không còn phụ thuộc hoàn toàn vào `reasoning_narrator.render(...)` để dựng beat mở đầu.

### 2. Tutor beat now emits fragments, not duplicated summary body

`tutor_surface._iteration_beat(...)` giờ:

- gọi `render_tutor_public_plan(...)`
- trả về `SimpleNamespace(label, summary, phase, fragments, tone_mode)`

`tutor_node._react_loop(...)` và `tutor_tool_dispatch_runtime.py` giờ:

- emit `thinking_start.summary` như header/meta
- chỉ stream `fragments` vào `thinking_delta`
- fallback sang `summary` chỉ khi test/beat cũ không có `fragments`

Hệ quả: header và body của tutor thinking đã bắt đầu tách đúng vai trò.

### 3. Raw tool_think is no longer public

Trong `tutor_tool_dispatch_runtime.py`, branch `tool_think` không còn:

- `await push_thinking_deltas(raw_thought)`

Raw `thought` giờ chỉ được ghi nội bộ vào tool observation/messages.

Điều này chặn một nguồn lớn làm tutor gray rail biến thành mini-answer hoặc prose quá “người”.

### 4. Tool acknowledgment now follows the central plan first

`tutor_surface._tool_acknowledgment(...)` giờ:

- ưu tiên lấy `render_tutor_public_plan(phase="act", ...)`
- chỉ fallback về narrator cũ khi plan không có fragment

Điều này gỡ thêm một producer phụ trước đây vẫn đẩy một block tutor-thinking giọng cũ sau `tool_result`.

### 5. Tutor answer prompt tightened

`build_tutor_system_prompt(...)` được thêm `TUTOR_RESPONSE_STYLE_INSTRUCTION`:

- không mở đầu bằng lời chào
- thesis-first
- không headings mặc định nếu user không yêu cầu
- giọng instructional, không companion-heavy

## Tests

Focused suite:

```text
python -m pytest maritime-ai-service/tests/unit/test_public_thinking_renderer.py maritime-ai-service/tests/unit/test_tutor_agent_node.py -q
35 passed
```

Compile check:

```text
python -m py_compile ...
pass
```

## Live verification

Server restarted:

```text
docker restart wiii-app
health/live => alive
```

Artifacts:

- sync v1: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-quality-sync-2026-03-30.json`
- stream v1: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-quality-stream-2026-03-30.txt`
- sync v2: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-quality-sync-2026-03-30-r2.json`
- stream v2: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-quality-stream-2026-03-30-r2.txt`

Prompt probe:

```text
Giải thích Rule 15 khác gì Rule 13
```

### Current truth after patch

#### Stream gray rail

`thinking_start` hiện ra đúng kiểu phase-aware:

- `Chot diem gay lech`
- `Doi chieu moc tri thuc`

Body stream không còn block narrator cũ sau `tool_result`.

`thinking_content` cuối của stream hiện còn một fragment chính:

```text
Gio minh can goi ra dung ranh gioi giua Rule 13 va Rule 15 tu nguon, de khi quay lai giai thich thi moi cau deu bam vao mot moc co the kiem chung duoc.
```

Tức là tutor thinking đã sạch hơn, mảnh hơn, và authority đã bớt phân tán.

#### Sync thinking

`/api/v1/chat` hiện cũng cho `thinking_content` đúng fragment curated ở trên, không còn ghép thêm prose reflection dài kiểu cũ.

## What is fixed

1. `tutor` không còn đẩy raw `tool_think` ra public thinking.
2. `tutor` không còn dựa vào `summary` để vừa làm header vừa làm body.
3. `tutor` không còn giữ hai producer lớn cạnh nhau cho beat phase và act reflection.
4. Sync/stream parity của `thinking_content` tốt hơn rõ rệt ở case tutor compare.

## What is still not fixed

Answer tone của tutor vẫn chưa sạch hẳn.

Live probes sau patch cho thấy:

- sync answer vẫn còn câu mở đầu kiểu “Để mình giúp bạn...”
- stream answer vẫn còn khá companion-heavy ở vài run, thậm chí có run vẫn mở bằng “Chào bạn...”
- formatting answer vẫn còn tendency dùng bold section / checklist nhiều hơn mức lý tưởng

Nói ngắn gọn:

- `thinking authority` của tutor đã tiến đúng hướng
- `answer voice contract` của tutor vẫn chưa được enforcement đủ mạnh

## Next recommended step

Tách tiếp `tutor answer contract` ra thành một lớp riêng, thay vì chỉ prompt-only:

1. hậu xử lý mở bài tutor để chặn greeting/companion opener khi intent=`learning`
2. normalize answer shape về `thesis-first -> explain -> example`
3. hạn chế headings/table mặc định nếu user không yêu cầu
4. nếu cần, đưa `tutor answer mode` vào shared response shaping layer thay vì để LLM tự quyết hoàn toàn
