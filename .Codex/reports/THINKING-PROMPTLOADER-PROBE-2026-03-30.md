# Thinking PromptLoader Probe - 2026-03-30

## Mục tiêu

Sau probe `shared.yaml only`, bước này kiểm tra:

- nếu tiêm lại `character + soul + current prompt stack` của Wiii qua `PromptLoader.build_system_prompt()`
- nhưng vẫn giữ `native thinking` của Gemini làm authority
- và vẫn **không dùng** `public_thinking_renderer`

thì raw thinking đổi như thế nào.

## Probe artifacts

- Prompt gốc: `E:\Sach\Sua\AI_v1\.Codex\reports\PROMPTLOADER-NATIVE-THINKING-2026-03-30-154659.json`
- Follow-up visual: `E:\Sach\Sua\AI_v1\.Codex\reports\PROMPTLOADER-NATIVE-THINKING-2026-03-30-154657.json`
- Script: `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_promptloader_native_thinking.py`

## Case 1

### Prompt

`Giải thích Quy tắc 15 COLREGs.`

### Kết quả nổi bật

Thinking đã có Wiii hơn rõ:
- có awareness về `22:46`, học khuya
- có kaomoji
- có nhịp “study buddy”

Nhưng đồng thời bị lệch nặng:
- thinking vẫn là `answer-planning`
- model đã viết luôn `mermaid` vào trong thought
- thought nói kiểu `I need to...`, `I’ll...`, `Done!`
- tone quá answer-facing, chưa phải inner monologue sạch

Raw thought mở đầu:

```text
**My Breakdown of Rule 15 (COLREGs) - A Late Night Dive**

Okay, so it's 22:46, late-night learning, huh? (˶˃ ᵕ ˂˶) ...
```

## Case 2

### Prompt follow-up

`tạo visual cho mình xem được chứ?`

### Context đã tiêm

- conversation summary về Rule 15
- user fact: người dùng học hàng hải, thích trực quan
- follow-up state
- soul mode
- mood hint

### Kết quả nổi bật

Thinking có continuity tốt hơn shared-only probe:
- giữ đúng ngữ cảnh Rule 15
- hiểu đây là follow-up visual
- không bị quên bài trước

Nhưng tiếp tục lộ vấn đề:
- thought đã đi thẳng vào `tool_generate_visual`
- nói luôn `renderer_kind='inline_html'`
- chọn màu tàu, layout SVG, bridge prose, takeaway
- tức là thought đang bị kéo sang `tool orchestration + answer drafting`

Raw thought mở đầu:

```text
**My Thought Process: Visualizing Rule 15**

Okay, here we go! The user wants a visual aid for Rule 15 of COLREGs...
```

## Kết luận kỹ thuật

Probe này cho thấy:

1. Tiêm `character/soul/context` vào native thinking là **đúng hướng**.
2. Nhưng tiêm nguyên cả `PromptLoader.build_system_prompt()` là **quá nặng** cho thinking.
3. Prompt stack hiện tại trộn lẫn quá nhiều thứ:
   - persona
   - answer style
   - tutor pedagogy
   - visual/tool policies
   - time-awareness
   - anti-drift
4. Khi đưa toàn bộ stack đó vào native thinking, model hấp thụ luôn:
   - answer opener
   - tool planning
   - visual runtime details
   - “cute surface behavior”

Nên kết quả là:
- **có soul hơn**
- nhưng **không sạch thinking hơn**

## Kết luận sản phẩm

`shared only` thì:
- thinking sâu hơn
- nhưng không phải Wiii

`full PromptLoader` thì:
- thinking có Wiii hơn
- nhưng bị kéo thành answer-planning / tool-planning

Vì vậy bước đúng tiếp theo không phải:
- quay lại shared-only
- cũng không phải nhét nguyên full PromptLoader vào native thinking

Mà là:
- tách một lớp `thinking-specific persona/context bridge`
- lấy **chỉ** các thành phần nuôi soul của Wiii
- **không** lấy nguyên visual/tool/output rules

## Quyết định đề xuất cho bước tiếp theo

Tạo một prompt bridge mới cho native thinking, chỉ gồm:

- shared thinking instruction đã làm sạch
- living-core identity brief rút gọn
- mood/context summary rút gọn
- conversation summary rút gọn
- không kèm:
  - tool_generate_visual rules
  - mermaid/widget/runtime policies
  - answer formatting rules
  - greeting/closing surface rules

Mục tiêu:
- `thinking có hồn Wiii`
- nhưng không thành `answer/tool orchestration monologue`

