# Thinking Claude-Style Pivot - 2026-03-30

## Goal

Pivot `tutor` public thinking away from a system-authored 4-beat template and closer to a Claude-style interval flow where:

- the LLM owns more of the actual thought flow
- the system only curates, sanitizes, deduplicates, and keeps Wiii coherent
- visible thinking stays inward, strategic, and living

## Files Changed

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_draft_service.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_draft_service.py`

## What Changed

### 1. Relaxed prompt contract

The tutor draft service no longer pushes a rigid `observe -> strategy -> doubt -> decision` sequence.

It now asks for:

- 3-5 beats when needed, but with natural flow rather than a checklist
- first beat anchored in the cognitive problem, not the final answer
- optional self-correction only when it is natural
- no decorative kaomoji in gray-rail body

### 2. Added few-shot quality examples

Tutor drafts now get short, lane-specific examples that model:

- real inward monologue
- pedagogical strategy selection
- follow-up visual thinking without replaying the whole explanation

### 3. Soft quality evaluator instead of hard arc gate

The service now judges quality with softer signals:

- too short
- answer-ish opening
- plan-first opening too early (`Mình sẽ...`)
- repetition
- missing strategic move
- missing self-correction on longer drafts

### 4. Repair loop is now actually judged

Before this patch, a repaired draft could still be short or weak and still get accepted.

Now the service:

- scores the initial draft
- scores repair outputs
- keeps the better version
- can run a second, firmer repair pass if needed

## Focused Verify

Command:

```powershell
$env:PYTHONIOENCODING='utf-8'; python -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_draft_service.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_supervisor_agent.py `
  -q -p no:capture
```

Result:

- `99 passed`

## Live Probes

### Tutor explanation

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-claude-pivot-sync-2026-03-30-r4.json`

Current tutor thinking sample:

> Nếu cứ bắt đầu bằng việc trích dẫn luật, mình sẽ vô tình biến một tình huống thực tế đầy áp lực trên biển thành một bài kiểm tra học thuộc lòng...

This run is materially better than the earlier template-like outputs because it:

- opens from the learner's likely confusion
- contains real self-correction
- makes pedagogical decisions visible
- sounds like Wiii thinking, not a system checklist

### Tutor visual follow-up

Artifact:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-tutor-claude-pivot-visual-sync-2026-03-30-r2.json`

Current truth:

- follow-up visual can stay on `tutor_agent`
- thinking now shifts toward what must become visible, not simply replaying the explanation

## Current Truth

The core problem has shifted:

- earlier: leak/parity/authority bugs
- now: quality and variance of model-authored visible thinking

After this pivot, `tutor` thinking is no longer mostly renderer-authored.
It is now:

- **LLM-authored first**
- **curated second**

That is much closer to the Claude-style interval-thinking direction than the old template path.

## Remaining Gaps

1. Some runs still repeat the same idea in two nearby beats.
2. Some runs still overuse `Mình sẽ...` in later beats.
3. `direct` lane can still fall back to older narrator-style scaffolds, so if routing drifts, quality drifts with it.

## Recommended Next Step

Apply the same `LLM-authored public thought draft` pattern to `direct` lane, especially:

- visual/social-open follow-ups
- analytical turns that still show narrator-era scaffolds

That is the highest-ROI move if the goal is to make thinking quality stable across the whole system, not just inside `tutor`.
