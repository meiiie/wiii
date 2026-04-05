# Thinking Authority Stream Finalization Patch — 2026-03-29

## Mục tiêu

Khép lại một seam parity quan trọng:

- sync path đã resolve `thinking_content` từ `public_thinking`
- stream final metadata vẫn còn đọc thẳng `final_state["thinking_content"]`
- fallback stream path cũng còn gán cứng `thinking_content = fallback_result.thinking`

Điều này làm `thinking_content` cuối của stream có thể lệch khỏi chính những `thinking_delta` đã surface cho user.

## Patch

### 1. Multi-agent stream final metadata

File:
- `maritime-ai-service/app/engine/multi_agent/graph_stream_runtime.py`

Thay đổi:
- import `_resolve_public_thinking_content`
- trước khi emit `metadata`, compute:

```python
public_thinking_content = _resolve_public_thinking_content(
    final_state,
    fallback=final_state.get("thinking_content") or "",
)
```

- `thinking_content` trong metadata giờ dùng `public_thinking_content`

Ý nghĩa:
- stream metadata cuối giờ tin cùng một canonical resolver như sync payload
- không còn bị state thô đè ngược authority

### 2. Fallback stream path

File:
- `maritime-ai-service/app/services/chat_stream_coordinator.py`

Thay đổi:
- `thinking` ưu tiên `metadata["thinking"]`
- `thinking_content` ưu tiên `metadata["thinking_content"]`
- chỉ fallback về `fallback_result.thinking` khi metadata không có

Ý nghĩa:
- ngay cả khi không đi full multi-agent, stream metadata vẫn bám đúng canonical surface hơn

## Tests

### Mới thêm

- `maritime-ai-service/tests/unit/test_graph_stream_runtime.py`
  - `test_emit_stream_finalization_prefers_public_thinking_fragments`
  - `test_emit_stream_finalization_falls_back_to_existing_thinking_content`

- `maritime-ai-service/tests/unit/test_chat_stream_coordinator_fallback_authority.py`
  - `test_stream_fallback_metadata_prefers_thinking_content_from_metadata`

### Focused verification

Command:

```bash
python -m pytest \
  maritime-ai-service/tests/unit/test_graph_stream_runtime.py \
  maritime-ai-service/tests/unit/test_chat_stream_coordinator_fallback_authority.py \
  maritime-ai-service/tests/unit/test_chat_stream_presenter.py -q
```

Result:
- `14 passed`

## Live verification

Artifacts:
- `thinking-authority-sync-2026-03-29.json`
- `thinking-authority-stream-2026-03-29.txt`
- `thinking-authority-stream-metadata-2026-03-29.json`

### Điều đã xác nhận

- `/api/v1/chat` trả `200`
- `/api/v1/chat/stream/v3` trả `200`
- stream raw metadata giờ phản ánh đúng canonical `thinking_content` của stream final state

### Điều còn lại

Sync và stream khi gọi **hai request thật riêng biệt** vẫn có thể cho `thinking_content` khác nhau.

Case `Phân tích giá dầu` vừa recheck cho thấy:

- sync call: chỉ có 2 beat generic
- stream call: có 4 beat vì run đó còn đi thêm visual/tool plan khác

Điểm này **không còn là lỗi metadata authority cuối**, mà là:

- hai request LLM độc lập có nondeterminism
- planner/tool choice khác nhau giữa hai lần chạy thật
- stream có thể surface thêm phase/beat nếu run đó thật sự đi thêm tool/visual path

## Kết luận

Patch này đã sửa đúng lớp:

- `transport/final metadata authority`

Nó **chưa** sửa lớp:

- `thinking quality`
- `analytical thinking frame`
- `one true producer` giữa sync-vs-stream khi hai run thật tự chọn plan khác nhau

## Bước kế tiếp hợp lý

Không quay lại sửa prompt ngay.

Nên đi tiếp theo thứ tự:

1. chốt `one true public thinking producer` cho analytical/direct lane
2. quyết định stream có được phép surface multi-phase beats mà sync không serialize hay không
3. sau khi authority thật sự sạch, mới nâng chất `analytical thinking frame`
