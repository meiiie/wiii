# Thinking P0 Producer Cleanup

Date: 2026-03-30
Owner: Codex LEADER

## Scope

This round focused on **cleaning public-thinking producers** before any deeper quality tuning.

Target lanes:

1. `rag`
2. `tutor`
3. `memory`

Goal:

- stop technical telemetry from surfacing as gray-rail thinking
- stop answer-draft prose from entering public thinking
- stop raw/private memory thought from leaking into visible thinking

## Files Changed

Backend:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\rag_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\tutor_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\agents\memory_agent.py`

Tests:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_rag_agent_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_memory_agent_node.py`

## What Changed

### 1. RAG lane

Public RAG thinking is now split into two classes:

- `status_only` internal telemetry
- public-safe visible thinking

Technical strings such as:

- `Độ phức tạp`
- `Knowledge Base`
- `Độ tin cậy phân tích`
- `Chiến lược tìm kiếm`

are now demoted out of public thinking.

Visible retrieval beats are sanitized into public-safe narration like:

- `Mình đang rà nguồn phù hợp trước khi chốt câu trả lời.`
- `Mình chưa thấy nguồn nào thật sự khớp, nên chuyển sang cách đáp trực tiếp.`

### 2. Tutor lane

Tutor no longer pushes the pre-tool draft into gray rail.

That was the path that used to make thinking look like a mini-answer before tools had even finished.

Current behavior:

- tool draft prose is suppressed from `thinking_delta`
- public tutor thinking is filtered through a public-thinking sanitizer
- sync tutor thinking no longer inherits private/raw LLM thought

### 3. Memory lane

Memory no longer propagates hidden/private thought from final response extraction into state.

Instead, visible memory thinking is now built from **public fragments only** and resolved through public-thinking aggregation.

Memory gray rail was also rewritten away from answer-like relational prose such as:

- `Nam vừa giới thiệu tên...`
- `Chào Nam!...`

into inward beats such as:

- `Mình rà lại những mảnh ký ức cũ trước, để không bấu vào chi tiết đã cũ hoặc lệch nhịp.`
- `Mình tách xem trong tin nhắn này có điều gì đủ bền để thành ký ức lâu hơn một lượt chat.`

## Focused Verification

Compile:

- `python -m py_compile ...memory_agent.py ...test_memory_agent_node.py`
- pass

Targeted suites:

- `test_tutor_agent_node.py`: `24 passed`
- `test_memory_agent_node.py`: `15 passed`
- `test_rag_agent_node.py + test_tutor_agent_node.py + test_memory_agent_node.py`: `55 passed`

## Live Runtime Artifacts

Latest live probes:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-p0-live-sync-final-2026-03-30.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-p0-live-stream-final-2026-03-30.txt`

Earlier probe snapshots used for comparison:

- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-p0-live-sync-rerun-2026-03-30.json`
- `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-p0-live-stream-rerun-2026-03-30.txt`

## Current Truth By Lane

### Tutor

Prompt tested:

- `Giải thích Rule 15 là gì`

Current truth:

- gray rail no longer shows `Độ phức tạp / Knowledge Base / 100%`
- pre-tool draft leakage path is closed
- stream still shows a long tutor reasoning beat, but it is now reasoning-shaped content, not telemetry
- sync currently returns `thinking_content=""` for this lane in the tested path

Interpretation:

- **producer leak cleanup: mostly fixed**
- **quality/shape: not done**

### Memory

Prompt tested:

- `Mình tên Nam, nhớ giúp mình nhé`

Current truth:

- private thought no longer leaks into `thinking` / `thinking_content`
- public thinking is no longer direct answer prose like `Nam vừa...`
- sync and stream now show safer internal beats around memory retrieval/extraction

Observed public memory thinking in latest live sync:

```text
Mình rà lại những mảnh ký ức cũ trước, để không bấu vào chi tiết đã cũ hoặc lệch nhịp.

Mình tách xem trong tin nhắn này có điều gì đủ bền để thành ký ức lâu hơn một lượt chat.
```

Interpretation:

- **private-thought leak: fixed**
- **mini-answer gray rail: improved substantially**
- **still not fully human-like yet**

### RAG

Current truth from focused tests and earlier live checks:

- technical telemetry is no longer allowed to become public thinking
- retrieval failure surface now degrades to user-safe narration instead of raw CRAG trace

Interpretation:

- **telemetry leak: fixed at producer layer**
- deeper RAG quality tuning remains separate work

## What Is Still Not Fixed

### 1. Tutor quality is still too companion-heavy

This is now more of an **answer-quality** problem than a producer-authority problem.

The latest live `Rule 15` answer still sounds too cute/companion-like for a serious instructional turn.

### 2. Tutor stream thinking can still be too long

It is no longer leaking the wrong class of content, but it still behaves like a long explanatory beat.

That is a **thinking quality/compression** issue, not the old leak issue.

### 3. Memory thinking is safe but still generic

Memory now sounds inward and safe, but not yet deeply alive or nuanced.

That should be handled in the next quality phase, not by reopening private/raw channels.

## Overall Verdict

P0 cleanup result:

- `rag`: pass
- `tutor`: partial pass
- `memory`: pass with quality debt

The important structural win is this:

**public thinking is now much cleaner at the producer layer.**

The remaining work is no longer mainly:

- telemetry leak
- raw private thought leak
- answer draft masquerading as thinking

The remaining work is now mainly:

- thinking quality
- lane-specific reasoning style
- answer-tone discipline

## Recommended Next Step

Move from **P0 producer cleanup** to **P1 thinking quality**:

1. tighten tutor teaching tone for serious instructional turns
2. shorten or structure tutor gray-rail beats without making them robotic
3. make memory thinking less generic and more genuinely reflective
4. keep `public thinking authority` locked to visible deltas only

