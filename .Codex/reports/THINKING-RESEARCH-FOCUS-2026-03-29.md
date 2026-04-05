# Thinking Research Focus — 2026-03-29

## Executive Summary

Wiii đang gặp vấn đề `thinking` không phải vì thiếu “prompt hay” hay vì Gemini không đủ tốt. Gốc vấn đề hiện tại là:

1. `public thinking` ở direct lane phần lớn vẫn sinh từ **deterministic fallback summaries**.
2. cue đầu vào cho fallback này quá **thô** (`general`, `visual`, `social`, `knowledge`), nên dù prompt đẹp đến đâu vẫn dễ ra câu “ổn mà rỗng”.
3. narrator gần như **không được ăn dữ liệu thực sự giàu ngữ cảnh** từ tool results, nên không thể nghĩ kiểu: OPEC+, EIA, ICE, tồn kho, địa chính trị, v.v.
4. sync và stream vẫn chưa có **một authority duy nhất** cho public thinking, nên trải nghiệm cuối dễ lệch và nghe như nhiều lớp cùng “nghĩ”.

Nói ngắn gọn:

- vấn đề chưa nằm ở “câu văn chưa đẹp”
- vấn đề nằm ở **thinking representation + producer authority + evidence packaging**

Nếu muốn đạt thinking kiểu hệ thống chuyên nghiệp như ví dụ `phân tích giá dầu`, thứ cần nghiên cứu sâu trước là:

1. `public thinking producer`
2. `analytical task frame`
3. `evidence distillation into thinking`
4. `sync/stream authority parity`

Prompt engineering chỉ nên là **bước sau**, không phải bước đầu.

---

## User Example vs Current Wiii

Ví dụ thinking tốt mà user đưa ra có 4 đặc tính rất rõ:

1. **Mở bằng domain frame**
   - ví dụ: “kiến thức kinh tế vĩ mô”, “hiệu ứng domino”, “thị trường”
2. **Có tension thật**
   - ví dụ: phân vân giữa dữ liệu thô hay lồng địa chính trị
3. **Có evidence plan**
   - ví dụ: OPEC+, EIA, ICE, tồn kho, Trung Đông
4. **Có progression**
   - câu sau đi xa hơn câu trước, không paraphrase

Thinking hiện tại của Wiii cho case dầu:

```text
Nhịp này không cần kéo dài quá tay.

Mình chỉ cần bắt đúng điều bạn đang chờ ở mình rồi đáp cho thật gần.

Ở đây phần nhìn phải đi trước lời giải thích, để bạn liếc một lần là bắt được nhịp của giá dầu.

Mình sẽ chốt vài mốc đáng tin rồi dựng một khung gọn, sau đó mới nói phần nhận xét.
```

Vấn đề của block này không phải là “văn xấu”, mà là:

- không có domain frame thật
- không có uncertainty thật
- không có evidence plan thật
- không có judgment thật
- không có biến số phân tích thật

Nó là một **surface cue**, chưa phải một quá trình nghĩ có tri thức.

---

## Evidence From Current Code

### 1. Direct lane đang dùng deterministic fast narrator rất nhiều

Các nơi dùng `render_reasoning_fast`:

- [direct_reasoning.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_reasoning.py#L101)
- [direct_opening_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_opening_runtime.py#L8)
- [direct_tool_rounds_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_tool_rounds_runtime.py#L39)
- [graph_surface_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_surface_runtime.py#L109)
- [graph_stream_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_surface.py#L253)

`render_reasoning_fast` cuối cùng đi vào:

- [reasoning_narrator.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py#L315)

và hàm này trả thẳng:

- [reasoning_narrator.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py#L268)

tức là `render_fast()` hiện thực chất là **fallback deterministic narrator**, không phải analytical narrator thật.

### 2. Fallback deterministic đang sống bằng bộ câu mẫu

Các hàm quan trọng:

- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py#L161)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py#L241)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py#L260)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py#L278)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py#L290)
- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py#L308)

Đây là nơi sinh ra các block kiểu:

- `Nhịp này không cần kéo dài quá tay...`
- `Ở đây phần nhìn phải đi trước lời giải thích...`
- `Mình sẽ gom vài mốc đáng tin...`

Những câu này ổn với:

- greeting
- emotional
- identity
- social beat ngắn

Nhưng với analytical/data/economic turns, chúng trở thành **template voice**.

### 3. Cue taxonomy quá thô cho analytical thinking

Cue hiện tại suy ra ở:

- [direct_reasoning.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/direct_reasoning.py#L47)

Cue map hiện chủ yếu ra các loại:

- `visual`
- `datetime`
- `news`
- `legal`
- `web`
- `lms`
- `memory`
- `browser`
- `analysis`
- `personal`
- `social`
- `off_topic`
- `general`

Với prompt kiểu `phân tích giá dầu`, direct lane thường chỉ biết đây là:

- `lookup`
- `direct`
- đôi khi `visual`
- hoặc `news/web`

Điều bị thiếu là một analytical frame cụ thể như:

- `macro_market_analysis`
- `multi-factor causal analysis`
- `economic-with-live-data`
- `research synthesis with evidence plan`

Không có frame này thì narrator không thể nghĩ ra:

- biến nào quan trọng
- nguồn nào cần đối chiếu
- xung lực nào cần tách riêng
- uncertainty nào đáng nói

### 4. Tool context hiện quá nghèo để sinh domain-rich thinking

Tool context builder:

- [reasoning_narrator_support.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator_support.py#L367)

Nó chủ yếu đưa vào:

- tên tool
- mô tả tool
- một mảnh `result_text` rút gọn

Nhưng trong direct stream, tool result summary lại thường bị nén thành kiểu:

- `Da keo them vai nguon de kiem cheo.`
- `Mình đã có thêm vài mảnh dữ liệu để gạn lại cho câu trả lời chắc hơn.`

Tức là narrator không nhận được:

- OPEC+ đang cắt gì
- EIA tồn kho ra sao
- Brent/WTI đang lệch thế nào
- căng thẳng địa chính trị nào đang ảnh hưởng

Không có evidence cụ thể thì model không thể nghĩ cụ thể.

### 5. Public thinking cuối của sync chỉ là aggregate của delta đã stream

Capture logic:

- [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py#L73)
- [public_thinking.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/public_thinking.py#L81)
- [graph_process.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_process.py#L135)

Điều này đúng về mặt authority nếu `thinking_delta` đã tốt.

Nhưng hiện tại `thinking_delta` ở direct lane vẫn thường là output từ `render_fast` template, nên final `thinking_content` cũng generic theo.

### 6. Stream đang hiện timeline phase, không phải analytical thought plan

Các điểm stream chính:

- [graph_stream_node_runtime.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_node_runtime.py#L43)
- [graph_stream_agent_handlers.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_agent_handlers.py#L10)
- [graph_stream_surface.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_surface.py#L227)

Hiện stream cho direct lane thường là:

1. `attune`
2. tool rounds
3. `action_text`
4. `synthesize`

Vấn đề là hai beat `attune/synthesize` này vẫn thường dùng narrator fast template, nên timeline có cảm giác:

- đang “đi qua bước”
- chứ chưa thật sự “đi qua suy nghĩ”

### 7. Answer authority vẫn còn split theo thời điểm phát

Điểm này không phải gốc chất lượng thinking, nhưng là gốc lệch UX:

- [graph_stream_agent_handlers.py](/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph_stream_agent_handlers.py#L10)

Direct lane có thể stream answer ngay khi node direct xong, trong khi sync lấy final response cuối graph.

Điều này làm user rất dễ thấy:

- gray rail một kiểu
- answer một kiểu
- final metadata một kiểu

---

## Live Evidence: “phân tích giá dầu”

Artifacts:

- [thinking-oil-sync-2026-03-29.json](/E:/Sach/Sua/AI_v1/.Codex/reports/thinking-oil-sync-2026-03-29.json)
- [thinking-oil-stream-2026-03-29.txt](/E:/Sach/Sua/AI_v1/.Codex/reports/thinking-oil-stream-2026-03-29.txt)

Điều live case này cho thấy:

1. cùng một prompt nhưng sync/stream vẫn có thể chọn tool khác nhau vì đó là **hai lần inference khác nhau**
2. cả hai lần đều cho thấy public thinking hiện vẫn thiên về:
   - cue generic
   - visual/gạn dữ liệu chung chung
   - thiếu analytical variables
3. trong stream, `action_text` và `thinking` vẫn sống rất gần nhau về UX, dù contract logic đã tách

Case này cũng cho thấy một vấn đề phụ nhưng đáng chú ý:

- routing metadata nói `RAG_AGENT` mới là lane tối ưu
- nhưng final agent vẫn là `direct`

Nghĩa là analytical queries đang bị route vào một lane tối ưu cho “đáp gần” hơn là “phân tích sâu”.

---

## What We Should Research Deeply First

## Priority 1 — Public Thinking Producer

**Đây là lớp cần nghiên cứu đầu tiên.**

Mục tiêu:

- quyết định ai là canonical producer của public thinking
- mọi thứ user thấy trên gray rail phải sinh từ producer này
- `thinking_content` cuối chỉ là aggregate của producer đó

Hiện hướng đúng nhất là:

- `thinking_delta` public đã sanitize = authority
- sync final = join của chính các `thinking_delta`
- `action_text` không nhập vào gray rail

Nếu không chốt authority trước, mọi cố gắng sửa prompt sẽ tiếp tục bị chồng lớp.

## Priority 2 — Analytical Thinking Frame

Đây là research area quan trọng thứ hai.

Ta cần một frame giàu ngữ nghĩa hơn `cue=visual/news/web/general`.

Ví dụ cho class query như `phân tích giá dầu`, frame nên có:

- `topic`: giá dầu
- `domain`: energy markets / macro
- `analytical_mode`: multi-factor causal analysis
- `key_variables`: OPEC+, tồn kho, nhu cầu kinh tế, địa chính trị, Brent/WTI
- `evidence_plan`: EIA / ICE / news / OPEC announcements
- `decision`: cần dữ liệu live hay khung phân tích thôi?

Khi có frame này, narrator hoặc generator mới có thể ra thinking kiểu:

- thấy tension
- chọn biến
- chọn nguồn
- chọn cách trình bày

Đây mới là thứ hệ chuyên nghiệp đang làm.

## Priority 3 — Evidence Distillation

Nghiên cứu sâu vào cách đưa evidence từ tool results vào thinking.

Hiện giờ tool reflection chủ yếu là:

- “đã có thêm vài mảnh dữ liệu”
- “đã có thêm vài nguồn”

Cần thay bằng dạng distill cụ thể hơn:

- `signal_cards`
- `evidence_bullets`
- `domain entities`
- `conflict / agreement`

Ví dụ cho oil:

- OPEC+ giữ cắt giảm
- tồn kho Mỹ tăng/giảm
- Brent và WTI đang lệch nhịp
- thị trường phản ứng mạnh với Trung Đông hơn là nhu cầu thực

Nếu thinking không nhận được distilled evidence, nó mãi chỉ nói “mình đang gạn lại dữ liệu”.

## Priority 4 — Routing for Analytical Queries

Research riêng:

- query kiểu `phân tích ...`
- `tại sao ... tăng giảm`
- `đánh giá xu hướng ...`
- `so sánh tác động ...`

đang nên đi lane nào?

Hiện trạng cho thấy nhiều query analytical bị đẩy vào:

- `direct`
- rồi direct tự mở web/news/visual

Điều này cho response có thể tạm được, nhưng thinking thường không có khung “analysis-first”.

Ta cần quyết định:

- analytical query vẫn ở `direct` nhưng có `analysis frame`
- hay route sang một lane research/analysis riêng

Đây là nghiên cứu quan trọng trước khi đụng prompt.

## Priority 5 — Narrator Prompt and Skills

Chỉ nên nghiên cứu sâu lớp này **sau 4 lớp trên**.

Lý do:

- persona skills hiện tại thực ra viết khá đúng
- vấn đề nằm ở runtime đang không nuôi được narrator bằng frame + evidence đủ giàu

Nói cách khác:

- prompt không phải là thứ thiếu nhất
- **context richness** mới là thứ thiếu nhất

---

## What We Should Not Focus On First

Chưa nên dồn lực trước vào:

1. `PromptLoader`
2. memory/persona blocks
3. thêm nhiều câu “triết lý Wiii”
4. chỉnh từ ngữ bề mặt của 2-3 template hiện có

Những thứ này có thể giúp ở lớp polish, nhưng không giải quyết:

- lack of analytical frame
- lack of evidence
- split authority

---

## Recommended Research / Fix Order

## Phase A — Canonical Public Thinking Contract

Research and define:

- source of truth cho `thinking_delta`
- mapping giữa stream và final `thinking_content`
- tách hẳn `action_text` ra lane riêng

## Phase B — Analytical Thinking Frame

Thiết kế một object hoặc schema kiểu:

- `thinking_mode`
- `topic`
- `variables`
- `evidence_plan`
- `judgment`
- `decision`

áp cho queries phân tích, thị trường, kinh tế, chính sách, nghiên cứu, legal reasoning, v.v.

## Phase C — Evidence Distillation Layer

Sau mỗi tool round:

- rút ra `evidence signals`
- đưa signals đó vào public thinking producer
- không feed raw tool dump trực tiếp

## Phase D — Keep Deterministic Narrator Only for Lightweight Turns

`render_fast` vẫn rất hữu ích cho:

- emotion
- identity
- greeting
- social turns ngắn

Nhưng analytical turns nên chuyển sang:

- narrator LLM thật
- hoặc frame-to-thinking generator giàu context hơn

## Phase E — Route Research/Analysis Queries Better

Đây là lúc quyết định:

- direct + analysis frame
- hay analysis lane riêng

---

## Concrete Answer To The User’s Question

Nếu hỏi thẳng:

> “Chúng ta nên nghiên cứu sâu phần nào trước?”

thì câu trả lời là:

1. **public thinking producer**
2. **analytical thinking frame**
3. **evidence distillation từ tool results**
4. **routing của analytical queries**
5. **narrator prompt/skills chỉ sau đó**

Với trạng thái code hiện tại, sửa prompt trước sẽ chỉ làm câu chữ bớt buồn cười trong một số case, nhưng sẽ **không** đưa Wiii lên mức thinking chuyên nghiệp ổn định.

---

## One-Line Diagnosis

Wiii hiện đang có `voice of thought`, nhưng chưa có `structure of thought`.

Muốn đạt thinking chuyên nghiệp, ta phải xây lại:

- dữ liệu mà thinking được ăn
- khung mà thinking bám vào
- và authority nào quyết định thinking công khai

rồi mới tối ưu câu chữ.
