# Thinking Runtime Recheck - 2026-03-29

> Scope: Bring the project up again after the refactor campaign, verify live runtime, and capture the current backend truth before the next thinking-focused pass.

---

## 1. Runtime Status

- Backend health: `http://127.0.0.1:8000/api/v1/health/live` responded `200` during verification.
- Frontend health: `http://127.0.0.1:1420` responded `200`.
- Docker services confirmed running:
  - `wiii-app`
  - `wiii-postgres`
  - `wiii-minio`

Frontend was restarted on port `1420` and the backend container was also explicitly restarted once during this recheck.

---

## 2. Runtime Regressions Fixed During Recheck

Two concrete post-refactor runtime regressions were preventing trustworthy thinking investigation:

1. `agent_nodes.py` synthesizer path used `settings` without importing it.
2. `graph.py` direct-tool compatibility wrapper no longer matched the newer `tool_collection._collect_direct_tools(..., state=...)` signature.

Additional wrapper regressions surfaced while re-running the graph:

3. `agent_nodes.py` called `get_rag_agent_node()`, `get_tutor_agent_node()`, and `get_memory_agent_node()` without importing them after shell-thinning refactors.

Files patched:

- [agent_nodes.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agent_nodes.py)
- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)

Result:

- `process_with_multi_agent()` can run again end-to-end in a direct container process.
- The graph no longer fails immediately with `NameError: settings` or `unexpected keyword argument 'state'`.

---

## 3. Smoke Truth: Core Engine vs HTTP API

This recheck found an important divergence between the **core engine path** and the **HTTP/API path**.

### 3.1 Direct core invocation inside container

Prompt:

`Phân tích về toán học con lắc đơn`

Raw artifact:

- [direct-core-pendulum-2026-03-29.json](E:/Sach/Sua/AI_v1/.Codex/reports/direct-core-pendulum-2026-03-29.json)

Observed result:

- `provider = google`
- `model = gemini-3.1-flash-lite-preview`
- `routing_metadata.method = structured`
- `routing_metadata.intent = learning`
- `error = null`

Response was substantive and domain-appropriate.

Current final thinking on this path:

```text
Nhịp này không cần kéo dài quá tay.

Mình chỉ cần bắt đúng điều bạn đang chờ ở mình rồi đáp cho thật gần.

Ở đây phần nhìn phải đi trước lời giải thích, để bạn liếc một lần là bắt được xu hướng chính.

Mình sẽ chốt vài mốc đáng tin rồi dựng một khung gọn, sau đó mới nói phần nhận xét.
```

### 3.2 HTTP `/api/v1/chat`

Raw artifact:

- [runtime-smoke-chat-2026-03-29-fixed.json](E:/Sach/Sua/AI_v1/.Codex/reports/runtime-smoke-chat-2026-03-29-fixed.json)

Observed result:

- HTTP `200`
- `provider = google`
- `model = gemini-3.1-flash-lite-preview`
- `routing_metadata.method = rule_based`
- `routing_metadata.intent = unknown`
- `reasoning_trace.direct_response.result = Fallback (LLM generation error)`

Response:

```text
Hmm, mình gặp chút trục trặc khi xử lý. Bạn thử hỏi lại nhé?
```

Thinking:

```text
Nhịp này không cần kéo dài quá tay.

Mình chỉ cần bắt đúng điều bạn đang chờ ở mình rồi đáp cho thật gần.
```

### 3.3 HTTP `/api/v1/chat/stream/v3`

Raw artifact:

- [runtime-smoke-stream-pendulum-2026-03-29-fixed.json](E:/Sach/Sua/AI_v1/.Codex/reports/runtime-smoke-stream-pendulum-2026-03-29-fixed.json)

Observed stream truth:

- `thinking_start.summary` is the same generic 2-line public-thinking beat
- two `thinking_delta` chunks repeat that same generic content
- answer falls back to the same short apology
- metadata confirms:
  - `routing_metadata.method = rule_based`
  - `agent_type = direct`
  - `thinking_content` remains the same generic 2-line fallback

---

## 4. Log Truth

Backend logs consistently show this on the HTTP/API path:

- `Native structured invoke failed`
- `LLM routing failed`
- `API key not valid. Please pass a valid API key.`
- direct response then falls back

Important nuance:

- This error happens in the **running server process**.
- A fresh direct Python process inside the same container can still produce a substantive answer with the same configured provider/model.
- Restarting `wiii-app` did **not** remove the discrepancy.

So the current truth is **not** “Gemini is simply down everywhere”.

The truth is narrower:

- core engine path can succeed
- live HTTP path still degrades into rule-based routing + generic direct fallback

---

## 5. What This Means For Thinking

This is the most important conclusion before starting the real thinking work:

### 5.1 Public thinking is still not authoritative

Even when the system is healthy enough to answer meaningfully on the direct core path, the public thinking still reads as a generic narrated overlay, not as a strong interval-thought trace.

Current example:

```text
Nhịp này không cần kéo dài quá tay.

Mình chỉ cần bắt đúng điều bạn đang chờ ở mình rồi đáp cho thật gần.
```

This is cleaner than raw status noise, but it is still too template-like and too weak for the Wiii target.

### 5.2 The UI-relevant path is still worse than the core path

The path that matters to the user-facing product is:

`request -> chat_orchestrator -> graph/stream -> public thinking -> answer`

That path is still degraded by routing failure and LLM generation failure before we even reach the deeper quality question.

So if we start editing prompt/style only, we will be polishing the wrong layer.

### 5.3 The earlier architectural conclusion still stands

The previous audit remains valid:

- thinking is still not governed by a single producer/authority
- `graph.py` and `graph_streaming.py` remain the hottest surface zones
- the first real thinking objective is still:

`unify producer + authority of public thinking`

not “add more prompt instructions” and not “add more memory flavor”.

---

## 6. Current Backend Truth

At the end of this recheck, the backend truth is:

- Project is up again.
- Frontend dev surface is reachable.
- Core graph runtime blocker regressions from refactor were fixed.
- Direct engine invocation can now answer `con lắc đơn` meaningfully.
- HTTP sync and stream are still degraded into:
  - routing fallback
  - direct fallback answer
  - generic public thinking

So:

- **runtime is partially restored**
- **thinking is still not ready for quality tuning**

because the live API path is not yet behaviorally aligned with the engine truth.

---

## 7. Immediate Next Step Before Thinking Quality Work

The next thinking sprint should start with:

1. explain and fix why the running HTTP server process hits `API_KEY_INVALID` on structured routing/direct generation while the direct container process can still answer;
2. only after sync + stream both stop degrading, re-audit the public thinking intervals;
3. then tackle interval-thinking ownership and quality itself.

If we skip step 1, every evaluation of “thinking quality” on the live surface will remain contaminated by upstream fallback behavior.
