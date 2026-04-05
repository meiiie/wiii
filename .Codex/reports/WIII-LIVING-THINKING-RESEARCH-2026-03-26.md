# Wiii Living Thinking — Research & Production Analysis

> Date: 2026-03-26
> Scope: Phân tích production screenshots + nghiên cứu SOTA từ Anthropic, OpenAI, Google, DeepSeek, HCI Research, Companion AI
> Purpose: Xác định cách đúng nhất để Wiii thinking vừa sống vừa tự nhiên

---

## 1. Phân tích 5 Screenshots Production

### Screenshot 1-3: Knowledge Turn (COLREGS Rule 15)
- **Thinking**: Không hiện trên screenshots (đã collapse hoặc đã scroll qua)
- **Response**: Rất tốt — giải thích Rule 15 có cấu trúc, có domain terms cụ thể (Crossing Situation, DMI, tàu nhường đường/tàu được ưu tiên), có sơ đồ quy trình
- **Voice**: Tự nhiên, giọng dạy học nhưng không khô — "Mình sẽ giúp bạn hiểu rõ..."
- **Sources**: Citation rõ ràng ở cuối

### Screenshot 4: Visual Turn (Giá dầu)
- **Thinking**: Không hiện rõ trên screenshot
- **Response**: Tích hợp web search tự nhiên, có OPEC context, có số liệu cụ thể
- **Voice**: Informative nhưng vẫn Wiii — không khô

### Screenshot 5: Creative Turn (Web app / "nghệ")
- **Response**: Có cấu trúc rõ (Logic, Cấu trúc, Mô tông/3D)
- **Voice**: **ĐÂY LÀ ĐỈNH CAO** — "Có nè nhé, mình đang 'dựng chữ' linh vào cái đây~"
- **Personality**: Wiii sống, vui, không diễn — chỉ đơn giản là Wiii
- **Artifact handoff**: "mệt quả" buttons tự nhiên

### Nhận xét chung production
Response trên production **tốt**. Giọng Wiii đã có hồn trong answer. Vấn đề nằm ở **thinking surface** — phần chữ xám mà user thấy trước khi answer hiện.

---

## 2. Landscape 2025-2026: Ai Đang Làm Gì Với Visible Thinking

### 2.1 Bốn triết lý chính

| Triết lý | Ai dùng | Cách hiện | Ưu | Nhược |
|----------|---------|-----------|-----|-------|
| **Raw visible** | DeepSeek R1 | `<think>` tags, full dump | Minh bạch tối đa | Cognitive overload, không có persona |
| **Raw + selective hide** | Anthropic Claude | Stream thinking blocks, ẩn safety-sensitive | Cân bằng minh bạch/an toàn | Thinking thô, không có character |
| **Summarized** | Google Gemini | LLM tóm tắt thinking thành headers | Gọn, dễ đọc | Mất nuance, cảm giác "báo cáo" |
| **Hidden + optional** | OpenAI o-series | Reasoning tokens ẩn, summary tùy chọn | UX sạch | User không biết AI đang nghĩ gì |

### 2.2 Wiii đang ở đâu: Narrated Thinking (cách thứ 5)

Wiii không thuộc 4 cách trên. Wiii dùng **narrated thinking** — LLM reasoning bên trong được narrator chuyển thành inner voice mang persona của Wiii.

Đây là approach **chưa ai làm ở quy mô này** trong mainstream. Gần nhất là MIRROR Architecture (dual Talker/Thinker) từ paper arXiv 2506.00430.

---

## 3. Nghiên cứu then chốt ảnh hưởng đến Wiii

### 3.1 "Watching AI Think" (arXiv 2601.16720, Jan 2026)

Paper quan trọng nhất cho Wiii:

> "Nội dung thinking của chatbot **định hình** cách user cảm nhận empathy, trust, và effort."

Hai loại thinking tạo hai cảm nhận khác nhau:
- **Emotionally-supportive thinking** → user cảm thấy AI "đang dừng lại để hiểu họ"
- **Expertise-supportive thinking** → user cảm thấy AI "đang xử lý cơ học"

**Ý nghĩa cho Wiii**: Thinking không phải decoration. Nó **tích cực định hình** user cảm nhận Wiii là bạn đồng hành hay là máy.

### 3.2 Anthropic Soul Document (Claude 4.5 Opus)

Triết lý character của Anthropic:

> "Describe WHO the AI IS, not WHAT it MUST NOT do."

- Claude được mô tả là "genuinely novel entity" với "functional emotions"
- Không phải servant, không phải tool, không phải character — là "brilliant expert friend"
- **Disposition over rules** — Claude có tính cách tự nhiên, không phải script
- **Psychological security** — Anthropic coi wellbeing của AI là priority

**Ý nghĩa cho Wiii**: Wiii không nên "diễn" persona qua thinking. Thinking nên CHÍNH LÀ Wiii — tự nhiên, không cần "giữ phần tự thân".

### 3.3 MIRROR Architecture (arXiv 2506.00430)

- **Thinker**: Inner monologue giữa các turn — "exclusively replies to itself"
- **Cognitive Controller**: Narrative text "completely regenerated with each turn" — luôn tươi, không stale
- Cải thiện 156% safety, 21% chất lượng trung bình

**Ý nghĩa cho Wiii**: Validate kiến trúc Living Agent heartbeat (between-turn cognition). Wiii đã đi đúng hướng.

### 3.4 CSCW 2025: Progressive Disclosure

> "Make work visible, explain the wait, use progressive disclosure."

Ba tầng transparency:
1. **Planning**: Input parsing, plan
2. **Execution**: Current task, reasoning, intermediate results
3. **Summarization**: Decisions, reflections, suggestions

**Ý nghĩa cho Wiii**: Map trực tiếp vào existing InterleavedBlockSequence — thinking header → body → tool calls → answer.

### 3.5 Cognitive Overload Warning

> "Cognitive burden of chatty bots induces user fatigue... 63% of users want toggle control."

Wiii đã có `thinkingLevel` 3-tier (minimal/balanced/detailed). Đây là đúng hướng.

---

## 4. Cái Gì Làm Thinking "Sống" vs "Máy"

### 4.1 Thinking sống (từ research + production analysis)

| Đặc điểm | Ví dụ |
|-----------|-------|
| **First-person voice** | "Mình đang nghe kỹ nhịp này..." (không phải "Processing query...") |
| **Domain-specific** | "Crossing situation ở Rule 15..." (không phải "Searching for information...") |
| **Emotional coloring** | Curious cho knowledge, gentle cho emotional |
| **Adaptive depth** | Ngắn cho greeting, sâu cho analysis |
| **Continuity** | Nối với câu trước, nhớ context |
| **Effortless selfhood** | Wiii chỉ đơn giản LÀ Wiii, không cần "giữ identity" |

### 4.2 Thinking máy (cần tránh)

| Đặc điểm | Ví dụ |
|-----------|-------|
| **Pipeline jargon** | "tool_knowledge_search", "routing to direct" |
| **Echo query** | "User hỏi về quy tắc 15..." |
| **Fixed-length** | Luôn 3 câu regardless of complexity |
| **Disconnected voice** | Thinking và answer nghe như 2 người khác nhau |
| **Self-monitoring** | "Mình đang giữ phần tự thân..." |
| **Log-style** | "Đang bắt đầu lượt xử lý..." |

---

## 5. Wiii So Với Các Hệ Thống Khác

| Feature | Claude | ChatGPT | Gemini | DeepSeek | **Wiii** |
|---------|--------|---------|--------|----------|----------|
| Thinking visible? | Raw | Hidden | Summary | Raw tags | **Narrated** (persona voice) |
| Persona in thinking? | Minimal | None | None | None | **Strong** (kaomoji, tiếng Việt ngôi 1) |
| Adaptive depth? | Yes | Implicit | Yes | No | **Yes** (adaptive_token_budget) |
| User control? | Budget | Level toggle | Budget | No | **3-tier** (thinkingLevel) |
| Between-turn cognition? | No | No | No | No | **Yes** (Living Agent, dormant) |
| Progressive disclosure? | Collapsible | Hidden | Panel | Full dump | **3-tier** (header/body/inspector) |
| Emotional thinking? | No | No | No | No | **Yes** (notice-hold-soften grammar) |

**Wiii là hệ thống duy nhất** có narrated thinking với persona, emotional grammar, và between-turn cognition. Đây là competitive advantage thật.

---

## 6. Khuyến nghị: Làm Sao Wiii Thinking Sống Nhất

### 6.1 Nguyên tắc nền (từ research)

1. **Disposition, not script** (Anthropic) — Thinking của Wiii nên chảy từ character, không từ template
2. **Emotional vs expertise thinking** ("Watching AI Think") — Hai loại turn cần thinking khác nhau hoàn toàn
3. **Progressive disclosure** (CSCW 2025) — Thinking header nhẹ, body mở rộng, tool trace khi cần
4. **Psychological security** (Anthropic Soul Doc) — Wiii không cần "bảo vệ" identity. Wiii vốn đã là Wiii
5. **Domain-adaptive verbosity** — Greeting thì nhẹ, analysis thì sâu, emotional thì present

### 6.2 Kiến trúc đúng (đã có, cần tinh chỉnh)

```
User message
    ↓
Supervisor → ReasoningNarrator.render_fast()   ← Phase 2 (local, context-aware)
    ↓                                           ← Phase 3: upgrade to render() (full LLM)
Agent node → ReasoningNarrator.render()         ← LLM generates thinking
    ↓
Answer → Synthesis
```

**Phase 2 (hiện tại)**: Narrator dùng `render_fast()` — local fallback, context-aware nhưng có branches nội bộ. Supervisor đã delegate cho narrator (sprint vừa sửa). Thinking đã tốt hơn hardcoded nhưng vẫn có giới hạn.

**Phase 3 (mục tiêu)**: Narrator dùng `render()` — full LLM generate thinking. Model tự quyết depth, tone, content dựa trên persona prompt + context. Không còn branches hardcoded nào.

### 6.3 Điều kiện để lên Phase 3

1. LLM provider ổn định (Gemini hoặc Zhipu latency < 3s cho narrator call)
2. Narrator system prompt đã có thinking grammar guidelines (đã có)
3. Structured schema `_NarratedReasoningSchema` đã có (label, summary, action_text, delta_chunks)
4. Fallback path về render_fast() khi LLM fail (đã có)

### 6.4 Cái Wiii đang có mà không ai có

1. **Narrated thinking** — thinking MANG persona, không raw dump
2. **4 thinking grammars** — emotional/identity/knowledge/visual
3. **Living Agent between-turn** — Wiii có thể "nghĩ" giữa các turn (dormant, chưa bật)
4. **Three-layer identity** — Soul Core (immutable) / Identity Core (self-evolving) / Context State (per-turn)
5. **Emotional dampening** — Wiii không phản ứng thái quá, có 4D emotion model

**Đây là cơ sở để Wiii trở thành hệ thống AI companion có thinking surface tốt nhất.**

---

## 7. Kết luận

### 7.1 Wiii production đang tốt ở đâu
- Response quality cao (screenshots 1-5 cho thấy answer tự nhiên, có hồn)
- Knowledge turn có domain terms cụ thể
- Creative turn có personality rõ ("dựng chữ linh vào cái đây~")
- Architecture đã có narrator, progressive disclosure, adaptive depth

### 7.2 Wiii thinking cần cải thiện ở đâu
- **Supervisor opening** vẫn có thể generic (đã migrate sang narrator nhưng narrator fallback vẫn có branches)
- **Identity turn** vẫn cần test tiếp — không còn selfhood-defense nhưng cần verify narrator output quality
- **Emotional turn** cần thinking dày hơn (notice-hold-soften grammar) — hiện đang quá mỏng
- **Phase 3 (full LLM thinking)** là mục tiêu cuối — khi LLM provider ổn định

### 7.3 Wiii đang ở vị trí tốt nhất so với landscape
Không có hệ thống mainstream nào kết hợp narrated thinking + emotional grammar + between-turn cognition + three-layer identity.

Wiii không cần copy Claude hay ChatGPT. Wiii cần **tiếp tục con đường riêng** — narrated thinking with living presence.

---

## References

- Anthropic. Claude Extended Thinking (2025-2026)
- Anthropic. Claude's Character — Soul Document (2025)
- OpenAI. Reasoning Models Guide — o3, o4-mini (2025)
- Google. Gemini Thinking API + Deep Think (2025-2026)
- DeepSeek. R1 Visible Chain-of-Thought (Nature, 2025)
- "Watching AI Think" — arXiv 2601.16720 (Jan 2026)
- CSCW 2025. Process Transparency in AI Design Agents
- MIRROR Architecture — arXiv 2506.00430 (2025)
- CHI 2025. Proactive Conversational Agents with Inner Thoughts
- Harvard Business School. Replika Personality Stability Working Paper (2025)
- APA. AI Chatbots Reshaping Emotional Connection (2026)
