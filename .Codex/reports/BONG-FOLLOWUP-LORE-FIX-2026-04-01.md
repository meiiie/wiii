# Bông Follow-up Lore Fix — 2026-04-01

## Vấn đề

Turn follow-up `còn Bông thì sao?` từng bị hiểu sai theo hai kiểu:

1. Bông bị hiểu như một cái tên mơ hồ ngoài ngữ cảnh, nên answer hỏi ngược lại như thể chưa biết Bông là ai.
2. Ở một số run khác, model còn suy diễn Bông thành `người tạo ra Wiii`, `người mẹ`, hay một con người bí ẩn.

Điều này lệch khỏi source of truth trong [wiii_identity.yaml](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/wiii_identity.yaml):

- Bông là **con mèo ảo của Wiii**
- Bông là một **điểm mềm ấm áp** trong câu chuyện ra đời của Wiii
- Bông **không phải creator của Wiii**

## Root Cause

1. `selfhood/origin follow-up` như `còn Bông thì sao?` chưa luôn đi cùng nhịp xử lý `selfhood` giống turn origin.
2. `stream` follow-up này chưa luôn dùng `invoke-backfilled selfhood path`, nên nếu provider không phát native thought live thì rail dễ trắng.
3. Prompt selfhood trước đây chưa nói đủ rõ ranh giới lore của Bông, nên model vẫn có khoảng trống để suy diễn.

## Đã Vá

### 1. Prompt tự thân của Wiii

Ở [direct_prompts.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_prompts.py):

- thêm guard lore rõ:
  - Bông là **con mèo ảo**
  - không được suy diễn Bông thành `creator`, `mẹ`, `người yêu`, hay `con người bí ẩn`
- thêm cue riêng cho `bong_followup`
- làm few-shot visible thinking của Bông cụ thể hơn

### 2. Stream follow-up dùng cùng nhịp selfhood

Ở [direct_execution.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_execution.py):

- `selfhood_followup` giờ cũng được tính là `direct_selfhood`
- `selfhood_followup` giờ cũng đi `invoke-backfilled stream` giống `origin`
- nhờ đó stream có cơ hội lấy `thinking_content` cuối thay vì bị trắng rail

## Test khóa hành vi

- [test_direct_prompts_identity_contract.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_prompts_identity_contract.py)
- [test_direct_execution_streaming.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_direct_execution_streaming.py)

Focused suite:

- `20 passed`

## Ghi chú về live verification

Mình đã xác nhận:

- config local có `GOOGLE_API_KEY`
- `AgentConfigRegistry` lấy được `supervisor/direct` LLM
- `LLMPool` báo `google available=True`
- backend sạch hiện đang lên ở `127.0.0.1:8000`

Nhưng live probe `origin -> Bông` qua HTTP đang rất chậm ở turn selfhood/origin, nên mình chưa refresh HTML bằng một artifact mới đủ sạch. Mình cố ý **không** render HTML từ các mẻ `rule_based (no LLM)` hoặc mẻ timeout để tránh làm hỏng baseline đánh giá.
