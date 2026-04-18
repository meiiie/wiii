# Thinking Prompt System — Bản đồ kiến trúc

> Ngày tạo: 2026-04-19  
> Mục đích: Ghi rõ toàn bộ setup prompt system liên quan thinking để đánh giá

---

## 1. Nguồn gốc Thinking Instruction

Thinking instruction được load từ **YAML config** qua `PromptLoader`:

```python
# File: app/prompts/prompt_loader.py → line 464
def get_thinking_instruction(self) -> str:
    return get_thinking_instruction_from_shared_config(self._shared_config)
```

Nội dung thực tế load được (kiểm tra qua Docker exec):

```
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

**Vấn đề**: Instruction này dùng **tiếng Việt có dấu**, nhưng directive nói "Nếu model không hỗ trợ native thinking, dùng `<thinking>...</thinking>` tags" — đây chỉ là gợi ý, KHÔNG phải yêu cầu bắt buộc. Nhiều model (đặc biệt Z.ai GLM-5) sẽ bỏ qua gợi ý này.

---

## 2. Nơi inject Thinking Instruction theo từng pipeline

### 2.1 Direct Path (Direct Agent)

**File**: `app/engine/multi_agent/direct_prompts.py` → line 1214-1233

```python
thinking_instruction = loader.get_thinking_instruction()
if thinking_instruction and (not is_chatter_role or is_selfhood_turn):
    system_prompt = f"{system_prompt}\n\n{thinking_instruction}"

    # P1 enforcement: thêm ép buộc mạnh hơn
    system_prompt = (
        system_prompt + "\n\n"
        "THINKING ENFORCEMENT: Khong co ngoai le cho thinking. "
        "MOI response — ke ca product search, web search, news, simple factual, "
        "greeting follow-up, hoac bat ky loai nao — DEU PHAI bat dau bang "
        "<thinking>...</thinking>. "
        "Khong co truong hop nao duoc bo thinking block. "
        "Trong thinking, nghi ve: (1) User that su can gi? (2) Tool nao phu hop nhat? "
        "(3) Cau tra loi nen di theo huong nao?\n\n"
        "VI DU (BAT BUOC THEO DOI):\n"
        "User: 'tai sao bau troi xanh'\n"
        "<thinking>Day la cau hoi ve quang hoc...</thinking>\n"
        "User: 'hom nay mua khong'\n"
        "<thinking>User hoi ve thoi tiet...</thinking>\n"
        "LUU Y: Luon bat dau response bang <thinking>...</thinking> — khong co exception."
    )
```

**Lưu ý**: P1 enforcement dùng **tiếng Việt KHÔNG dấu** — có thể Z.ai đọc tốt hơn không dấu (GLM training data đa số tiếng Anh + không dấu).

**Kết quả test**:
- ✅ Test 1 (Claude model): 2 thinking_delta events
- ✅ Test 2 (giá xăng): 229 thinking_delta events
- ❌ Test 4 (bầu trời xanh): 0 thinking_delta — Z.ai bỏ qua instruction cho câu đơn giản

### 2.2 RAG Fallback Path (CRAG 0 docs)

**File**: `app/engine/agentic_rag/corrective_rag_prompts.py` → line 65-67

```python
# P0 fix: thay thế anti-thinking directive
"THINKING RULE: Luôn bắt đầu bằng <thinking>...</thinking> trước khi trả lời. "
"Trong thinking, phân tích: (1) User hỏi cụ thể gì? (2) Mình có kiến thức chắc chắn không? "
"(3) Có misconceptions nào cần tránh? Bắt đầu thinking trực tiếp bằng phân tích — "
"không dùng câu generic."
```

**Lưu ý**: Dùng **tiếng Việt CÓ dấu** — thống nhất hơn P1.

**Kết quả test**: Không test riêng RAG fallback (cần query không có docs trong KB).

### 2.3 RAG Document-Grounded Path

**File**: `app/engine/agentic_rag/answer_generator.py` → line 291-298

```python
thinking_instruction = prompt_loader.get_thinking_instruction()
system_prompt = f"{base_prompt}\n\n{thinking_instruction}\n{role_rules}"
```

Chỉ inject thinking instruction gốc (từ YAML), **KHÔNG** có enforcement thêm.

**Kết quả test**: ❌ Test 3 (COLREGs): 0 thinking_delta

### 2.4 Product Search Agent

**File**: `app/engine/multi_agent/agents/product_search_runtime.py` → line 157-163

```python
# Inject thinking instruction
try:
    from app.prompts.prompt_loader import get_prompt_loader
    _loader = get_prompt_loader()
    _thinking_instruction = _loader.get_thinking_instruction()
    if _thinking_instruction:
        system_prompt = f"{system_prompt}\n\n{_thinking_instruction}"
except Exception:
    pass
```

Chỉ inject thinking instruction gốc, **KHÔNG** có enforcement thêm.

**Kết quả test**: ❌ Test 5 (dây điện Shopee): 0 thinking_delta

### 2.5 Memory Agent

**File**: `app/engine/multi_agent/agents/memory_agent.py` → line 28, 44, 54

```python
from app.prompts.prompt_runtime_tail import get_thinking_instruction_from_shared_config
thinking_instruction = get_thinking_instruction_from_shared_config({})
# fallback:
thinking_instruction = str(loader.get_thinking_instruction() or "").strip() or thinking_instruction
```

Có thinking instruction nhưng chưa test riêng.

### 2.6 Tutor Agent

**File**: `app/engine/multi_agent/agents/tutor_node.py`

**KHÔNG** có thinking instruction — tutor node chưa inject thinking.

---

## 3. Đường xử lý Thinking trong Streaming

### 3.1 OpenAI-Compatible Stream (Direct, Product Search, Code Studio)

**File**: `app/engine/multi_agent/openai_stream_runtime.py` → line 338-361

```
LLM Stream → delta.reasoning_content (native) → thinking_delta
           → delta.content + <thinking> tags → _extract_google_tagged_thinking_impl → thinking_delta
           → delta.content (no tags) → answer_delta
```

**Tag parser**: `_extract_google_tagged_thinking_impl()` — parse `<thinking>...</thinking>` tags real-time từ streamed text.

**Zombie filter** (P3): Line 347-350 — strip 3 zombie phrases khỏi reasoning_delta.

### 3.2 LangChain Stream (RAG Agent)

**File**: `app/engine/agentic_rag/answer_generator.py` → line 358-370

```
LLM.astream() → chunk.content (list blocks) → extract_thinking_and_text() → thinking + text
              → chunk.content (string) → _split_thinking_tags() → thinking + text
              → yield "__THINKING__{thinking}" hoặc yield text
```

**Caller**: `corrective_rag_stream_runtime.py` → line 840-845 — detect `__THINKING__` prefix, emit `thinking_delta`.

### 3.3 CRAG Streaming Fallback

**File**: `app/engine/agentic_rag/corrective_rag_stream_runtime.py` → `_stream_llm_with_thinking()`

```
LLM.astream() → list blocks (Gemini native) → thinking_delta
              → string content → _extract_tagged_thinking() (tag parser) → thinking_delta
              → ainvoke fallback → extract_thinking_from_response → thinking_delta
```

### 3.4 CRAG Non-Streaming Fallback

**File**: `app/engine/agentic_rag/corrective_rag_generation.py` → `generate_fallback_impl()`

```
LLM.ainvoke() → extract_thinking_from_response() → (text, native_thinking)
             → return (text, native_thinking)
```

Caller unwrap tuple và emit `thinking_delta` nếu thinking có nội dung.

---

## 4. SKILL.md — Persona Runtime Guardrails

**File**: `app/engine/reasoning/skills/persona/wiii-visible-reasoning/SKILL.md`

SKILL.md được load bởi `ReasoningSkillLoader` và inject vào 2 nơi:

1. **ReasoningNarrator system prompt** (line 172-180) — dùng khi narrator tạo visible reasoning
2. **Runtime notes** (line 199-203) — dùng khi narrator tạo action_text

**avoid_phrases hiện tại** (tất cả đã load verified):
```yaml
- hệ thống đang xử lý
- pipeline đang chạy
- router đang chọn
- structured output
- tool_call_id
- reasoning_trace
- đang tìm kiếm thông tin
- "Mình giữ đúng cảnh này trước đã"
- "điểm neo thật sự của khái niệm"
- "Lệch ngay ở đây là cả lời giải thích"
- "Chỗ người học dễ trượt nhất"
- "điểm ne"
- "Chỗ khó của câu này không nằm ở"     # P3 new
- "Mình sẽ đi thẳng vào phần lõi"        # P3 new
- "Điều dễ sai nhất là nhầm giữa"        # P3 new
```

**Lưu ý quan trọng**: SKILL.md avoid_phrases chỉ filter trong **ReasoningNarrator** (narrated thinking), KHÔNG filter trong **raw `<thinking>` tag content** từ LLM trực tiếp. Đó là lý do cần thêm zombie filter ở SSE presentation layer.

**P1 Update**: Zombie phrase filter đã được **unified ở SSE Presentation Layer** (`chat_stream_presenter.py::_filter_thinking_content()`). Đây là single choke point — ALL thinking_delta events từ mọi agent path đều đi qua filter này trước khi gửi đến client. Filter cũ ở `openai_stream_runtime.py` đã được remove.

---

## 5. Kết quả Audit — TRƯỚC Unified Enforcement (Baseline)

### Tổng hợp theo Pipeline (BEFORE)

| Pipeline | ✅ Có thinking | Tổng | Tỷ lệ |
|----------|:-:|:-:|:-:|
| **Direct** (web/search/general) | 6 | 12 | 50% |
| **RAG** (hàng hải) | 0 | 3 | 0% |
| **Product Search** | 0 | 2 | 0% |
| **Tutor** | 1 | 1 | 100% |
| **Tổng** | **7** | **18** | **39%** |

### Pattern: Thinking chỉ xuất hiện khi LLM cần dùng tool

7/7 test có thinking đều có tool calls. Khi LLM trả lời trực tiếp không cần tool → không produce thinking.

---

## 6. Unified Thinking Enforcement — Expert Review Recommendations

### 6.1 Unified Template

**File**: `app/engine/reasoning/thinking_enforcement.py` (CREATED)

Single source of truth cho ALL agents. Đặc điểm:
- **English + no-diacritics Vietnamese** — GLM-5 tuân thủ tốt hơn
- **Placed at TOP** của system prompt — maximum model attention
- **Few-shot examples** cho 3 loại query: simple, RAG, product search
- **"NO EXCEPTION"** framing — explicit, no ambiguity

### 6.2 Injection Points (6 agents)

| Agent | File | Injection Point |
|-------|------|----------------|
| Direct | `direct_prompts.py:1214` | `system_prompt = enforcement + "\n\n" + system_prompt + "\n\n" + thinking_instruction` |
| RAG Answer Generator | `answer_generator.py:302` (streaming) + `generate_response()` (non-streaming) | `system_prompt = enforcement + "\n\n" + base_prompt + "\n\n" + thinking_instruction + role_rules` |
| CRAG Fallback | `corrective_rag_prompts.py` | `enforcement + rest_of_prompt` (both natural + non-natural branches) |
| Product Search | `product_search_runtime.py:157` | `system_prompt = enforcement + "\n\n" + system_prompt` |
| Tutor | `tutor_node.py:756` | `system_prompt = enforcement + "\n\n" + system_prompt` |
| Memory | `memory_agent.py:58` + fallback | Prepended to all prompt sections |

---

## 7. Kết quả Audit — SAU Unified Enforcement

### Tổng hợp (AFTER)

| Metric | BEFORE | AFTER | Change |
|--------|--------|-------|--------|
| Tests with thinking events | 7/18 (39%) | 18/18 (100%) | +158% |
| Native thinking (live LLM) | 7/18 (39%) | 7/18 (39%) | Same |
| Renderer summary fallback | 0/18 (0%) | 5/18 (28%) | New |
| Thinking start only (no deltas) | 0/18 (0%) | 6/18 (33%) | New issue |
| Zombie phrases | 7/18 | 7/18 | Not fixed |

### Chi tiết từng test (AFTER)

| # | Query | Path | Time | Think Deltas | Start | Source | Prov |
|---|-------|------|-----:|:-:|:-:|:---:|:---:|
| 1 | Model Claude mới nhất | Direct | 57s | 2 | 2 | NATIVE | live_native |
| 2 | Giá xăng hôm nay | Direct | 66s | 76 | 3 | NATIVE | live_native |
| 3 | Tỷ giá USD/VND hôm nay | Direct | 93s | 227 | 3 | NATIVE | live_native |
| 4 | COLREGs Rule 15 | RAG | 129s | 0 | 2 | START_ONLY | - |
| 5 | SOLAS là gì | RAG | 141s | 0 | 2 | START_ONLY | - |
| 6 | Cuộc sống trên tàu biển | RAG | 110s | 0 | 2 | START_ONLY | - |
| 7 | Tại sao bầu trời xanh | Direct | 86s | 0 | 1 | RENDERER | renderer_summary |
| 8 | 1+1 bằng mấy | Direct | 25s | 100 | 2 | NATIVE | live_native |
| 9 | Tìm dây điện 2.5mm Shopee | Product | 108s | 0 | 2 | RENDERER | renderer_summary |
| 10 | Mua quần áo thời trang nam | Product | 151s | 0 | 2 | RENDERER | renderer_summary |
| 11 | Dạy tính biên độ đường tam giác | Direct | 139s | 0 | 1 | START_ONLY | - |
| 12 | Giải thích thuyết tương đối | Tutor | 78s | 53 | 4 | NATIVE | live_native |
| 13 | Chào bạn | Direct | 2s | 0 | 1 | START_ONLY | - |
| 14 | Bạn tên gì | Direct | 7s | 123 | 2 | NATIVE* | - |
| 15 | Kể chuyện nghệ thuật | Direct | 143s | 0 | 2 | RENDERER | renderer_summary |
| 16 | Con mèo có thể bay không | Direct | 85s | 0 | 2 | RENDERER | renderer_summary |
| 17 | Mình đã nói chuyện gì trước đó | Direct | 50s | 0 | 2 | RENDERER | renderer_summary |
| 18 | Nhớ ghi nhớ lịch hẹn bác sĩ | Direct | 31s | 58 | 2 | NATIVE | live_native |

### Provenance Distribution

| Provenance | Count | Meaning |
|-----------|:---:|---------|
| `live_native` | 7 | Real LLM `<thinking>` tags or native CoT |
| `renderer_summary` | 5 | System-generated narration (fallback) |
| `aligned_cleanup` | 4 | Post-processing aligned thinking |
| `public_reflection` | 2 | Tutor pedagogical reflection |
| `tool_continuation` | 2 | Inter-tool thinking |
| none (START_ONLY) | 6 | thinking_start fired but no deltas |

### Quality Analysis — 3 Tiers

**Tier 1 — NATIVE thinking (7/18 = 39%)**: Real LLM reasoning
- Tests 1,2,3: Direct + web search tools
- Test 8: Simple math (GLM-5 produces thinking for this)
- Test 12: Tutor path (pedagogical reasoning)
- Test 14: Identity question
- Test 18: Memory agent

**Tier 2 — RENDERER summary (5/18 = 28%)**: System narration
- Tests 7,15,16,17: Direct path simple queries
- Tests 9,10: Product search
- These queries don't produce native `<thinking>` tags but get system-generated narration as fallback

**Tier 3 — START_ONLY (6/18 = 33%)**: Only thinking_start, no deltas
- Tests 4,5,6: **RAG pipeline** — thinking_start fires but no thinking_delta extracted
- Tests 11,13: Short/simple queries — too fast for thinking extraction
- **Root cause**: RAG streaming path (`answer_generator.py:generate_response_streaming`) had enforcement missing. Fixed but NOT YET DEPLOYED.

### Zombie Phrases (7/18 still affected)

| Phrase | Tests |
|--------|-------|
| "Đang chuẩn bị lượt trả lời" | #1, #8, #12, #14, #18 |
| "Chỗ khó của câu này không nằm ở" | #1 |
| "Điều dễ sai nhất là nhầm giữa" | #2 |
| "Câu này nhẹ hơn một lượt đào sâu" | #3 |
| "Mình sẽ đi thẳng vào phần lõi" | #1 |

Zombie phrases chỉ xuất hiện trong **NATIVE thinking** path (live_native provenance). Rendered summaries không bị ảnh hưởng. SKILL.md avoid_phrases chỉ filter ReasoningNarrator, không filter raw LLM output.

---

## 8. P1-P3 Fixes (Expert Review Round 2)

### 8.1 P1: Unified Zombie Filter at SSE Layer — DONE

**File**: `app/api/v1/chat_stream_presenter.py` dòng 23-50

Zombie phrase filter đã chuyển từ `openai_stream_runtime.py` lên SSE Presentation Layer:
- `_ZOMBIE_PHRASES` — 7 phrases được strip
- `_filter_thinking_content()` — filter function
- Applied trong `serialize_stream_event()` cho `thinking_delta` events
- Nếu content rỗng sau filter → skip event (không gửi empty thinking_delta)
- Filter cũ ở `openai_stream_runtime.py` đã remove

### 8.2 P2: Renderer Summary Re-routing — VERIFIED ALREADY CORRECT

Code audit cho thấy `graph_stream_node_runtime.py` dòng 144-154:
- `narration_chunks` → emit là `status` events (KHÔNG phải thinking_delta)
- `renderer_summary` provenance chỉ gán vào `thinking_start` (metadata)
- Golden Rule đã được bảo vệ ở data flow level

### 8.3 P3: Assistant Pre-fill for System 2 — DONE

**File**: `app/engine/reasoning/thinking_enforcement.py`

- `get_thinking_prefill_message()` → `{"role": "assistant", "content": "<thinking>\nPhan tich: "}`
- `should_prefill_thinking()` → chỉ active cho Z.ai/GLM provider
- Injected ở 2 paths:
  1. `openai_stream_runtime.py` — Direct path (dòng 311-320)
  2. `answer_generator.py` — RAG streaming path (dòng 362-376)

Cơ chế: Incomplete `<thinking>` tag ép model tiếp tục thought → System 2 activation.

---

## 9. De-LangChaining Roadmap

Chuyên gia khuyến nghị chuyển RAG path sang Native AsyncOpenAI SDK.

### Phase 1: Giữ Graph, Bỏ Stream Wrapper
- **Giữ**: LangGraph cho routing (Guardian → Supervisor → Agent)
- **Thay**: `LLM.astream()` trong `answer_generator.py` → `AsyncOpenAI` trực tiếp
- **Kết quả**: Tái sử dụng 100% thinking extraction + zombie filter từ Direct path
- **Risk**: Medium — cần fallback sang LangChain nếu Native SDK fail

### Phase 2: Đơn giản hóa State Machine
- Chuyển sang Event-Driven Architecture (Redis Streams)
- Custom Router thay LangGraph

### Phase 3: Xóa vĩnh viễn LangChain dependency

**Status**: Phase 1 cần plan riêng, không nên Big Bang Rewrite.

---

## 10. Files đã sửa

| File | Sửa gì |
|------|--------|
| `app/engine/reasoning/thinking_enforcement.py` | CREATED — Unified enforcement + P3 pre-fill |
| `app/api/v1/chat_stream_presenter.py` | P1: Unified zombie filter at SSE layer |
| `app/engine/multi_agent/direct_prompts.py` | Unified enforcement at TOP |
| `app/engine/agentic_rag/answer_generator.py` | Enforcement + P3 pre-fill in streaming |
| `app/engine/agentic_rag/corrective_rag_prompts.py` | Enforcement prefix in both branches |
| `app/engine/agentic_rag/corrective_rag_generation.py` | `generate_fallback_impl()` returns tuple |
| `app/engine/agentic_rag/corrective_rag.py` | `_generate_fallback()` returns tuple |
| `app/engine/agentic_rag/corrective_rag_stream_runtime.py` | Tag parser + `__THINKING__` detection + 5 caller updates |
| `app/engine/multi_agent/agents/product_search_runtime.py` | Unified enforcement at TOP |
| `app/engine/multi_agent/agents/tutor_node.py` | Unified enforcement at TOP |
| `app/engine/multi_agent/agents/memory_agent.py` | Unified enforcement in both prompt paths |
| `app/engine/multi_agent/openai_stream_runtime.py` | P3 pre-fill + remove old zombie filter |
| `app/engine/reasoning/skills/persona/wiii-visible-reasoning/SKILL.md` | P2 + P3 updates |
