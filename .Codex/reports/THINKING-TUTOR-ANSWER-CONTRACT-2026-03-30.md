# THINKING-TUTOR-ANSWER-CONTRACT-2026-03-30

## Summary
- Added a tutor answer contract in `tutor_response.py` so learning turns strip companion-heavy openers and preserve thesis-first framing.
- Brought tutor streaming parity in `tutor_node.py` by streaming the curated final answer instead of raw model chunks.
- Hardened `SupervisorAgent.synthesize()` so metadata like `*_tools_used` no longer forces a second synthesis pass that can rewrite the tutor voice.

## Files
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_response.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/supervisor.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_tutor_agent_node.py`
- `E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_supervisor_agent.py`

## Verification
- `python -m pytest tests/unit/test_tutor_agent_node.py tests/unit/test_supervisor_agent.py -q`
- Result: `77 passed`

## Live truth
Prompt: `Giải thích Rule 15 khác gì Rule 13`

### Sync `/api/v1/chat`
- No greeting opener.
- Opens thesis-first: `Rule 13 và Rule 15 khác nhau cơ bản ở thứ tự ưu tiên và vị trí tương đối...`
- No forced Markdown headings/table shell.

### Stream `/api/v1/chat/stream/v3`
- Thinking rail stays curated and instructional.
- Final answer opens thesis-first: `Khác biệt cốt lõi nằm ở tiêu chí nhận diện và điều kiện áp dụng...`
- Raw companion preface is no longer streamed into the answer lane.

## Remaining gap
- Sync and stream still come from two real requests, so wording can differ run to run.
- The remaining work is no longer opener leakage. It is deeper answer-quality alignment and tool-choice stability for tutor turns.
