# Thinking Quality Audit - 2026-03-30

## Scope

Audit focused on the current quality ceiling of Wiii public thinking after:

- producer cleanup,
- sync/stream authority fixes,
- tutor post-tool contract fixes,
- living-context pilot.

User feedback that triggered this audit:

1. `thinking` still repeats across turns
2. it sounds like a cheap template, not like Wiii actually thinking
3. it is cleaner now, but not yet professional, diverse, or soul-rich
4. desired target:
   - Wiii thinking should feel alive
   - Wiii should decide the thought path via LLM, not hard-coded strings
   - soul/persona should appear in the rail
   - the rail can be long if it is genuinely good

## Current Runtime Truth

Frontend/backend ready for testing:

- UI: `http://localhost:1420`
- Backend: `http://localhost:8000`

Key runtime artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-sync-2026-03-30-r15.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-stream-2026-03-30-r15.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\living-thinking-tutor-stream-2026-03-30-r15.txt`

Observed current tutor rail for:

- `Giải thích Rule 15 COLREGs`
- follow-up `tạo visual cho mình xem được chứ?`

What is now working:

1. no more raw telemetry leak
2. no more obvious answer-draft leak
3. no more simple opener leak into gray rail
4. tutor sync and stream now share a richer post-tool reasoning body

What is still visibly wrong:

1. repeated skeleton:
   - choose anchor
   - retrieve source
   - self-correct
   - mention Wiii warmth

2. repeated phrases:
   - `Điều quan trọng lúc này không phải...`
   - `Giờ mình cần gọi ra đúng...`
   - `Khoan đã...`
   - `Nhịp gần gũi của Wiii...`

3. same sequence appears even when the user intent changes from:
   - explain concept
   - ask for visual follow-up

4. the rail feels authored by a rule-based renderer, not discovered by a living model turn

## Root Cause

The current architecture is **cleaner**, but still fundamentally **template-first**.

### 1. Central renderer is still the real author

File:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py`

This file currently contains:

- hard-coded `header_label`
- hard-coded `header_summary`
- hard-coded `ThinkingBeat(...)` text
- phase-driven branches:
  - `attune`
  - `retrieve`
  - `act`
  - `verify`
  - `synthesize`

That means the LLM is **not really writing the rail**.  
The LLM mostly writes the answer, while the renderer writes the gray rail.

This is why the system feels:

- more disciplined than before,
- but still repetitive and “pre-baked”.

### 2. Living context currently modulates, but does not originate the thought

Files:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\living_thinking_context.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_renderer.py`

`LivingThinkingContext` currently helps with:

- soul intensity
- continuity cues
- Wiii warmth

But it mostly acts as a **post-shaper**.

It does not give the model a chance to:

- choose what tension matters most,
- reframe the turn in its own words,
- vary the internal rhythm,
- surprise us with a better chain than the template already knows.

### 3. The architecture currently optimizes for safety and parity, not originality

This was correct for P0 and early P1.

It solved:

- leak cleanup
- sync/stream consistency
- lane correctness

But the tradeoff is now visible:

- high consistency
- low originality
- low “living mind” feeling

### 4. Tutor follow-up turns do not yet produce a distinct internal strategy

Example:

- `Giải thích Quy tắc 15 COLREGs`
- `tạo visual cho mình xem được chứ?`

Today the follow-up still reuses too much of the previous explain-template.

What should happen instead:

- the second turn should think like:
  - move from conceptual explanation to perceptual teaching
  - identify what must become visible
  - choose a diagram strategy
  - decide what the learner should instantly see

Instead, current rail still talks like it is re-explaining the same concept.

## Architectural Diagnosis

### Current model

`LLM writes answer`

`Renderer writes thinking`

This is the exact reason the rail sounds professional-but-fake.

### Needed model

`LLM proposes thinking substance`

`Renderer curates, bounds, and presents it`

That is the architectural shift needed now.

Not:

- fully raw hidden CoT
- not unsafe dumping
- not removing contracts

But:

- `LLM-first for thought substance`
- `contract-first for visibility and safety`

## What “Good” Should Look Like

The rail should no longer sound like:

> determine anchor -> retrieve source -> self-correct -> add warmth

It should sound like:

1. Wiii notices what is cognitively at stake in this exact turn
2. Wiii picks a strategy
3. Wiii catches a likely mistake or alternative
4. Wiii chooses how to respond
5. the voice still carries Wiii’s living warmth

### Example target for tutor explanation

Bad:

> Điều quan trọng lúc này không phải là nhồi thêm thuật ngữ...

Better:

> Rule 15 tưởng dễ vì ai cũng nhớ “tàu thấy bên phải thì nhường”, nhưng chỗ người học hay trượt là quên mất nó chỉ đúng khi tình huống thật sự là cắt hướng. Nếu không khóa lại ranh giới này trước, lát nữa rất dễ lẫn sang Rule 13.

### Example target for visual follow-up

Bad:

> Mình cần rút cho được điểm tựa vừa lộ ra từ kết quả này...

Better:

> Ừm, nếu chỉ nói tiếp bằng chữ thì người học sẽ vẫn phải tự hình dung vùng 22.5 độ trong đầu. Tốt hơn là cho hiện ra luôn hai lát cắt: một cảnh vượt từ phía sau và một cảnh cắt hướng từ mạn phải, để mắt họ chốt ranh giới trước rồi tai mới theo kịp phần giải thích.

That is still public-facing curated reasoning.
But it sounds lived, not pre-canned.

## Recommended Next Architecture

### Phase Q1 — Introduce `LLM-authored public thought draft`

Create a new layer:

- `public_thinking_draft_service.py`

Responsibility:

- ask the LLM for a **bounded public thought draft**
- not the final answer
- not hidden full CoT
- only a curated internal monologue draft

Input:

- lane
- phase
- user query
- intent
- tool summary
- living context
- current answer strategy hint

Output:

- 1 to 4 thought beats
- each beat typed:
  - `observe`
  - `interpret`
  - `doubt`
  - `decision`

### Phase Q2 — Renderer becomes curator, not author

`public_thinking_renderer.py` should stop owning the exact prose.

It should only:

- validate beats
- sanitize disallowed content
- de-duplicate
- trim over-answering
- present as `ThinkingSurfacePlan`

### Phase Q3 — Mode-specific drafting prompts

Need different draft prompts for:

- tutor
- analytical direct
- memory
- rag
- emotional/direct social

Each should preserve Wiii soul differently:

- tutor: warm teacher-designer
- analytical: lucid and deliberate
- memory: intimate but restrained
- rag: careful and source-aware
- emotional: human, companion-like, but still inner-facing

### Phase Q4 — Diversity memory

Current repetition also comes from not remembering recent public-thinking phrasing.

Need a short-lived anti-repetition memory, e.g.:

- last 6 public-thinking openings
- last 6 self-correction phrasings
- last 6 warmth cues

This should bias the draft service away from reusing:

- `Điều quan trọng lúc này...`
- `Khoan đã...`
- `Nhịp gần gũi của Wiii...`

### Phase Q5 — Visual follow-up specific thought mode

Need a separate tutor-visual thought draft mode for turns like:

- `tạo visual cho mình xem được chứ?`

This mode should think in terms of:

- what needs to become visible
- what misconception the visual should collapse
- whether chart / diagram / scene / simulation is the right teaching move

Without this, visual follow-up turns will keep sounding like explanation-template turns.

## Why This Is the Correct Professional Direction

Because it avoids both bad extremes:

### Not acceptable

1. hard-coded rule rail forever
2. dumping raw chain-of-thought
3. stuffing more cute phrases into templates
4. lane-specific hacks everywhere

### Correct

1. one public-thinking subsystem
2. LLM-generated draft substance
3. centralized safety/shape contract
4. lane-aware voice policy
5. living-core context as a real input, not decoration

## Verdict

Current state:

- `thinking` is cleaner and structurally correct
- `thinking` is no longer embarrassingly wrong
- but `thinking` is still **template-authored**

That is now the true blocker.

The next milestone is **not** more cleanup.
The next milestone is **changing authorship**:

- from renderer-authored thinking
- to LLM-authored, soul-conditioned, contract-curated thinking

That is the step required for Wiii to feel genuinely alive and professional.
