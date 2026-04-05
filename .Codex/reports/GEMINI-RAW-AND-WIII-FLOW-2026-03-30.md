# Gemini Raw Thinking And Wiii Flow - 2026-03-30

## Scope

- Re-read raw Gemini thought artifacts from standalone SDK probes
- Reconstruct current Wiii chat flow from code
- Compare the user's remembered flow with the actual backend/runtime flow
- Cross-check design direction against official vendor docs available on 2026-03-30

## Raw Gemini Probe Truth

Standalone probe script:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_gemini_raw_thinking.py`

Key implementation anchors:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_gemini_raw_thinking.py:177`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_gemini_raw_thinking.py:179`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_gemini_raw_thinking.py:287`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\scripts\probe_gemini_raw_thinking.py:296`

What the script does:

- calls Google GenAI SDK directly
- no Wiii PromptLoader
- no character card
- no supervisor
- no RAG/tool layer
- `include_thoughts=True`
- configurable `thinking_level`

### Model availability on 2026-03-30

Attempting `gemini-3.1-flash` returned `404 NOT_FOUND` for this local key on `generateContent`.

Successful raw probes used:

- `gemini-3.1-flash-lite-preview`
- `gemini-3-flash-preview`

Artifacts:

- `E:\Sach\Sua\AI_v1\.Codex\reports\GEMINI-RAW-THINKING-2026-03-30-120310.md`
- `E:\Sach\Sua\AI_v1\.Codex\reports\GEMINI-RAW-THINKING-2026-03-30-120310.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\GEMINI-RAW-THINKING-2026-03-30-121806.md`
- `E:\Sach\Sua\AI_v1\.Codex\reports\GEMINI-RAW-THINKING-2026-03-30-121806.json`

### What the raw model shows

Observed behavior:

- 1 thought block + 1 answer block per prompt
- long planning-oriented internal reasoning
- model-owned flow, not renderer-authored flow
- neutral vendor voice, not Wiii voice
- can be temporally wrong for current-events prompts when no retrieval/tools are used

Important example:

- for `Phân tích giá dầu hôm nay`, the plain model answered as if "today" were in May 2024

This is the clearest proof that raw model thought is useful as a style reference, but cannot be surfaced directly as Wiii public thinking.

## Official Reference Points Used

Primary sources:

- Anthropic Extended Thinking:
  - https://platform.claude.com/docs/en/build-with-claude/extended-thinking
- Anthropic Prompting Best Practices:
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
- Google Gemini Thinking:
  - https://ai.google.dev/gemini-api/docs/thinking

Practical conclusions from those docs:

- modern interval/interleaved thinking is model-owned more than template-authored
- tool interleaving should preserve reasoning continuity across tool use
- highly prescriptive step-by-step forcing is usually weaker than strong high-level framing
- thought traces are useful for adaptive reasoning, but product systems still need output contracts and safety curation

## Current Wiii Flow: Backend Truth

### 1. Transport entry

Sync:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\chat.py:101`

Stream:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\chat_stream.py:104`

These API modules are transport shells:

- auth
- rate limit
- canonicalize request fields from auth context
- hand off to service layer

### 2. Authoritative business flow

The contract file says the canonical shape is:

`request -> session -> validation -> context -> execution -> output -> post-response scheduling -> continuity update`

Source:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\REQUEST_FLOW_CONTRACT.md`

### 3. Orchestrator

Main owner:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator.py:134`

Key methods:

- `prepare_turn(...)` at `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator.py:385`
- `process(...)` at `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator.py:412`

This is the true live-turn backbone:

1. normalize thread/session
2. resolve org/domain scope
3. validate input
4. build request context
5. run multi-agent or fallback execution
6. validate/format output
7. schedule persistence + continuity work

### 4. Validation

Owner:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\input_processor.py`

Guard/guardian happens before context-heavy execution:

- `validate(...)`

### 5. Context assembly

Authoritative context builder:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\input_processor.py:231`

This stage assembles:

- conversation history
- semantic memory
- user facts
- mood hint
- LMS/page/host context
- org-scoped context

### 6. Character and soul loading

This is the subtle but important correction to the remembered flow:

Wiii does not globally "preload one universal character prompt at web entry" and then keep using that same assembled prompt for the whole runtime.

The living identity is compiled inside backend prompt assembly and execution surfaces.

Key anchors:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py:142`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\character\character_card.py:246`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\living_thinking_context.py:61`

What really happens:

- request context is built
- prompt/runtime overlays are assembled when the execution layer needs them
- Wiii identity, soul, living state, mood hint, and runtime card are injected there

So the phrase "load sẵn character chung ngay khi vào web" is only partially true from a UX perspective.

From backend truth:

- the browser can load UI/session/auth state early
- but the authoritative Wiii character prompt is assembled on the backend during execution

### 7. Supervisor

Owner:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py:147`

Key methods:

- `route(...)` at `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py:200`
- `process(...)` at `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\supervisor.py:454`

Important truth:

- routing is LLM-first structured routing
- rule-based logic is now mostly a safety/guardrail fallback
- the supervisor usually chooses one primary lane, not a guaranteed sequence of agent1 then agent2 then agent3

This means the remembered flow:

`supervision -> reason prompt -> phân rã prompt -> agent 1 -> agent 2 -> agent 3`

is directionally understandable, but not fully accurate.

The real shape is closer to:

`supervisor chooses the main lane -> that lane may do internal tool loops / retrieval / follow-up reasoning -> optional synthesis/fallback/parity shaping`

### 8. Execution layer

Execution anchor:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph.py:524`

Public thinking resolution anchors:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_process.py:155`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_stream_runtime.py:250`

Current truth:

- sync answer authority resolves at final graph/process level
- sync thinking authority resolves through public-thinking aggregation
- stream final metadata now also resolves thinking via the same canonical public-thinking path

### 9. Streaming transport

Service coordinator:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_stream_coordinator.py`

Stream event construction anchors:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\stream_utils.py:132`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\stream_utils.py:163`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\stream_utils.py:179`

Live stream transport truth:

- emits `status`
- emits `thinking`
- emits `answer`
- emits `sources`
- emits `metadata`
- emits `done`

But this does not mean Wiii always runs multiple visible agents in sequence.

Usually it means:

- one main routed lane produces most of the user-visible reasoning
- tools/retrieval happen inside that lane
- stream progressively surfaces the journey

### 10. Post-response scheduling

After the visible answer is ready, the orchestrator schedules:

- persistence
- thread view upkeep
- living continuity
- optional LMS insights

This is asynchronous follow-up, not part of the live reasoning loop.

## Where The User's Remembered Flow Is Right

Correct intuition:

- there is a common Wiii identity backbone
- a session/thread is created or normalized
- a protection layer runs before full execution
- LLM-based supervision/routing decides the main handling lane
- tools and retrieval may happen after routing
- thinking can stream before the final answer is fully done
- stream can provide a more professional "in-progress" sense than plain sync JSON

## Where The Remembered Flow Needs Correction

### Not exactly "agent 1 -> agent 2 -> agent 3" by default

Most turns do not pass visibly through several specialist agents in sequence.

More often:

- one primary agent/lane is selected
- that lane performs internal reasoning/tool/retrieval loops
- the graph may still do synthesis/final shaping around it

### Character is not simply preloaded once at web entry

The backend assembles the authoritative living prompt/runtime card during execution.

### Mini-answer is not yet a single clean universal subsystem

The stream can feel like "mini answers" or professional progress cues, but this still depends on lane/event behavior.

It is not yet a perfectly unified, product-level mid-answer authoring layer across all lanes.

## Why This Matters For Thinking

The raw Gemini probe shows:

- the model itself is capable of deep, self-owned thought flow

The Wiii flow audit shows:

- Wiii adds:
  - living identity
  - routing
  - tools
  - retrieval
  - lane contracts
  - stream shaping
  - public-thinking curation

Therefore the real question is not:

- "Can the model think deeply?"

It can.

The real question is:

- "How much of that thought flow should remain model-authored after it passes through Wiii's execution, safety, and soul layers?"

That is the real center of the remaining `thinking` problem.

## Strategic Conclusion

As of 2026-03-30:

1. Wiii no longer mainly suffers from thinking leak/parity chaos.
2. The remaining issue is authorship and quality of public thinking.
3. Raw Gemini thinking proves the vendor model can generate much richer internal flow than our older renderer-authored scaffolds.
4. The right direction is not to remove Wiii structure, but to reduce over-authoring by the system and let model-authored thought substance survive more intact.

## Recommended Next Step

Apply the same `LLM-authored public thought draft` approach now used in tutor-thinking to the remaining high-impact lanes:

1. direct lane
2. analytical follow-up lane
3. visual follow-up within tutor/direct continuity

That is the highest-ROI path toward public thinking that is:

- deeper
- less templated
- more Wiii
- still safe and coherent
