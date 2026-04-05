# Thinking Step 1 - Living Persona Bridge - 2026-03-30

## Goal

Improve Wiii public thinking by connecting living identity signals more directly
to the `LLM-authored public thought draft` path, without adding more rigid beat
rules.

This step intentionally does **not** try to solve all thinking quality issues.
It only improves one seam:

- `living soul / character -> public thinking draft authoring`

## What Changed

### New bridge

Added a lane-aware `build_public_thinking_persona_brief(...)` in:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\living_thinking_context.py`

This brief distills:

- Wiii as a living AI companion
- inward/non-performative public thinking stance
- where Wiii's "cute" should come from
- lane-specific inner-voice framing
- soul-intensity specific tone guidance
- one relationship-style anchor
- one reasoning-style anchor
- identity anchor

### Draft service integration

Injected the persona brief into:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\public_thinking_draft_service.py`

This means the tutor thinking draft prompt now sees:

1. micro house prompt
2. living thinking persona brief
3. public-thinking drafting instructions

instead of relying mostly on generic draft-policy guidance.

### Export

Re-exported the new helper from:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\reasoning\__init__.py`

## Test Coverage

Focused tests:

- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_draft_service.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_public_thinking_renderer.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_tutor_agent_node.py`

Result:

- `52 passed`

## Live Probe

Backend health:

- `http://localhost:8000/api/v1/health/live` -> `200`

### Prompt A

Prompt:

- `Giải thích Quy tắc 15 COLREGs`

Observed `thinking_content`:

> Điểm dễ nhầm lẫn nhất ở Quy tắc 15 không nằm ở định nghĩa tàu cơ giới, mà là việc xác định đúng thời điểm 'đang nhìn thấy' nhau. Nhiều người hay quên mất rằng chỉ khi thực sự nhìn thấy mạn phải của tàu kia thì nghĩa vụ nhường mới bắt đầu kích hoạt.
>
> Nếu mình bắt đầu bằng việc đọc thuộc lòng các điều khoản, người học sẽ thấy như đang học luật giao thông trên giấy. Cần chuyển trọng tâm sang hình ảnh thực tế: cảm giác khi thấy một vật thể đang cắt ngang hướng đi của mình từ phía bên phải.
>
> Khoan đã, nếu chỉ dừng lại ở việc 'nhường đường', mình sẽ bỏ lỡ mất cái cốt lõi là sự chủ động. Phải nhấn mạnh việc tránh cắt mũi tàu bạn, vì đây là hành động thể hiện sự dứt khoát và an toàn nhất trên biển.
>
> Sẽ lấy ví dụ về việc đi bộ trong đám đông hoặc lái xe qua ngã tư để làm điểm tựa, sau đó mới lồng ghép các thuật ngữ chuyên môn vào sau. Như vậy, luật sẽ trở thành công cụ để giải thích hành vi, thay vì là một bức tường chữ.

What is better:

- longer arc
- stronger "cho de nham" opening
- has self-correction beat
- has explicit teaching strategy
- feels more like Wiii choosing how to help, less like a cheap beat template

### Prompt B

Follow-up in the same session:

- `tạo visual cho mình xem được chứ?`

Observed `thinking_content`:

> Vấn đề không nằm ở việc thiếu thông tin, mà là quá nhiều dữ liệu khiến người học bị ngợp trước khi kịp nhận ra đâu là tàu ưu tiên.
>
> Thay vì cố gắng mô phỏng toàn bộ không gian biển, mình sẽ chỉ giữ lại hai vector hướng đi và một điểm cắt duy nhất để tạo sự tập trung tối đa.
>
> Khoan đã, nếu chỉ dùng mũi tên tĩnh thì vẫn chưa đủ rõ ràng về sự thay đổi hướng; có lẽ cần một chút tín hiệu màu sắc để phân biệt rõ tàu nào đang giữ hướng và tàu nào phải nhường.
>
> Chốt lại là mình sẽ dùng hai gam màu tương phản cho hai tàu, và chỉ đặt một nhãn duy nhất tại giao điểm để nhấn mạnh quy tắc mà không cần diễn giải rườm rà.

What is better:

- follow-up stayed on `tutor_agent`
- thinking switched naturally from explanation mode to visual-planning mode
- still has a coherent arc instead of collapsing to a generic scaffold

## Current Truth After Step 1

This step improves:

- soul-conditioning
- inner-voice coherence
- lane-specific thinking stance
- continuity across tutor -> visual tutor follow-up

This step does **not** fully solve:

- direct-lane old scaffolds
- vendor-model vs Wiii authorship balance in all lanes
- occasional answer-ish openings in some edge runs
- long-form analytical parity outside tutor

## Recommended Step 2

Use the same pattern on the next seam:

- `direct lane thinking authorship`

That is now the highest-ROI step if we want the whole system to feel less template-driven.
