# Wiii Backend Reasoning Quality Phase 6

**Date:** 2026-03-17  
**Author:** Codex (LEADER)

## Scope

Phase này tập trung vào **năng lực hệ thống** cho `Code Studio` và `simulation/app quality`, không chạm vào UI/chat chrome.

Mục tiêu:
- simulation/app requests phải được suy nghĩ sâu hơn trước khi code
- follow-up patch không được làm tụt quality bar
- Code Studio không được preview các output simulation quá sơ sài

## Changes

### 1. Adaptive reasoning cho simulation/app

Files:
- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py)

What changed:
- thêm `recommended_visual_thinking_effort(...)`
- `supervisor_node` giờ auto nâng `thinking_effort` cho các case `code_studio_app` chất lượng cao
- `premium simulation` mặc định được nâng lên `max`
- nếu request đã có `thinking_effort` thủ công, supervisor giữ nguyên và không làm mất field này

Impact:
- Wiii không còn xử lý simulation premium như một task “moderate mặc định”
- các app/simulation khó có cơ hội trả về quá nhanh với code naïve

### 2. Follow-up patch giữ nguyên quality bar

Files:
- [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py)
- [visual_intent_resolver.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/visual_intent_resolver.py)

What changed:
- follow-up simulation patch như `thêm slider trọng lực`, `thêm góc lệch và vận tốc` được nhận diện là `simulation`
- các follow-up này giữ `quality_profile="premium"`
- nếu `code_studio_context.active_session` đang là premium, metadata patch cũng preserve quality này

Impact:
- không còn tình trạng mở app premium ở lượt 1 nhưng follow-up lại tụt xuống bar thấp hơn ở lượt 2/3

### 3. Critic gate mạnh hơn cho premium simulation

Files:
- [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)

What changed:
- `_validate_code_studio_output(...)` nhận thêm `quality_profile`
- với `requested_visual_type="simulation"` và `quality_profile="premium"`, validator yêu cầu:
  - render surface rõ (`canvas`/`svg`/equivalent)
  - parameter control thực sự (`range`/`number`/`select`)
  - readout sống (`angle`, `velocity`, status, `aria-live`, ...)
  - state/time engine (`requestAnimationFrame`, `setInterval`, `performance.now`, physics state vars, ...)
- các demo kiểu “vài div + 2 nút + đổi text” bị reject trước preview

Impact:
- Wiii sẽ không còn chấp nhận những output mô phỏng chỉ đủ để “trông như có gì đó chạy”

### 4. Prompt/skill guidance cho planning-first

Files:
- [code_studio.yaml](E:/Sach/Sua/AI_v1/maritime-ai-service/app/prompts/agents/code_studio.yaml)
- [VISUAL_CODE_GEN.md](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/reasoning/skills/subagents/code_studio_agent/VISUAL_CODE_GEN.md)

What changed:
- bổ sung policy `plan first` cho premium simulation/app
- yêu cầu model xác định:
  - state model
  - render surface
  - controls
  - readouts
  - feedback hooks
- nhấn mạnh một vòng self-critique trước khi commit tool call

Impact:
- nâng chất lượng planning ở tầng prompt/skill, không chỉ dựa vào validator cuối

### 5. Cleanup tool contract wording

Files:
- [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py)

What changed:
- bỏ docstring cũ gây hiểu nhầm rằng `tool_create_visual_code` là đường chính cho mọi visual
- contract giờ khớp với lane policy thật:
  - article/chart -> `tool_generate_visual`
  - app/widget/artifact -> `tool_create_visual_code`

## Important frontend/backend contract note

4 field này **không phải phantom fields**:
- `studio_lane`
- `artifact_kind`
- `quality_profile`
- `renderer_contract`

Backend hiện thực sự emit chúng trong `code_open` và `code_complete` SSE events từ [graph.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/multi_agent/graph.py).

`code_studio_context.active_session` cũng đang được backend dùng để:
- reuse đúng session patch
- preserve quality bar
- suy ra mức reasoning tốt hơn cho follow-up app/simulation

Frontend có thể không hiển thị trực tiếp các field này, nhưng **không nên remove khỏi pipeline**.

## Verification

Commands run:

```powershell
python -m pytest maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q
python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q
python -m pytest maritime-ai-service/tests/unit/test_sprint154_tech_debt.py -q
python -m pytest maritime-ai-service/tests/unit/test_graph_routing.py -q
python -m pytest maritime-ai-service/tests/unit/test_code_studio_streaming.py -q
```

Results:
- `20 passed`
- `78 passed`
- `67 passed`
- `24 passed`
- `14 passed`

Targeted total: **203 tests passed**

## Remaining work

Non-blocking but recommended next:
- thêm chart runtime recipe bar cao hơn cho benchmark/data charts
- thêm richer scaffold families cho maritime simulations
- thêm critic/repair loop nhiều bước thay vì validator một lượt
- thêm semantic widget result contract cho `search_widget` và `code_widget`

## Recommendation for current parallel frontend cleanup

Safe to simplify:
- local Code Studio tab state
- UI labels trong panel/card
- over-engineered version helpers nếu team thấy không cần

Do **not** remove blindly:
- `code_studio_context.active_session`
- SSE metadata fields `studio_lane`, `artifact_kind`, `quality_profile`, `renderer_contract`
- backend-driven lane/quality contract
