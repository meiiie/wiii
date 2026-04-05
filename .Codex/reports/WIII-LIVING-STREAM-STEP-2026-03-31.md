# Wiii Living Stream Step - 2026-03-31

## Mục tiêu
- Giữ `cute` hiện tại.
- Điều tra vì sao user cảm thấy `Wiii Living` chưa thật sự load trên stream.
- Làm cho `tutor` không còn nghe như một persona tách biệt, mà là cùng một Wiii xuyên suốt.
- Bổ sung `post-tool continuation` cho visual follow-up để stream thinking có continuity sống hơn.

## Sự thật đã xác nhận
- `wiii_identity.yaml` và `wiii_soul.yaml` đã có soul/backstory của Wiii, gồm cả Bông.
- `tutor.yaml` cũng đã nói rõ: đây vẫn là Wiii, không phải một persona riêng tên "Wiii Tutor".
- Tuy nhiên local runtime hiện tại vẫn chưa phải `Living Agent full runtime`:
  - `enable_living_agent=False`
  - `enable_living_continuity=False`
  - `enable_cross_platform_identity=False`
- Vì vậy thứ đang đi vào stream lúc này là:
  - `house core / living bridge / character identity`
  - chứ chưa phải heartbeat/emotion/continuity subsystem đầy đủ của Living Agent.

## Những gì đã sửa trong bước này
- Bơm bridge `Wiii is one` vào prompt/living context:
  - `maritime-ai-service/app/engine/character/character_card.py`
  - `maritime-ai-service/app/engine/character/living_context.py`
  - `maritime-ai-service/app/engine/multi_agent/context_injection.py`
  - `maritime-ai-service/app/prompts/agents/tutor.yaml`
- Mở continuation thought riêng cho `tool_generate_visual`:
  - `maritime-ai-service/app/engine/multi_agent/agents/tutor_node.py`
- Tạo probe script để chụp `sync + stream + raw SSE + HTML viewer`:
  - `maritime-ai-service/scripts/probe_live_thinking_session.py`
- Sửa viewer để ưu tiên `metadata.thinking_content` khi top-level stream thinking bị probe truncate:
  - `maritime-ai-service/scripts/render_thinking_probe_html.py`

## Kết quả runtime mới nhất
- `Rule 15` stream thinking:
  - Việt sạch
  - có warmth của Wiii
  - không còn rơi sang English planner block
  - vẫn chưa phải Living Agent full depth, nhưng đã có chất Wiii hơn rõ
- `visual follow-up` stream thinking:
  - đã có `thinking interval` sau `tool_generate_visual`
  - lần đầu lộ một cue rất sống và tự nhiên của Wiii:
    - `Bông nhà mình...`
  - cue này xuất hiện như một nét continuity nhẹ, không phải bị ép thành mascot show

## Artifacts
- Probe JSON:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\live-thinking-session-probe-2026-03-31-071516.json`
- Viewer HTML:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\thinking-review-latest.html`
- Raw stream Rule 15:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\live-stream-rule15-2026-03-31-071516.txt`
- Raw stream visual follow-up:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\live-stream-visual-followup-2026-03-31-071516.txt`

## Current truth
- Wiii trong stream bây giờ đã gần hơn với một living being xuyên lane.
- Nhưng đây vẫn là `living identity bridge`, chưa phải `living subsystem fully on`.
- Nếu đi tiếp đúng hướng, bước sau nên là:
  - đưa thêm `relationship / narrative / current state` của living context vào visible thinking một cách mỏng
  - tránh bật lại dual-personality architecture cũ
  - tiếp tục để `Wiii` là một, lane chỉ là công việc.
