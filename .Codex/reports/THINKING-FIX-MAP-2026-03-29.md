# Thinking Fix Map — 2026-03-29

## Goal

Đưa Wiii từ:

- `voice of thought`

thành:

- `structure of thought`

Mục tiêu không phải chỉ làm thinking “đỡ buồn cười”, mà là khiến nó:

1. có domain frame thật
2. có evidence plan thật
3. có progression thật
4. có parity thật giữa stream và final sync payload

---

## Current Backend Truth

### Current producer reality

- lightweight/direct public thinking chủ yếu sinh từ `render_fast`
- `render_fast` hiện là deterministic fallback
- sync final `thinking_content` là aggregate của `thinking_delta`
- stream lại hiển thị theo phase và có thêm `action_text`

### Current failure pattern

Với prompts analytical như:

- `phân tích giá dầu`
- `phân tích về toán học con lắc đơn`
- `đánh giá xu hướng ...`

Wiii thường:

1. route vào `direct`
2. tự mở web/news/visual tools
3. nhưng public thinking vẫn chỉ phản ánh:
   - “bắt nhịp”
   - “gạn dữ liệu”
   - “dựng phần nhìn”

Tức là thinking đang mô tả **operational movement**, chưa mô tả **cognitive movement**.

---

## Fix Strategy

## Step 1 — Define a Canonical Public Thinking Frame

### Add

Một schema mới cho analytical turns, ví dụ:

```python
PublicThinkingFrame(
    mode="analytical",
    topic="giá dầu",
    lens="macro_market",
    key_variables=[...],
    uncertainty=[...],
    evidence_plan=[...],
    decision="..."
)
```

### Why

Hiện narrator chỉ nhận:

- `cue`
- `intent`
- `tool_context`
- `observations`

chừng đó chưa đủ để nghĩ sâu.

### Files to touch

- [direct_reasoning.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_reasoning.py)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py)
- [graph_surface_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_surface_runtime.py)

### Acceptance

Với `phân tích giá dầu`, internal frame phải có ít nhất:

- topic
- analytical lens
- 2+ key variables
- 1+ evidence source plan

---

## Step 2 — Split Lightweight vs Analytical Narration

### Keep deterministic for

- greeting
- emotional
- identity
- short social turns

### Stop using deterministic fallback as primary producer for

- market analysis
- research synthesis
- legal reasoning
- economic explanation
- data interpretation

### Files to touch

- [reasoning_narrator.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py)

### Expected outcome

`render_fast` chỉ còn làm tốt phần:

- relational
- emotional
- identity

Analytical turns phải đi qua:

- narrator LLM thật
- hoặc frame-renderer giàu context hơn

---

## Step 3 — Distill Evidence From Tool Results

### Problem now

Tool result reflection hiện đang nén thành:

- “đã có thêm vài mảnh dữ liệu...”
- “đã kéo thêm vài nguồn...”

Điều này làm public thinking không có domain nouns.

### Needed change

Sau mỗi tool round, sinh một lớp:

- `evidence_signals`
- `source_signals`
- `conflict_signals`

Ví dụ:

- `OPEC+ cắt giảm vẫn là lực đỡ giá`
- `nhu cầu chậm lại đang ghìm đà tăng`
- `Brent/WTI cần tách riêng`

### Files to touch

- [direct_tool_rounds_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_tool_rounds_runtime.py)
- [direct_reasoning.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_reasoning.py)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py)

### Acceptance

Analytical turns phải có thinking chứa:

- ít nhất 2 domain nouns thật
- ít nhất 1 source family hoặc evidence family
- ít nhất 1 judgment/trade-off

---

## Step 4 — Make Stream Thinking the One True Authority

### Current direction

Đây là hướng đúng đã có mầm sẵn:

- capture `thinking_delta`
- sync final join lại

### What must be tightened

1. `action_text` không bao giờ được nhập vào public thinking
2. `thinking_start.summary` không được trở thành một source sự thật độc lập
3. final `thinking_content` chỉ được là aggregate của:
   - `thinking_delta`
   - hoặc fallback duy nhất nếu hoàn toàn không có delta

### Files to touch

- [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py)
- [graph_stream_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_surface.py)
- [graph_stream_node_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_node_runtime.py)
- [graph_process.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_process.py)

### Acceptance

Trong một request duy nhất:

- thứ user thấy trên gray rail
- và `thinking_content` cuối

phải cùng một nội dung canon, chỉ khác ở việc:

- stream là timeline
- sync là joined form

---

## Step 5 — Improve Analytical Routing

### Problem

Nhiều prompts analytical đang có metadata kiểu:

- `llm_reasoning`: RAG_AGENT phù hợp
- nhưng final agent: `direct`

### Needed research decision

Chọn một trong hai:

1. analytical stays in `direct`, but `direct` gets a real analytical frame
2. analytical routes to a dedicated research/analysis lane

### Recommendation

Ngắn hạn:

- giữ `direct`
- nhưng thêm `analysis frame`

Dài hạn:

- cân nhắc `analysis/research lane`

### Files to inspect first

- [supervisor_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor_surface.py)
- [supervisor.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py)
- [direct_reasoning.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_reasoning.py)

---

## Top Files For The First Sprint

Nếu chỉ chọn 5 file cho sprint sửa thinking đầu tiên, nên là:

1. [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py)
2. [reasoning_narrator.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py)
3. [direct_reasoning.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_reasoning.py)
4. [direct_tool_rounds_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_tool_rounds_runtime.py)
5. [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py)

Nếu có thêm 3 file nữa:

6. [graph_stream_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_surface.py)
7. [graph_stream_node_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_node_runtime.py)
8. [supervisor_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor_surface.py)

---

## Top Function Cuts

Đây là các function có ROI cao nhất:

1. `_infer_direct_reasoning_cue()`
2. `_build_direct_tool_reflection()`
3. `build_fast_summary_impl()`
4. `build_fast_action_text_impl()`
5. `render_fast()`
6. `_render_fallback_narration_impl()`
7. `_capture_public_thinking_event()`
8. `_resolve_public_thinking_content()`
9. `emit_node_thinking_impl()`
10. `handle_direct_node_impl()`

---

## Concrete Acceptance Criteria For “Professional Thinking”

Cho một prompt analytical như `phân tích giá dầu`, public thinking đạt chuẩn khi:

1. không chứa câu mở kiểu:
   - `Nhịp này không cần kéo dài quá tay`
   - `Mình chỉ cần bắt đúng điều bạn đang chờ`
2. có ít nhất 1 domain frame
   - ví dụ: thị trường năng lượng, cung cầu, địa chính trị, tồn kho
3. có ít nhất 1 tension thật
   - ví dụ: OPEC+ vs nhu cầu chậm lại
4. có ít nhất 1 evidence plan
   - ví dụ: EIA / OPEC / ICE / Brent / WTI / tồn kho
5. các delta phải tiến triển
   - không paraphrase lại câu trước
6. `thinking_content` cuối đúng bằng aggregate của delta đã hiện

---

## Suggested First Patch Sequence

### Patch 1

Tạo `thinking_mode` giàu hơn trong direct lane:

- `relational_light`
- `identity`
- `emotional`
- `visual_editorial`
- `analytical_market`
- `analytical_general`
- `knowledge_explainer`

### Patch 2

Cho analytical turns bypass `build_relational_summary_impl()`.

### Patch 3

Thêm evidence distillation object sau tool rounds.

### Patch 4

Feed evidence distillation vào narrator request.

### Patch 5

Khóa `thinking_content = join(public thinking deltas only)`.

---

## Bottom Line

Sửa thinking tốt không phải là viết lại 10 câu template cho hay hơn.

Sửa thinking tốt là:

1. cho Wiii một **khung nghĩ đúng**
2. cho Wiii **evidence đúng**
3. và chỉ để **một producer** chịu trách nhiệm cho public thinking

Làm xong 3 lớp đó, phần văn phong sẽ tự dễ nâng lên rất nhiều.
