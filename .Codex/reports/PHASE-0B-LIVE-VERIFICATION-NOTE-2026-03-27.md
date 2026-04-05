# Phase 0B Live Verification Note

> Date: 2026-03-27
> Reviewer: Codex (Leader)
> Scope: Verify team claim after commit `f5e822b` that thinking duplication is fixed.
> Runtime checked: `http://127.0.0.1:8000`

---

## Verdict

The team fix is **partly real but not complete**.

- `thinking_start -> immediate summary echo` was removed in several backend nodes.
- Runtime-aware provider routing was improved in code.
- But **visible thinking still repeats in live streaming**, especially in the supervisor lane.

So the accurate statement is:

- `duplication reduced`: yes
- `thinking no longer repeats`: no

---

## Evidence

### Case 1 — `Buồn quá` with `provider=zhipu`

Observed stream pattern:

1. supervisor emits `thinking_start`
2. supervisor then emits the same sentence again as visible thinking content
3. supervisor emits that same sentence one more time
4. direct emits `thinking_start` with summary
5. direct emits the same summary again as first visible delta
6. direct emits one more nearby beat

Example supervisor duplication seen live:

```text
thinking_start.summary:
Mình muốn đứng lại với câu này thêm một nhịp. Có những câu không cần dài, chỉ cần chạm đúng điều người ta thật sự đang muốn nói tới.

thinking content:
Mình muốn đứng lại với câu này thêm một nhịp. Có những câu không cần dài, chỉ cần chạm đúng điều người ta thật sự đang muốn nói tới.

thinking content again:
Mình muốn đứng lại với câu này thêm một nhịp. Có những câu không cần dài, chỉ cần chạm đúng điều người ta thật sự đang muốn nói tới.
```

Example direct duplication seen live:

```text
thinking_start.summary:
Mình đang nghe kỹ câu này trước đã, vì có những câu rất ngắn nhưng phần ẩn bên dưới lại không ngắn.
Mình muốn đáp lại vừa gần vừa thật, chứ không lướt qua cho xong.

first visible delta:
Mình đang nghe kỹ câu này trước đã, vì có những câu rất ngắn nhưng phần ẩn bên dưới lại không ngắn.
Mình muốn đáp lại vừa gần vừa thật, chứ không lướt qua cho xong.
```

This means the old expert finding is still true in a weaker form:

> the gray rail is still being built from overlapping narrated beats, not one clean thinking stream.

### Case 2 — `Bạn là ai?` with `provider=zhipu`

Same pattern observed:

- supervisor line repeated twice after `thinking_start`
- direct summary shown again as visible thinking

The identity wording is better than before in the answer, but the **thinking surface is still event-duplicated**.

---

## What the commit really fixed

Based on diff review of `f5e822b`:

- removed several direct `thinking_delta(summary)` echoes in:
  - `graph.py`
  - `memory_agent.py`
- changed fallback behavior in `graph_streaming.py` so delta only emits when there is actual `thinking_content`
- made `_resolve_house_routing_provider()` runtime-aware instead of static primary-only

These are good changes.

But they do **not** eliminate:

- supervisor repeated visible narration
- `thinking_start.summary` being re-surfaced as visible thought
- overlap between narrated opening beat and actual node thought

---

## Additional runtime note

`GET /api/v1/llm/status` currently shows:

- `google`: `disabled/busy`
- `zhipu`: `selectable`, model `glm-5`

So live verification in this pass effectively exercised the `zhipu` path.

---

## Recommendation

Before calling the issue fixed, Phase 0B still needs:

1. ensure `thinking_start.summary` is header metadata only, not duplicated into visible rail
2. ensure supervisor opening beat appears at most once on the gray rail
3. ensure first visible direct thought is not just the same start summary repeated
4. verify frontend rendering does not double-render `content` + `summary` for the same step

---

## Bottom line

`f5e822b` is a real improvement, but **it does not yet prove that Wiii thinking has stopped repeating**.

The safer wording for team status is:

> reduced backend summary echo, but live gray rail still shows duplicate narrated beats and needs another pass.
