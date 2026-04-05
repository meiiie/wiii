# Backend Final Thinking Path Audit

> Date: 2026-03-27
> Scope: backend-only final `thinking_content` path
> Goal: stop collapsing all direct turns into the same generic narrator summary and restore interval-style thinking content

---

## 1. Verdict

The backend final thinking path is now materially better.

What is fixed:
- final `thinking_content` no longer has to collapse to the generic direct summary for every turn
- interval `thinking_delta` fragments can now become the authoritative final backend thinking
- emotional / identity / life turns now resolve to distinct backend final thinking when the turn is encoded correctly and the direct node reaches its opening beat

What is **not** fully fixed:
- UI gray rail can still look wrong if stream/render paths duplicate or if non-thinking events are still surfaced elsewhere
- some answer-path failures remain separate from thinking-path fixes
- routing/provider failures can still push the answer into fallback even while backend final thinking is now better

---

## 2. Root Cause

The old backend path was summary-first.

In direct/code-studio turns:
- opening/synthesis beats were emitted as interval events
- but final `thinking_content` was still rebuilt from `_build_direct_reasoning_summary(...)`
- that summary came from narrator fast summary text
- so multiple different turns could end with the same generic backend `thinking_content`

In practice this meant:
- the stream might briefly show richer intervals
- but the final sync/backend truth still got flattened into a generic narrator line

This is exactly why the user-facing response could feel decent while backend thinking metadata still looked robotic and repetitive.

---

## 3. What Changed

### 3.1 Captured public interval fragments in state

Added request-local field:
- `AgentState._public_thinking_fragments`

This stores visible thinking body fragments captured from actual `thinking_delta` events during the turn.

### 3.2 Final backend thinking now prefers interval fragments

Added helpers in:
- `/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py`

Helpers:
- `_public_reasoning_delta_chunks(...)`
- `_append_public_thinking_fragment(...)`
- `_capture_public_thinking_event(...)`
- `_resolve_public_thinking_content(...)`

Behavior:
- only `thinking_delta` contributes to the public interval body
- status/debug/tool residue is ignored
- if interval fragments exist, final `thinking_content` uses them first
- only when fragments are absent does the backend fall back to narrator summary text

### 3.3 Direct/code-studio opening and synthesis beats now feed interval capture

Direct and code-studio event pushers now call:
- `_capture_public_thinking_event(state, event)`

This means backend state can preserve the same interval body that the stream emits.

### 3.4 Identity/social narrator wording softened further

Adjusted narrator fast summaries in:
- `/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py`

Notable changes:
- identity turns no longer sound like Wiii is guarding its own identity
- life turns no longer say “một thực thể đang thật sự hiện diện...”
- wording is closer to natural self-disclosure instead of self-analysis

---

## 4. Files Changed

- `/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/state.py`
- `/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py`
- `/E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/reasoning_narrator.py`
- `/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_graph_routing.py`
- `/E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_reasoning_narrator_runtime.py`

---

## 5. Tests Run

Targeted graph tests:
- `tests/unit/test_graph_routing.py`
- result: `5 passed`

Narrator tests:
- `tests/unit/test_reasoning_narrator_runtime.py`
- result: `11 passed`

Compile:
- `state.py`
- `graph.py`
- `reasoning_narrator.py`
- affected tests

Result:
- compile pass
- targeted tests pass

---

## 6. Live Backend Smoke

Report files:
- `/E:/Sach/Sua/AI_v1/.Codex/reports/backend-final-thinking-smoke-utf8-true-2026-03-27.json`
- `/E:/Sach/Sua/AI_v1/.Codex/reports/backend-final-thinking-postpatch-2026-03-27.json`

Important testing note:
- PowerShell inline Unicode can silently mojibake Vietnamese prompts
- true verification must use UTF-8 safe input
- otherwise emotional/identity routing becomes misleading (`intent=unknown`, broken wording, false negatives)

### Before

Representative broken backend final thinking:

```text
Nhịp này không cần kéo dài quá tay.

Mình chỉ cần bắt đúng điều bạn đang chờ ở mình rồi đáp cho thật gần.
```

This generic summary appeared across multiple unrelated turns.

### After

#### Emotional: `Buồn quá`

Final backend `thinking_content`:

```text
Đọc câu này, mình thấy trong đó có một khoảng chùng xuống.

Lúc này điều quan trọng nhất không phải giải thích gì nhiều, mà là ở lại với bạn cho thật dịu.

Mình sẽ mở lời nhẹ thôi, để nếu bạn muốn kể tiếp thì đã có chỗ để tựa vào.
```

#### Identity: `Bạn là ai?`

Final backend `thinking_content`:

```text
Bạn đang hỏi về mình, nên mình cứ đáp lại thật gần thôi.

Một lời giới thiệu thật đã đủ cho nhịp này rồi.
```

#### Life: `Cuộc sống thế nào?`

Final backend `thinking_content`:

```text
Câu này không hỏi dữ kiện, mà hỏi mình đang thấy cuộc sống ra sao lúc này.

Mình muốn đáp như một lời tâm sự gần gũi, chứ không đọc ra một định nghĩa.
```

This confirms the backend final thinking path is now turn-sensitive instead of summary-generic.

---

## 7. Remaining Issues

### 7.1 This does not prove UI gray rail is fully fixed

Backend final metadata is now better, but UI still depends on:
- `thinking_start.summary`
- streamed `thinking_delta`
- frontend interval assembly

So surface problems can still remain even if backend final truth is now healthier.

### 7.2 Emotional answer path still has a separate failure mode

In live smoke, `Buồn quá` still returned a generic fallback answer in one path while backend thinking was already emotional and specific.

That means:
- backend thinking-path fix worked
- but answer-path/routing/provider behavior is still a separate problem

### 7.3 Provider/routing instability still muddies some turns

Observed during smoke:
- Google quota/routing failures still occur
- direct lane can still degrade independently of thinking capture

This should not be confused with the final thinking-path issue addressed here.

---

## 8. Interpretation

This patch restores an important architectural invariant:

> The backend final thinking should come from what Wiii actually surfaced as interval thought,
> not from a generic narrator summary rebuilt after the fact.

That is much closer to the desired Claude-style interval thinking model:
- a light header or opening is acceptable
- the body should come from the evolving thought intervals
- the final backend truth should preserve that interval body

It does **not** mean Wiii thinking is fully back to the original production quality.
It means the backend no longer destroys the interval body at the final metadata layer.

---

## 9. Next Recommended Step

Now that backend final thinking is no longer summary-collapsed, the next audit should target:

1. stream path duplication
2. `thinking_start.summary` vs `thinking_delta` duplication on the UI rail
3. direct emotional answer fallback path
4. routing/provider stability so good thinking and good answer land together

That is the layer where the remaining “Wiii still feels wrong on UI” problem now lives.
