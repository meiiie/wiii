# Graph Refactor Round 7 — 2026-03-28

## Scope

Round này tiếp tục refactor theo hướng clean architecture, ưu tiên:

1. giảm responsibility của streaming shell
2. kéo `prompt_loader.py` xuống khỏi vùng god-file
3. kéo `corrective_rag.py` xuống gần hơn với pipeline core thay vì ôm utility/surface logic

## Thay đổi chính

### 1. Streaming bootstrap/finalization tách khỏi shell

File mới:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_stream_runtime.py`

File chỉnh:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\graph_streaming.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\multi_agent\openai_stream_runtime.py`

Đã tách:
- bootstrap initial state / event bus / invoke config
- final sources / metadata / done emission

Hiệu quả:
- `graph_streaming.py` giảm inline orchestration boilerplate
- wrapper seam rõ hơn cho streaming runtime
- sửa luôn một regression test của `openai_stream_runtime.py` do import alias `get_settings()`

### 2. Prompt overlay guard tách riêng

File mới:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_overlay_guard.py`

File chỉnh:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py`

Đã tách:
- sanitize domain overlay
- sanitize contextual overlay text
- merge_with_base
- identity-override guard constants/patterns

Mục tiêu đạt được:
- `prompt_loader.py` không còn ôm cả overlay-protection logic
- prompt identity guard trở thành utility riêng, dễ test hơn

### 3. Prompt time/pronoun helpers tách riêng

File mới:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_context_utils.py`

File chỉnh:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\prompts\prompt_loader.py`

Đã tách:
- `build_time_context()`
- `detect_pronoun_style()`
- `get_pronoun_instruction()`
- associated constants/rules

Mục tiêu đạt được:
- `prompt_loader.py` quay gần hơn về vai trò `load + compose`
- time/pronoun policy thành module độc lập

### 4. Corrective RAG surface helpers tách riêng

File mới:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\agentic_rag\corrective_rag_surface.py`

File chỉnh:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\agentic_rag\corrective_rag.py`

Đã tách:
- visible text normalization
- no-doc retrieval copy
- house fallback reply
- English detection
- Vietnamese translation helper

Mục tiêu đạt được:
- `CorrectiveRAG` tập trung hơn vào retrieve / grade / generate / verify
- surface wording và translation utilities ra ngoài class

## Kích thước file sau round này

Theo local line scan:

- `graph.py`: `1428`
- `supervisor.py`: `1328`
- `graph_streaming.py`: `1508`
- `prompt_loader.py`: `1250`
- `corrective_rag.py`: `1551`

Top remaining large files:

- `visual_tools.py`: `4586`
- `_settings.py`: `1689`
- `corrective_rag.py`: `1551`
- `graph_streaming.py`: `1508`
- `admin.py`: `1458`

## Verification

### Compile

Passed:
- `graph_streaming.py`
- `graph_stream_runtime.py`
- `openai_stream_runtime.py`
- `prompt_loader.py`
- `prompt_context_utils.py`
- `prompt_overlay_guard.py`
- `corrective_rag.py`
- `corrective_rag_surface.py`

### Tests passed

Focused green batches:

- `test_sprint54_graph_streaming.py` → `40 passed`
- `test_graph_routing.py` + `test_supervisor_agent.py` → `119 passed`
- `test_graph_routing.py` + `test_supervisor_agent.py` + `test_sprint54_graph_streaming.py` → `159 passed`
- `test_enhanced_prompt_loader.py` + `test_corrective_rag_unit.py` + `test_rag_agent_node.py` → `36 passed`

### Test failures observed but not introduced by this round

1. `test_sprint189_rag_integrity.py`
   - fail do môi trường local `sqlalchemy.orm.DeclarativeBase` import
   - đây là environment problem hiện hữu, không liên quan trực tiếp refactor round này

2. `test_sprint54_rag_agent.py`
   - fail do legacy patch seam `app.engine.agentic_rag.rag_agent.PromptLoader`
   - fail này xuất hiện từ module `rag_agent.py` cũ/legacy patch assumption, không phải regression trực tiếp từ `corrective_rag_surface`

3. Một số `prompt/visual` tests rộng
   - đang fail do baseline content/fixture drift sẵn có
   - không được dùng làm signal chính cho round refactor cấu trúc này

## Sentrux

Latest gate:

- `Quality: 3581 -> 3580`
- `Coupling: 0.36 -> 0.34`
- `Cycles: 8 -> 8`
- `God files: 9 -> 7`
- verdict: `No degradation detected`

Interpretation:

- quality tổng gần như giữ nguyên
- coupling giảm ổn định
- god-file count vẫn dừng ở `7`, nhưng đã rời xa trạng thái ban đầu hơn rõ
- refactor round này là structural improvement thật, không chỉ move code

## Nhận định

Round này quan trọng ở chỗ:

1. `graph_streaming.py` đã có seam runtime rõ hơn
2. `prompt_loader.py` thoát khỏi vùng lớn và bớt vai trò lẫn lộn
3. `corrective_rag.py` bớt utility noise để chuẩn bị cắt tiếp

Điều này phù hợp với mục tiêu dài hạn:

- shell mỏng hơn
- utility/policy tách riêng
- domain service tập trung vào pipeline thay vì ôm cả formatting/surface

## Nhát cắt tiếp theo đề xuất

Ưu tiên:

1. tiếp tục hạ `graph_streaming.py` xuống rõ ràng dưới ngưỡng
2. tiếp tục hạ `corrective_rag.py` bằng cách tách confidence / fallback prompt building
3. bắt đầu audit `admin.py` hoặc `visual_tools.py` theo cụm pure helper trước

Không nên làm ngay:

- đại phẫu `_settings.py` nếu chưa có strategy cấu hình/module boundaries rõ
- đụng thinking/UI contract trong cùng round refactor này
