# Thinking Current Truth - 2026-03-29

## Scope

Checkpoint after:
- runtime secret parity fix
- large-scale refactor cleanup
- direct analytical thinking-mode patch

This note replaces older assumptions gathered while runtime policy and transport parity were still drifting.

## Expert Reference

Reference model for public-thinking behavior:
- Anthropic Extended Thinking: https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking

What is relevant from Claude-style systems:
- thinking can be interleaved with tool use
- visible thinking should feel like one coherent interval timeline, not several unrelated narrators
- answer and thinking are distinct surfaces and should not overwrite each other

## Current Request Flow

For local UI:
- frontend entry: `http://localhost:1420`
- backend entry: `http://localhost:8000`

For sync:
- `/api/v1/chat`
  - auth canonicalization
  - `chat_service.process_message()`
  - `ChatOrchestrator.prepare_turn()`
  - context assembly
  - `ChatOrchestrator._process_with_multi_agent()`
  - `graph.process_with_multi_agent()`
  - final `InternalChatResponse`

For stream:
- `/api/v1/chat/stream/v3`
  - same prepare/context path
  - same multi-agent execution path
  - SSE transport through `generate_stream_v3_events()`
  - event-time presentation via `graph_streaming` stack

Important architectural truth:
- `/api/v1/chat` and `/api/v1/chat/stream/v3` are not two different business pipelines
- they are one business pipeline with two transports

## Authority Model

### Answer Authority

Canonical answer should be:
- final response after graph execution

Stream may show answer incrementally, but persisted/final truth must remain the final response.

### Thinking Authority

Canonical public thinking should be:
- sanitized public `thinking_delta` fragments that were actually surfaced to the user

Final `thinking_content` should be:
- the aggregate of those already-surfaced fragments
- not a second independently-generated narrator

## What Is Verified Right Now

### 1. Localhost FE

`http://localhost:1420` is the correct local origin for browser flows and Google login redirect behavior.

UI currently shows the login screen correctly on localhost.

Screenshot:
- `E:\Sach\Sua\AI_v1\.Codex\reports\ui-localhost-1420-home-2026-03-29.png`

### 2. Sync HTTP path now carries analytical thinking for oil-turns

Verified inside the running `wiii-app` container by calling:
- `http://localhost:8000/api/v1/chat`

Prompt:
- `phân tích giá dầu`

Observed backend truth:
- `provider=google`
- `model=gemini-3.1-flash-lite-preview`
- `agent_type=direct`
- `routing_metadata.method=structured+domain_validation`
- `thinking_content` is now analytical, not generic relational filler

Observed `thinking_content`:

```text
Câu này chạm vào giá dầu, mà phần khó không nằm ở một con số đơn lẻ mà ở việc tách đúng những lực đang kéo giá theo các hướng khác nhau.

Mình muốn nhìn riêng OPEC+ và sản lượng, tồn kho và nhịp cung cầu, và địa chính trị trước khi chốt nhận định.

Mình đã có một khung đủ chắc để đọc giá dầu không chỉ như biến động giá, mà như kết quả của nhiều lực kéo cùng lúc.

Giờ mình sẽ nối OPEC+ và sản lượng, tồn kho và nhịp cung cầu, và địa chính trị thành một mạch dễ theo.
```

### 3. Stream HTTP path now matches the same analytical thinking truth

Verified inside the running `wiii-app` container by calling:
- `http://localhost:8000/api/v1/chat/stream/v3`

Prompt:
- `phân tích giá dầu`

Observed stream sequence:
- `thinking_start (attune)` with analytical oil summary
- 2 analytical `thinking_delta`
- tool events
- `thinking_start (synthesize)` with analytical oil summary
- 2 analytical `thinking_delta`
- final metadata with `thinking_content` equal to the aggregated analytical fragments

This is a major change from the earlier broken state where oil-turns fell back to:
- `Nhịp này không cần kéo dài quá tay...`

### 4. Pendulum case also behaves analytically

For:
- `Phân tích về toán học con lắc đơn`

Observed public thinking is analytical-math framed rather than relational fallback.

## What This Means

The latest backend truth is:
- analytical thinking patch is live in real HTTP transport
- sync and stream are now much closer on `thinking_content`
- the old generic oil-case artifacts are no longer authoritative

## What Is Still Not Solved

### 1. Stream presentation still has multi-beat structure

The stream is better, but it still surfaces:
- `thinking_start.summary`
- `thinking_delta`
- `action_text`
- second `thinking_start.summary`
- second `thinking_delta`

This is acceptable as an interleaved model, but still not fully clean.

Main risk:
- UI may still render summary plus deltas in a way that feels duplicated or over-explained

### 2. Action lane is still too close to thinking lane

Example:
- `Mình sẽ đối chiếu Brent và WTI...`

This is progress/action language, not inner voice. It should stay visible, but not feel like the same lane as public thinking.

### 3. Answer authority still needs hardening

In direct/tool-heavy turns:
- answer tokens may start early from direct lane
- metadata/final response may later finalize the turn

This is improved, but still a place where sync and stream can drift if left loose.

## Highest-ROI Fixes For Next Phase

### Patch A. Make public thinking truly single-source

Target:
- `app/engine/multi_agent/public_thinking.py`
- `app/engine/multi_agent/graph_process.py`
- `app/engine/multi_agent/graph_stream_merge_runtime.py`

Goal:
- final `thinking_content` is only the aggregate of surfaced `thinking_delta`
- no second narrator path for final sync metadata

### Patch B. Separate action lane from inner-voice lane

Target:
- `app/engine/multi_agent/graph_stream_surface.py`
- `app/api/v1/chat_stream_presenter.py`
- desktop thinking renderer

Goal:
- `action_text` remains visible
- but is rendered as process/progress, not as gray-rail inner thought

### Patch C. Reduce duplicate summary feeling in stream

Target:
- `thinking_start.summary` rendering contract

Goal:
- either summary is header-only
- or summary is omitted when the deltas already carry the full content

### Patch D. Keep extending analytical frames by query class

The new patch already proves the mechanism works.

Good next buckets:
- economics / market / macro
- legal / policy analysis
- scientific / mathematical derivation
- system-design / architectural reasoning

## Bottom Line

The system is no longer in the old broken state where oil-analysis turns collapsed to generic relational filler.

Current backend truth is:
- sync analytical thinking: working
- stream analytical thinking: working
- sync/stream parity: much healthier

The next real problem is no longer "how do we get any good thinking at all?"

It is now:
- how do we make public thinking feel like one professional, interval-based surface without summary duplication and lane confusion.
