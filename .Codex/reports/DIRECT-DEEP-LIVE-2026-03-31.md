# Direct Deep Live Check — 2026-03-31

## Scope

Xác nhận direct lane sau khi:
- chuẩn hóa `thinking_effort`
- thêm Google deep-tier model override
- giữ metadata runtime qua các lớp `bind(...)`
- forward đúng `tier` vào failover helper của direct tool-capable path
- strip raw `<thinking>` khỏi answer stream

## Research basis

Đối chiếu theo docs chính thức tại ngày 2026-03-31:
- Google Gemini Thinking: request-level thinking controls, tách khỏi model name
- OpenAI reasoning effort: request-level control
- Anthropic extended thinking: model-authored thought, orchestration mỏng
- Z.AI / GLM deep thinking: thinking mode tách khỏi model

Kết luận áp dụng cho Wiii:
- reasoning control phải model-agnostic
- nhưng deep Google turns vẫn nên có model tier sâu riêng

## Runtime changes locked in

- `google_model_advanced` đã được nối vào config/runtime profile/provider stack
- Direct deep turns hiện có thể dùng `gemini-3.1-pro-preview`
- `direct_tool_rounds_runtime` đã forward `tier` thật vào `graph_ainvoke_with_fallback(...)`
- `direct_execution` đã strip partial/complete `<thinking>` khỏi streamed answer text

## Live probe used

- JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\live-origin-math-probe-2026-03-31-205951.json`
- Raw origin stream: `E:\Sach\Sua\AI_v1\.Codex\reports\live-stream-wiii-origin-2026-03-31-205951.txt`
- Raw hard-math stream: `E:\Sach\Sua\AI_v1\.Codex\reports\live-stream-hard-math-2026-03-31-205951.txt`
- HTML viewer: `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest.html`

## Current truth

### Origin / selfhood

- `sync_wiii_origin`
  - provider/model: `google / gemini-3.1-pro-preview`
  - answer tốt, đúng chất Wiii
  - visible thinking trống

- `stream_wiii_origin`
  - provider/model: `google / gemini-3.1-pro-preview`
  - answer tốt, không còn lộ raw `<thinking>`
  - visible thinking trống

### Hard math

- `sync_hard_math`
  - không còn fallback rỗng
  - answer dài và đúng bài
  - run này kết thúc ở `zhipu / glm-5`

- `stream_hard_math`
  - không còn lỗi `timeout_25.0s`
  - có `thinking_start -> thinking_delta -> thinking_end`
  - thinking bám đúng bài toán toán tử tự liên hợp / resolvent compact / Stone / deficiency indices
  - answer substantive, không còn generic fallback

## Interpretation

Điểm sửa quan trọng nhất là bug tier propagation trong direct tool-capable path:
- trước đây hard direct turn có thể bị gọi failover helper với tier mặc định `moderate`
- nên timeout rơi về 25s dù direct local heuristics đã muốn `high`
- sau khi forward đúng tier, hard-math live path không còn gãy theo kiểu cũ nữa

## Remaining issue

Direct visible thinking vẫn chưa ổn định giữa các loại turn:
- selfhood/origin: thường trống
- hard analytical: đã có thought thật

Điểm tiếp theo nên làm:
- nâng consistency của direct visible thought mà không quay lại template
- chỉ surface thought khi thật sự đáng surfacing
