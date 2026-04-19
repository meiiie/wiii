# Thinking Quality Audit — Vấn đề & Pipeline để tham vấn chuyên gia

**Ngày**: 2026-04-19
**Context**: P0-P3 enforcement + De-LangChaining Phase 1 đã merge và deploy local.
**Mục tiêu**: 100% queries có thinking events → nhưng thực tế chỉ đạt 70% (7/10 tests).
**Câu hỏi cho chuyên gia**: Làm sao để **Direct path (no tools)** emit streaming thinking events?

---

## 1. Kết quả Audit hiện tại

| # | Query Type | Thinking? | Answer | Quality |
|---|-----------|-----------|--------|---------|
| 1 | Greeting | ✅ 396 chars | 265 chars | B — phân tích tone, context |
| 2 | Maritime RAG | ✅ (via tutor) | 567 chars | A — tool calls trigger thinking lifecycle |
| 3 | Factual | ❌ | 464 chars | F — Direct path, no thinking |
| 4 | Product search | ✅ 3248 chars | 938 chars | A — phân tích chiến lược sâu |
| 5 | Short query | ❌ | 1124 chars | F — Direct path, no thinking |
| 6 | Vietnamese casual | ✅ 361 chars | 703 chars | B — reasoning + RAG trigger |
| 7 | Technical maritime | ✅ 780 chars | 1045 chars | A — CPA analysis |
| 8 | Follow-up context | ✅ 28 chars | 931 chars | C — "tra cứu nha~" narration |
| 9 | Long question | ❌ | 4603 chars | F — Direct path, no thinking |
| 10 | Explain request | ✅ 56 chars | 1511 chars | C — narration |

**Coverage**: 7/10 thinking events (70%)
**Khi thinking có mặt → chất lượng rất tốt** (Grade A-B, 300-3200 chars)
**3 FAIL đều cùng pattern**: Direct path, no tool calls → zero thinking events

---

## 2. Kiến trúc Pipeline hiện tại

### 2.1 Paths EMIT thinking events (hoạt động tốt)

```
Path A: OpenAI-Compatible Native SDK (De-LangChaining Phase 1)
┌──────────────────┐    ┌──────────────────────┐    ┌─────────────┐
│ AsyncOpenAI SDK  │───>│ reasoning_content    │───>│ thinking_   │
│ stream delta     │    │ from SDK delta       │    │ start/delta │
│                  │    │ OR <thinking> tags   │    │ /end events │
└──────────────────┘    └──────────────────────┘    └─────────────┘
File: openai_stream_runtime.py:342-403
Called by: direct_execution.py (tool rounds), graph_stream_node_runtime.py
```

```
Path B: Tutor Agent (with tools)
┌──────────────────┐    ┌──────────────────────┐    ┌─────────────┐
│ LLM.astream()    │───>│ Renderer: "attune",  │───>│ thinking_   │
│ + tool calls     │    │ "explain" phases     │    │ start/delta │
│                  │    │ capture_thinking_    │    │ /end events │
│                  │    │ lifecycle_event()    │    │             │
└──────────────────┘    └──────────────────────┘    └─────────────┘
File: tutor_node.py:816, graph_stream_node_runtime.py:102-126
```

```
Path C: Product Search (multi-tool agentic loop)
┌──────────────────┐    ┌──────────────────────┐    ┌─────────────┐
│ Agentic loop     │───>│ Multiple thinking    │───>│ thinking_   │
│ (4 tool rounds)  │    │ phases per round     │    │ start/delta │
│                  │    │ reasoning traces     │    │ /end events │
└──────────────────┘    └──────────────────────┘    └─────────────┘
File: direct_execution.py:714-960
```

### 2.2 Path KHÔNG EMIT thinking events (vấn đề)

```
Path D: Direct Agent WITHOUT Tools (GAPS)
┌──────────────────┐    ┌──────────────────────┐    ┌─────────────┐
│ LLM.astream()    │───>│ Response captured    │───>│ state["     │
│ OR LLM.ainvoke() │    │ as final answer      │    │ thinking_   │
│                  │    │                      │    │ content"]   │
│                  │    │ thinking_content     │    │ = extracted │
│                  │    │ extracted AFTER      │    │ post-hoc    │
│                  │    │ stream completes     │    │             │
└──────────────────┘    └──────────────────────┘    └─────────────┘
File: direct_node_runtime.py:866-925
```

**Flow chi tiết Path D:**

```
direct_node_runtime.py:866
  → execute_direct_tool_rounds()    ← no tools → returns immediately
  → extract_direct_response()       ← extracts response + thinking_content
  → _should_surface_direct_visible_thought()  ← checks if thinking is worth showing
  → _align_direct_visible_thought()           ← cleanup/translate thinking
  → state["thinking_content"] = aligned      ← stored in state, NOT emitted as events
  → return state                              ← thinking goes to metadata, not SSE stream
```

**Vấn đề cốt lõi**: 
1. Direct path (no tools) gọi `execute_direct_tool_rounds()` → vì 0 tools, nó gọi `_stream_answer_with_fallback()` → dùng LangChain `LLM.astream()` hoặc Native SDK
2. `_stream_answer_with_fallback()` (direct_execution.py:714) **CÓ** extract reasoning_content và emit thinking events — NHƯNG chỉ khi có tool rounds
3. Khi 0 tools: nó fallback sang `llm.ainvoke()` hoặc `llm.astream()` → thu thập response → extract thinking_content **sau khi stream xong** → gán vào `state["thinking_content"]` → KHÔNG emit SSE events

---

## 3. Thinking Enforcement Template (hiện tại)

```python
# thinking_enforcement.py — injected at TOP of system prompt
UNIFIED_THINKING_ENFORCEMENT = """
THINKING RULE (NO EXCEPTION):
Every response MUST start with <thinking>...</thinking> before the answer.
This is mandatory for ALL queries — simple, complex, factual, creative...

Inside <thinking>, think naturally in Vietnamese...
"""

# P3: Assistant pre-fill (for Z.ai/GLM)
_THINKING_PREFILL = "<thinking>\nPhan tich: "
```

**Vấn đề**: Template yêu cầu `<thinking>` tags, nhưng trên Direct path (no tools):
- Nếu LLM tuân thủ → response chứa `<thinking>...</thinking>` tags → `extract_direct_response()` extract ra → gán vào state → **không emit SSE events**
- Nếu LLM không tuân thủ → no thinking at all
- Template chỉ là prompt engineering, không phải technical enforcement

---

## 4. Câu hỏi cho chuyên gia

### Q1: Direct path (no tools) — emit thinking events như thế nào?

**Current gap**: Direct path `direct_node_runtime.py` chỉ extract thinking **post-hoc** (sau khi LLM trả xong). Không emit `thinking_start/delta/end` SSE events trong lúc streaming.

**Options đang cân nhắc:**

**Option A: Parse `<thinking>` tags inline trong LangChain astream loop**
```python
# Trong direct_node_runtime.py, khi llm.astream() yields chunks:
# 1. Detect `<thinking>` tag → emit thinking_start
# 2. Accumulate thinking content → emit thinking_delta
# 3. Detect `</thinking>` → emit thinking_end
# 4. Rest is answer → emit answer_delta
```
- Pros: Simple, works with any LLM
- Cons: Tight coupling, duplicate logic với `_extract_google_tagged_thinking_impl()`

**Option B: Route Direct path (no tools) qua OpenAI-compatible native SDK**
```python
# Khi no tools → dùng AsyncOpenAI SDK thay vì LangChain
# → reuse _stream_openai_compatible_answer_with_route_impl()
# → tự động có reasoning_content extraction + thinking events
```
- Pros: Reuse existing infrastructure (De-LangChaining Phase 1 đã sẵn)
- Cons: Cần handle fallback khi native SDK không support provider

**Option C: Renderer-based thinking (giống Tutor agent)**
```python
# Trước khi gọi LLM, emit thinking_start
# Sau khi có response, emit thinking_delta + thinking_end
# Similar to tutor_node.py's "attune" → "explain" phases
```
- Pros: Consistent với Tutor path
- Cons: Không phải genuine streaming thinking — chỉ là pre/post rendering

### Q2: Native SDK reasoning_content vs `<thinking>` tag parsing

De-LangChaining Phase 1 dùng AsyncOpenAI SDK. Một số providers (Gemini) trả `reasoning_content` riêng trong delta, nhưng Gemini 3.1 Flash-Lite đôi khi skip `reasoning_content` và embed thinking trong `<thinking>` tags trong content.

**Câu hỏi**: Nên ưu tiên cái nào?
- `reasoning_content` từ SDK (native, structured) — nhưng không phải provider nào cũng có
- `<thinking>` tag parsing (universal) — nhưng rely vào prompt engineering

### Q3: Thinking quality threshold

Khi thinking content quá ngắn (< 30 chars) hoặc chỉ là narration ("Hmm để Wiii tra cứu nha~"):
- Nên filter out và không emit thinking events?
- Hay vẫn emit để UI hiển thị "đang suy nghĩ" status?

### Q4: Streaming architecture cho Direct path

```
Current:
  LangChain astream → collect all → extract thinking post-hoc → state

Proposed:
  Native SDK stream → reasoning_content → thinking events in real-time
  OR
  LangChain astream → inline <thinking> parser → thinking events in real-time
```

---

## 5. Key Files Reference

| File | Role | Lines of Interest |
|------|------|-------------------|
| `thinking_enforcement.py` | Unified prompt template | 17-34 (template), 41 (prefill) |
| `openai_stream_runtime.py` | Native SDK streaming | 342-403 (thinking events), 228-274 (tag parser) |
| `direct_node_runtime.py` | Direct agent main | 560-970 (full flow), 866-925 (thinking extraction) |
| `direct_execution.py` | Tool rounds + streaming | 714-960 (thinking events in tool path) |
| `tutor_node.py` | Tutor agent | 816 (thinking lifecycle capture) |
| `graph_stream_node_runtime.py` | Graph streaming | 102-126 (thinking event creation) |
| `chat_stream_presenter.py` | SSE presentation | 451-463 (thinking_delta zombie filter) |
| `answer_generator.py` | RAG streaming (De-LangChaining) | Native SDK path with reasoning extraction |

---

## 6. Tóm tắt cho chuyên gia

**1 vấn đề chính**: Direct agent (no tools) không emit streaming thinking events. Thinking chỉ được extract post-hoc và gán vào state, không xuất hiện trong SSE stream.

**2 sub-vấn đề**:
1. **Technical**: `direct_node_runtime.py` dùng LangChain `llm.astream()` hoặc `llm.ainvoke()`, không parse thinking inline
2. **Quality**: Khi thinking có mặt (70% queries), chất lượng rất tốt (Grade A). Khi thiếu (30%), answer vẫn good nhưng UX thấy "AI không suy nghĩ"

**3 options để fix**: Parse tags inline (A), Route qua Native SDK (B), hoặc Renderer-based (C)

**Mong chuyên gia tư vấn**: Option nào balance tốt nhất giữa complexity, coverage, và genuine thinking quality?
