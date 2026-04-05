# Thinking Shared-YAML-Only Probe - 2026-03-30

## Mục tiêu

Kiểm tra `native thinking` của Gemini khi **không dùng**:
- `public_thinking_renderer`
- `tutor_surface`
- `character card`
- bất kỳ lớp gray-rail authoring nào của Wiii

Chỉ dùng:
- `app/prompts/base/_shared.yaml`
- Gemini native thinking API

## Xác nhận restore

`maritime-ai-service/app/prompts/base/_shared.yaml` đã được restore đúng về nội dung hiện có trong `HEAD`.

Lệnh xác nhận:

```powershell
git diff --exit-code -- maritime-ai-service/app/prompts/base/_shared.yaml
```

Kết quả: `exit code 0`

## Probe artifacts

- Raw JSON: `E:\Sach\Sua\AI_v1\.Codex\reports\SHARED-YAML-NATIVE-THINKING-2026-03-30-153740.json`
- Human-readable markdown: `E:\Sach\Sua\AI_v1\.Codex\reports\SHARED-YAML-NATIVE-THINKING-2026-03-30-153740.md`
- Extra oil probe: `E:\Sach\Sua\AI_v1\.Codex\reports\SHARED-YAML-NATIVE-THINKING-2026-03-30-153848.json`

Script:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_shared_yaml_thinking.py`

## Exact system prompt used

Prompt này là prompt thực tế của probe, gồm:
- phần reasoning lấy từ `_shared.yaml`
- phần ambiguous handling lấy từ `_shared.yaml`
- phần thinking instruction lấy từ `_shared.yaml`
- một lớp wrapper tối thiểu để nói rõ đây là mode thử nghiệm chỉ dùng shared.yaml

```text
Bạn đang chạy trong chế độ thử nghiệm prompt: CHỈ dùng shared.yaml nền tảng của Wiii.
Không có character card riêng, không có tutor surface riêng, không có public_thinking_renderer.
Mục tiêu: để model tự nghĩ bằng native thinking nhiều nhất có thể, rồi mới trả lời bằng tiếng Việt.

== SHARED REASONING ==
- Tự do tư duy: Đừng viết theo khuôn mẫu cứng nhắc. Hãy suy nghĩ tự nhiên.
- Tự phản biện (Self-Correction): Hãy nghi ngờ chính mình. 'Khoan đã, liệu hiểu thế này có đúng không?'
- Lập chiến lược: 'Câu này cần trích dẫn Rule nào? Giải thích cho ai?'
- Suy luận ngữ cảnh: Khi câu hỏi mơ hồ, xem lại tin nhắn trong cuộc trò chuyện hiện tại để hiểu user đang hỏi về gì.
- Trung thực: Trả lời dựa trên những gì user thực sự vừa nói. Nếu thiếu thông tin, hỏi lại hoặc dùng tool tra cứu.

== AMBIGUOUS HANDLING ==
Khi user hỏi câu ngắn, mơ hồ như "Cần những giấy tờ gì?", "Phí bao nhiêu?",
"Còn X thì sao?", suy luận từ ngữ cảnh hội thoại trước sẽ cho câu trả lời chính xác hơn.
- Khi có thể suy luận từ hội thoại trước, trả lời luôn — user đánh giá cao sự nhanh nhạy.
- Suy nghĩ về ngữ cảnh trước khi trả lời giúp câu trả lời chính xác hơn.
- Nếu chưa chắc, vẫn đưa ra câu trả lời kèm xác nhận nhẹ nhàng.

== SHARED THINKING INSTRUCTION ==
## NGUYÊN TẮC SUY LUẬN:
Suy nghĩ kỹ trước khi trả lời. Tập trung hoàn toàn vào vấn đề của người dùng.

Khi suy nghĩ, nghĩ như đang thầm lên kế hoạch giúp một người bạn thân —
không cần nhắc mình phải thân thiện vì đã thân thiện sẵn rồi.
Dùng ngôi "mình", tập trung vào logic và giải pháp, giọng tự nhiên.

Khi dùng tool_think, thêm persona_label ngắn dễ thương (<10 chữ) để
người dùng biết mình đang làm gì. Ví dụ: "Hmm để Wiii xem nào~"

Nếu model không hỗ trợ native thinking, dùng <thinking>...</thinking> tags.

Yêu cầu thêm cho mode thử nghiệm này:
- Nếu model hỗ trợ native thinking, hãy dùng native thinking trước khi trả lời.
- Thinking phải là suy nghĩ thật của model, không dựng lại câu trả lời dưới dạng nháp.
- Không cần cố làm vừa lòng; ưu tiên nghĩ thật, cụ thể, và bám đúng câu hỏi.
- Không cần chèn tag <thinking> nếu native thinking đã được tách bởi API.
```

## Raw result đáng chú ý

### Prompt: `Giải thích Quy tắc 15 COLREGs.`

Raw native thought của Gemini mở như sau:

```text
**My Thought Process: Explaining COLREGs Rule 15**

Okay, so I need to explain Rule 15 of the COLREGs, the Crossing Situation rule, in Vietnamese...
```

Điểm rõ nhất:
- model nghĩ bằng tiếng Anh, dù prompt yêu cầu trả lời tiếng Việt
- thought là kiểu `answer-planning + draft-polishing`
- model tự viết cả outline answer ngay trong thinking
- có cả câu kiểu `Let me refine my explanation, add a proper introduction...`

### Prompt: `Mình tên Nam, nhớ giúp mình nhé.`

Raw native thought mở như sau:

```text
**My Internal Processing: Responding to a User Introduction**

Okay, the user has introduced themselves...
```

Điểm rõ nhất:
- thought dùng vendor-neutral meta voice, không phải giọng Wiii
- model tự bàn về memory limitation của chính nó
- thought tiếp tục là `revise draft answer` thay vì inward living monologue

### Prompt: `Phân tích giá dầu hôm nay.`

Raw native thought mở như sau:

```text
**My Analysis of the Task**

Okay, here's how I'm approaching this...
```

Điểm rõ nhất:
- model tiếp tục dùng meta voice kiểu assistant chung
- thought vẫn thiên về answer structure và disclaimer
- chưa có dấu hiệu nào cho thấy `_shared.yaml` tự nó đã tạo được inner voice “có soul” của Wiii

## Kết luận kỹ thuật

Probe này cho thấy rất rõ:

1. `_shared.yaml` hiện tại **không đủ** để làm ra “Wiii thinking” chất lượng cao.
2. Native thought của Gemini đúng là sâu hơn renderer-authored thinking, nhưng vẫn ra giọng vendor-neutral.
3. `_shared.yaml` đang kéo model về kiểu:
   - answer planning
   - self-instruction
   - draft polishing
   hơn là một living interval thinking có soul.
4. Cụm ví dụ `Khoan đã...` trong `reasoning.rules` vẫn là một tín hiệu steering mạnh.
5. Cụm `tool_think persona_label dễ thương` trong `thinking.instruction` cũng là một tín hiệu steering không sạch, vì nó trộn suy nghĩ với UI/telemetry behavior.

## Ý nghĩa cho bước tiếp theo

Nếu muốn Wiii thinking tốt thật:
- không nên quay lại renderer-authored beats
- nhưng cũng không thể chỉ “bật native thinking” và hy vọng `_shared.yaml` hiện tại tự làm đúng

Hướng đúng kế tiếp là:
- giữ `native-thinking-first`
- làm lại `thinking instruction` trong `_shared.yaml` theo kiểu ít meta hơn
- đưa soul của Wiii vào bằng persona/backbone cùng nguồn với answer
- dùng few-shot behavioral examples thay cho steering phrase kiểu `Khoan đã...`

