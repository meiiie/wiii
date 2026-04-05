# Thinking Architecture Direction

Date: 2026-03-30
Owner: Codex LEADER

## Why This Matters

Wiii is now past the phase where the main issue is:

- god files
- cycle-heavy architecture
- public-thinking producer leaks

Those were important blockers and have been cleaned enough to expose the real problem:

**thinking quality is now limited by architecture, not only by prompt wording.**

If we keep patching `rag`, `tutor`, `memory`, and `direct` with lane-local strings, the system will become:

- inconsistent
- hard to scale
- hard to test
- easy to regress

So from this point on, thinking should be built as a **first-class subsystem**, not as ad-hoc text glued inside agent nodes.

## Reading The Expert Feedback

The expert feedback is directionally excellent, especially on:

1. `P0 before P1`
2. `thinking is not answer draft`
3. `thinking must show strategy, not just procedure`
4. `high-end 2026 thinking must include self-correction`

However, some parts need refinement for Wiii.

## What I Agree With

### 1. Public thinking must never be raw system exhaust

This is absolutely correct.

Wiii gray rail must never directly expose:

- raw telemetry
- raw JSON/tool internals
- hidden/private chain-of-thought
- answer draft prose
- system rules

### 2. Thinking quality must move from procedural to strategic

Correct.

The current progression is:

- Level 1: performative answer-in-disguise
- Level 2: procedural but safe
- Level 3: strategic, context-aware, self-calibrating

This is the right rubric.

### 3. Cognitive headers are useful

Correct.

Headers should behave like cognitive labels, not conversational text.

Good:

- `Phân tích tín hiệu cá nhân`
- `Đối chiếu nguồn`
- `Chọn chiến lược giải thích`
- `Rà soát xung đột dữ liệu`

Bad:

- `Đang nghĩ giúp Nam...`
- `Mình đang trả lời Nam đây...`

## What I Would Refine

### 1. “Third-person absolute” is too rigid

The expert note says thinking should always acknowledge the user in third person.

That is useful as a guardrail, but too rigid as a final law.

For Wiii, the better rule is:

- **never speak to the user inside thinking**
- **never perform the answer inside thinking**
- **it is okay for the inner voice to use first-person self-regulation**

Allowed:

- `Nam đang bị chạm đúng chỗ đau rồi.`
- `Mình mà khuyên ngay lúc này thì hỏng nhịp.`
- `Khoan đã, nếu đi thẳng vào lý lẽ thì sẽ lạnh quá.`

Not allowed:

- `Đừng buồn nhé Nam...`
- `Để mình an ủi Nam ngay...`
- `Nam cứ yên tâm nhé...`

So the real rule is not “third-person absolute”.

The real rule is:

**no second-person address, no answer speech-act, no audience performance.**

### 2. “Memory and RAG must be cold” is too binary

That advice is safe, but too blunt for Wiii.

The better distinction is not:

- memory/rag = cold
- direct/tutor = warm

The better distinction is:

- **data operation layer** = restrained, precise
- **response strategy layer** = can carry persona

For example:

In memory lane, public thinking should not say:

- `Đang ghi row vào memory table`

But it also does not need to sound like an enterprise database log.

Instead it can say:

- `Tên riêng này nên trở thành điểm neo mới cho cách xưng hô ở những lượt sau.`

That is still user-safe, but it has Wiii’s soul.

Same for RAG:

Internal truth:

- source A outdated
- source B newer
- confidence conflict

Public thinking:

- `Có hai nguồn chạm cùng một ý, nhưng một bản cũ hơn nên mình cần bám vào mốc mới hơn.`

That is not raw telemetry, but also not cold robot speak.

## The Real Design Principle

Wiii should not copy Claude exactly.

Wiii should implement:

**Character-Driven Public Monologue**

Definition:

- public
- curated
- strategic
- lane-aware
- persona-consistent
- non-performative

This means Wiii’s thinking should feel like:

- a real inner monologue
- but one that has been cleaned for user-facing display

Not raw hidden CoT.
Not system logs.
Not answer draft.

## The Professional Architecture

## Core Principle

**Agents should not directly author final public-thinking prose.**

They should emit semantic reasoning beats.

A centralized thinking subsystem should render those beats into public thinking.

That is the difference between:

- patchwork system
- extensible professional system

## Proposed Layers

### Layer 1. Thinking Beat Contract

Create a contract such as:

- `ThinkingBeat`
- `ThinkingHeader`
- `ThinkingMode`
- `ThinkingRisk`
- `ThinkingBeatKind`

Suggested beat kinds:

- `observe`
- `interpret`
- `doubt`
- `decision`
- `plan`
- `conflict`
- `source_choice`
- `response_strategy`

Suggested fields:

- `lane`
- `phase`
- `kind`
- `subject`
- `claim`
- `risk`
- `uncertainty`
- `strategy`
- `visibility`
- `tone_mode`

This is the single most important structural move.

### Layer 2. Thinking Policy Router

Introduce a central router that decides **how public thinking should sound**.

Not by one giant prompt, but by policy:

- lane
- task type
- emotional intensity
- data sensitivity
- tool usage
- ambiguity/conflict level

Suggested modes:

- `technical_restrained`
- `analytical_companion`
- `instructional_companion`
- `relational_companion`

### Layer 3. Thinking Renderer

A renderer converts semantic beats into prose with Wiii’s voice.

This renderer should handle:

- tone
- rhythm
- self-correction insertion
- third-person subject reference
- anti-answer-draft guardrails

This is where we can inject persona safely without polluting the agent logic.

### Layer 4. Public Thinking Authority

Keep the authority rule already established:

- stream `thinking_delta` is canonical public thinking
- final `thinking_content` is only an aggregate of what was visibly streamed

No separate hidden final override.

## Mode Matrix

## 1. Memory Lane

Target style:

- socially aware
- strategic
- relational but not performative

Good:

- `Nam vừa chủ động xưng tên, nên đây không chỉ là dữ kiện định danh mà là tín hiệu muốn những lượt sau cá nhân hơn.`
- `Khoan đã, nếu đáp quá thân ngay lúc này thì sẽ thành vồ vập giả.`
- `Tên này nên trở thành điểm neo mới cho cách xưng hô.`

## 2. Tutor Lane

Target style:

- instructional designer inner voice
- not lecture prose
- not answer draft

Good:

- `Điểm dễ lệch ở đây là người học hay nhầm vai trò giữa tàu nhường đường và tàu giữ nguyên hướng.`
- `Nếu mở bằng định nghĩa khô quá thì user sẽ nhớ kém. Tốt hơn là dựng một tình huống cắt mặt trước.`
- `Khoan đã, ví dụ này dễ gây hiểu sai nếu không chốt điều kiện 'có nguy cơ đâm va'.`

## 3. RAG Lane

Target style:

- evidence-aware
- cautious
- source-sensitive
- slightly more restrained than companion chat

Good:

- `Có hai nguồn chạm cùng một ý, nhưng một bản cũ hơn nên mình nên bám vào mốc mới hơn.`
- `Nguồn hiện tại chưa đủ chắc để khẳng định mạnh tay.`
- `Khoan đã, đoạn này nghe hợp lý nhưng chưa thấy mốc dẫn đủ tin cậy.`

## 4. Direct Emotional / Companion Lane

Target style:

- warm
- human
- socially intelligent
- emotionally tuned

Good:

- `Chết thật, Nam đang bị sếp quật nặng rồi.`
- `Giờ mà lôi lý lẽ ra ngay thì dở hơi lắm.`
- `Tốt nhất là để Nam xả hết cục nghẹn này ra trước đã.`

Important:

This lane can be warmer and more human than the others.

But still must not become direct answer speech.

## Professional Guardrails

## Rule 1. No Answer Draft In Thinking

Never allow:

- consolation speech
- explanation speech
- direct coaching speech
- final response sentence starters

inside gray rail.

## Rule 2. No Raw Telemetry In Thinking

Never show:

- confidence score
- complexity label
- internal KB markers
- query rewrite raw text
- tool internals

## Rule 3. Self-Correction Is Conditional

Do not inject `Khoan đã` everywhere.

Only use epistemic doubt when there is:

- ambiguity
- emotional risk
- source conflict
- pedagogical trap
- social calibration risk

Otherwise the thinking becomes fake-theatrical.

## Rule 4. Header != Body

Header:

- cognitive label only

Body:

- reasoning beat content

These should not collapse into one another.

## Why The Current Patch Is Not The Final Architecture

The current memory patch is useful, but still transitional.

It proves that better public thinking is possible.

But if we keep doing this by embedding more handcrafted prose inside:

- `memory_agent.py`
- `tutor_node.py`
- `rag_node.py`

then the system will drift into local heuristics and duplicated logic.

That is not the professional end-state.

## What To Build Next

### Phase A. Extract Thinking Contracts

Create a dedicated module, for example:

- `app/engine/reasoning/public_thinking_contracts.py`
- `app/engine/reasoning/public_thinking_policy.py`
- `app/engine/reasoning/public_thinking_renderer.py`

### Phase B. Migrate Memory Lane First

Memory is the best pilot lane because:

- highly visible
- easy to compare before/after
- exposes social calibration clearly

### Phase C. Apply To Tutor Lane

Tutor is the highest ROI lane after memory because it still leaks “lecture prose” into gray rail.

### Phase D. Apply To RAG Lane

RAG should become evidence-aware, not telemetry-heavy.

## Recommended Product Standard

Wiii should target this standard:

- **Claude-level structure**
- **Wiii-level soul**

Meaning:

- structured enough to remain safe and stable
- human enough to feel like a living companion

That is the product gap Wiii can occupy uniquely.

## Final Position

I agree with the expert’s direction, but the best professional implementation is:

not:

- cold robot thinking everywhere

and not:

- raw casual inner monologue everywhere

but:

**a centralized, lane-aware, character-driven public-thinking system**

That is the architecture that scales.

