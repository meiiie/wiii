# Thinking Audit And Fix Plan — 2026-03-30

## Scope

Audit lại toàn bộ luồng `thinking` hiện tại của Wiii sau phase refactor, tập trung vào câu hỏi thực sự:

- vì sao có lúc gray rail nghe khá sống
- vì sao có lúc lại rơi về pseudo-thinking kỹ thuật hoặc answer draft
- cần sửa producer nào trước để thinking thật hơn, không chỉ ngắn hơn

## Method

Mình kiểm tra theo 4 lớp:

1. live HTTP `/api/v1/chat` và `/api/v1/chat/stream/v3`
2. backend producers của từng lane (`direct`, `rag`, `tutor`)
3. sync finalization (`thinking_content`) vs stream interval events (`thinking_start`, `thinking_delta`)
4. frontend assembly (`useSSEStream`, `chat-store`, `ThinkingJourneyBanner`, `InterleavedBlockSequence`)

Tham chiếu nguyên tắc thiết kế:

- Anthropic Extended Thinking: <https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking>
- Anthropic Streaming Messages: <https://docs.anthropic.com/en/api/messages-streaming>

Hai nguyên tắc quan trọng nhất từ các hệ chuyên nghiệp:

- `thinking` và `text` phải là hai loại content khác nhau
- streaming phải giữ ranh giới rõ giữa `thinking_delta`, `tool_use`, và `text/answer`

## Current Truth

### 1. Direct analytical lane đã tiến bộ thật

Local hiện tại với các prompt như:

- `giá dầu hôm nay`
- `phân tích giá dầu`
- `Phân tích về toán học con lắc đơn`

đã chủ yếu đi `direct` và cho ra thinking analytical tốt hơn trước.

Hiện quan sát được:

- `giá dầu hôm nay` route thành `direct` với `intent=web_search`, `final_agent=direct`
- public thinking hiện nói theo kiểu:
  - lực kéo nền vs nhiễu ngắn hạn
  - cân bằng mong manh
  - biến số bẻ hướng

Tức là direct lane hiện **không còn là điểm yếu số 1**.

### 2. RAG lane vẫn còn producer sai loại

Ở `CorrectiveRAG` streaming path hiện vẫn có code bơm raw analysis kỹ thuật ra `thinking`:

- `app/engine/agentic_rag/corrective_rag_stream_runtime.py`
- `app/engine/multi_agent/agents/rag_node.py`

Hiện `corrective_rag_stream_runtime.py` vẫn emit dạng:

- `Độ phức tạp: simple`
- `Chủ đề: ...`
- `Thuộc lĩnh vực chuyên ngành → Sử dụng Knowledge Base`
- `Độ tin cậy phân tích: 100%`

Rồi `rag_node.py` nhận event `thinking` này và đẩy tiếp ra public stream.

Đây **không phải inner voice**, mà là:

- query classification
- routing telemetry
- trace/explainability payload

Nó đang bị render như suy nghĩ công khai.

### 3. Tutor lane còn nghiêm trọng hơn: answer có thể rò vào thinking

Ở:

- `app/engine/multi_agent/agents/tutor_node.py`
- `app/engine/multi_agent/agents/tutor_surface.py`

Tutor loop hiện có hai hành vi nguy hiểm:

1. narrator LLM cho tutor có thể sinh ra summary mang nội dung answer thật
2. `tutor_node.py` có path đẩy pre-tool / pre-answer draft thành `thinking_delta`

Live probe `Giải thích Rule 15 là gì` cho thấy:

- `thinking_start.summary` đã mang nội dung giải thích gần như answer thật
- `thinking_delta` tiếp tục stream chính phần answer đó

Nghĩa là ở tutor lane hiện có lúc:

- `thinking` không còn là suy tư
- mà trở thành **answer draft bị đặt sai channel**

Đây là lỗi rất lớn của `thinking authority`.

### 4. Sync và stream hiện đã gần nhau hơn, nhưng chưa cùng một truth tuyệt đối

Hiện tại:

- sync final `thinking_content` được resolve qua `public_thinking`
- stream metadata cuối cũng đã đi qua cùng authority đó

Các file chính:

- `app/engine/multi_agent/public_thinking.py`
- `app/engine/multi_agent/graph_process.py`
- `app/engine/multi_agent/graph_stream_runtime.py`

Đây là tiến bộ đúng.

Nhưng vẫn còn lệch ở cấp producer:

- direct lane produce khá ổn
- rag lane produce technical analysis
- tutor lane produce answer-like content

Nên vấn đề còn lại **không phải authority tổng**, mà là **authority per lane**.

### 5. Frontend vẫn còn khuynh hướng kéo technical status lên mặt trước

Ở frontend:

- `src/hooks/useSSEStream.ts`
- `src/stores/chat-store.ts`
- `src/components/chat/ThinkingJourneyBanner.tsx`

`status` events vẫn được append vào `phase.statusMessages`.

`ThinkingJourneyBanner` lại dùng:

- `phase.statusMessages[last]`
- hoặc `phase.thinkingContent`

để dựng `caption/detail`.

Hệ quả:

- kể cả khi `status_only` chỉ là progress meta
- nó vẫn có thể thành “detail” của journey UI

Tức là UI vẫn còn trộn:

- thinking thật
- progress/status meta

## End-to-End Thinking Flow (Current)

### A. Sync path

`/api/v1/chat`

1. `ChatOrchestrator.prepare_turn()`
2. build execution input
3. graph / lane execution
4. lane writes:
   - `thinking`
   - `thinking_content`
   - `_public_thinking_fragments`
5. `graph_process._build_process_result_payload()`
6. `public_thinking._resolve_public_thinking_content(...)`
7. `chat_response_presenter.build_chat_response()`

### B. Stream path

`/api/v1/chat/stream/v3`

1. `chat_stream_coordinator.generate_stream_v3_events()`
2. graph streaming bootstrap
3. lane emits:
   - `thinking_start`
   - `thinking_delta`
   - `thinking_end`
   - `status`
   - `action_text`
   - `tool_call`
   - `tool_result`
   - `answer`
4. `chat_stream_presenter.serialize_stream_event()`
5. frontend `useSSEStream.ts`
6. `chat-store.ts` builds:
   - `streamingBlocks`
   - `streamingPhases`
7. `InterleavedBlockSequence` + `ThinkingJourneyBanner`

## Producer Audit

### 1. Direct lane

Files:

- `app/engine/multi_agent/direct_opening_runtime.py`
- `app/engine/multi_agent/direct_tool_rounds_runtime.py`
- `app/engine/multi_agent/direct_reasoning.py`
- `app/engine/reasoning/reasoning_narrator_support.py`

Current quality:

- mostly correct
- public thinking is genuinely interval-based
- action text is separated better than before

Current weakness:

- still somewhat scaffolded in some runs
- answer compression still not always ideal

Priority:

- medium

### 2. RAG lane

Files:

- `app/engine/agentic_rag/corrective_rag_stream_runtime.py`
- `app/engine/agentic_rag/corrective_rag_runtime_support.py`
- `app/engine/multi_agent/agents/rag_node.py`
- `app/engine/reasoning_tracer.py`

Current quality:

- explainability/tracing is rich

Current problem:

- trace/explainability payload is leaking into public thinking
- query-analysis telemetry is being mistaken for inner voice
- sync `thinking_content` can still inherit technical tracer summary

Priority:

- **P0**

### 3. Tutor lane

Files:

- `app/engine/multi_agent/agents/tutor_node.py`
- `app/engine/multi_agent/agents/tutor_surface.py`

Current quality:

- streaming is rich and fast

Current problem:

- answer draft can be emitted into `thinking_delta`
- narrator summary can become answer-like instead of meta-reasoning

Priority:

- **P0**

### 4. Frontend journey/meta lane

Files:

- `wiii-desktop/src/hooks/useSSEStream.ts`
- `wiii-desktop/src/stores/chat-store.ts`
- `wiii-desktop/src/components/chat/ThinkingJourneyBanner.tsx`

Current quality:

- nice structured UX

Current problem:

- status-only progress can still be elevated into visible “thinking journey” detail
- technical detail can survive as caption/chip context

Priority:

- **P1**

## Root Causes

### Root Cause 1: Different content classes still share one lane

Hiện có ít nhất 4 loại nội dung đang chạm vào `thinking` surface:

1. public reasoning thật
2. routing / query-analysis telemetry
3. progress meta
4. answer draft

Khi chúng đi chung một kênh, UI không thể “render đúng” được nữa.

### Root Cause 2: Thinking is not yet lane-owned

Hiện `thinking authority` đã tốt hơn ở mức tổng, nhưng từng lane vẫn khác nhau:

- `direct`: narrator-driven public thinking
- `rag`: tracer/explainability payload
- `tutor`: draft answer + narrator mix

Muốn thinking “như người thật”, mỗi lane phải có một loại public reasoning riêng.

### Root Cause 3: Tutor and RAG still optimize for explainability, not public inner voice

RAG và tutor hiện được xây theo hướng:

- giải thích pipeline
- cho thấy bước xử lý
- minh bạch tool/retrieval

Điều đó có ích cho observability, nhưng **không đồng nghĩa với inner voice chất lượng cao**.

### Root Cause 4: Frontend still treats some meta as narrative

Ngay cả khi backend phát `status_only`, frontend vẫn có path dùng status message làm `journey.caption`.

Điều này làm ranh giới giữa:

- pipeline progress
- public thinking

bị mờ đi.

## What “Human-Like Thinking” Should Mean For Wiii

Không phải:

- ngắn hơn
- văn hoa hơn
- nhiều chữ hơn

Mà là:

1. thấy Wiii đang cân điều gì
2. biết vì sao Wiii chưa vội kết luận
3. nhìn được trục nào đang giữ kết luận, trục nào chỉ là nhiễu
4. không thấy pipeline telemetry
5. không bị lẫn với answer draft

Nói ngắn gọn:

- user phải thấy “Wiii đang suy tư”
- chứ không phải “hệ thống đang báo trạng thái”

## Fix Plan

## Phase 1 — Hard Source Separation

Mục tiêu:

- loại producer sai loại khỏi public thinking

### Patch 1A — Ban query-analysis telemetry from public thinking

Target:

- `app/engine/agentic_rag/corrective_rag_stream_runtime.py`
- `app/engine/multi_agent/agents/rag_node.py`
- `app/engine/agentic_rag/corrective_rag_runtime_support.py`

Actions:

- `Độ phức tạp / Domain / 100%` không còn được emit dưới `thinking`
- chuyển chúng thành:
  - trace-only
  - hoặc `status_only`
  - hoặc metadata nội bộ
- `rag_node` chỉ được bơm ra public thinking sau khi đã qua một summarizer đúng kiểu “evidence sufficiency”

Acceptance:

- query RAG không còn hiện `simple / domain / confidence`

### Patch 1B — Stop answer draft from entering tutor thinking

Target:

- `app/engine/multi_agent/agents/tutor_node.py`
- `app/engine/multi_agent/agents/tutor_surface.py`

Actions:

- cấm pre-answer draft đi vào `thinking_delta`
- narrator summary cho tutor phải là meta-reasoning, không phải mini-answer
- nếu cần draft riêng thì giữ private buffer, không surface

Acceptance:

- `Giải thích Rule 15 là gì`:
  - thinking không được chứa đoạn answer hoàn chỉnh
  - answer chỉ xuất hiện ở answer lane

## Phase 2 — Lane-Owned Public Thinking

Mục tiêu:

- mỗi lane có một “kiểu suy tư công khai” riêng

### Direct

- analytical
- relational
- visual/editorial

### RAG

public thinking phải xoay quanh:

- nguồn nào đủ tin
- khoảng trống nào còn thiếu
- tại sao phải tra cứu thêm hay fallback

không được xoay quanh:

- complexity
- domain classification
- confidence scoring

### Tutor

public thinking phải xoay quanh:

- điểm dễ hiểu sai
- mô hình giải thích chọn dùng
- cách sắp lại ý cho người học

không được trở thành:

- answer draft
- lesson prose chưa gửi

## Phase 3 — Frontend Demotion Of Meta

Mục tiêu:

- UI chỉ render inner voice là inner voice

Target:

- `wiii-desktop/src/hooks/useSSEStream.ts`
- `wiii-desktop/src/stores/chat-store.ts`
- `wiii-desktop/src/components/chat/ThinkingJourneyBanner.tsx`

Actions:

- `status_only` không được chiếm `journey.caption` nếu phase đã có real thinking
- technical status chỉ ở progress surface phụ
- journey banner headline/caption ưu tiên:
  - `thinkingContent`
  - rồi mới tới humanized status

## Phase 4 — Richer Reasoning Contracts

Sau khi source separation sạch, mới nâng chất:

- direct analytical: deeper causal weighing
- rag: richer evidence sufficiency voice
- tutor: “teaching strategy” voice

Lúc đó prompt/narrator work mới thật sự có ROI cao.

## Recommended Order

1. **P0**: RAG technical leak
2. **P0**: Tutor answer-in-thinking leak
3. **P1**: Frontend meta demotion
4. **P1**: richer lane-specific reasoning quality

## Concrete Acceptance Tests

### Test A — Market live query

Prompt:

- `giá dầu hôm nay`

Pass when:

- no `Độ phức tạp`
- no `Knowledge Base`
- no `100%`
- thinking speaks in market forces / uncertainty / signal-vs-noise terms

### Test B — Tutor concept query

Prompt:

- `Giải thích Rule 15 là gì`

Pass when:

- thinking does not contain answer prose
- answer lane carries the explanation
- thinking only shows teaching strategy / key difficulty / framing

### Test C — Analytical math

Prompt:

- `Phân tích về toán học con lắc đơn`

Pass when:

- thinking mentions model validity / assumptions / where derivation can go wrong
- answer remains separate

### Test D — UI journey banner

Pass when:

- journey caption never surfaces technical telemetry as if it were inner voice

## Recommendation

Đợt sửa tiếp theo nên bắt đầu bằng **Patch 1A + Patch 1B**.

Lý do:

- đây là hai chỗ đang làm user cảm thấy “thinking giả”
- và chúng là bug về content class / producer authority, không phải bug về style

Nếu sửa đúng hai chỗ này trước, những patch nâng chất tiếp theo mới thực sự “ăn”.
