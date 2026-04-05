# Graph Refactor Round 28 — 2026-03-29

## Scope

Round này tiếp tục refactor theo hướng facade + runtime support, chưa đụng vào `thinking`.

Mục tiêu:

- giảm trách nhiệm trực tiếp trong các service/executor shell
- giữ nguyên public surface và patch points mà test đang bám
- chốt thêm compatibility seam cho lazy packages

## Changes

### 1. OpenSandbox executor split

Files:

- `app/sandbox/opensandbox_executor.py`
- `app/sandbox/opensandbox_executor_runtime.py` (new)

Kết quả:

- `opensandbox_executor.py`: `706 -> 516` lines
- `opensandbox_executor_runtime.py`: `380` lines

Extraction:

- metadata/network/config helpers
- `healthcheck`
- `execute`
- `validate_request`
- `create_sandbox`
- `stage_files`
- `execute_python_workload`
- `execute_command_workload`
- `_extract_execution_artifacts`

Giữ nguyên trong shell:

- `OpenSandboxExecutor`
- `OpenSandboxSdk`
- `_load_opensandbox_sdk`
- `httpx.AsyncClient` patch path
- artifact/inline/publish wrappers mà test đang patch/inspect gián tiếp

### 2. LLM runtime audit live-probe split

Files:

- `app/services/llm_runtime_audit_service.py`
- `app/services/llm_runtime_audit_probe_support.py` (new)

Kết quả:

- `llm_runtime_audit_service.py`: `696 -> 463` lines
- `llm_runtime_audit_probe_support.py`: `414` lines

Extraction:

- `_close_async_iterator`
- `_probe_streaming`
- `_probe_tool_calling`
- `_resolve_openai_compatible_probe_config`
- `_probe_openai_compatible_structured_output`
- `_probe_google_runtime_health`
- `_probe_structured_output`
- `_probe_ollama_context_window`
- `_can_probe_provider`
- `_summarize_probe_error`
- `_probe_provider_capabilities`
- `run_live_capability_probes`
- `build_runtime_audit_summary`

Lưu ý quan trọng:

- các hàm module-level cũ vẫn còn ở `llm_runtime_audit_service.py`
- wrapper chỉ delegate xuống support module
- vì vậy các test patch string như
  - `app.services.llm_runtime_audit_service._probe_provider_capabilities`
  - `app.services.llm_runtime_audit_service._can_probe_provider`
  - `app.services.llm_runtime_audit_service._probe_structured_output`
  vẫn tiếp tục hoạt động

### 3. Compatibility improvements for lazy packages

Files:

- `app/api/v1/__init__.py`
- `app/services/__init__.py`

Thay đổi:

- thêm fallback `importlib.import_module(f\"{__name__}.{name}\")` trong `__getattr__`

Lý do:

- sau các đợt lazy import trước đó, nhiều test/patch path cũ kiểu
  - `app.api.v1.health.settings`
  - `app.services.chat_service...`
  bị vỡ vì package chỉ expose một symbol map hẹp
- fallback này khôi phục compatibility mà vẫn giữ lợi ích lazy loading

## Verification

### Compile

Passed:

- `app/sandbox/opensandbox_executor.py`
- `app/sandbox/opensandbox_executor_runtime.py`
- `app/services/llm_runtime_audit_service.py`
- `app/services/llm_runtime_audit_probe_support.py`
- `app/api/v1/__init__.py`
- `app/services/__init__.py`

### Focused tests

Passed:

- `python -m pytest tests/unit/test_opensandbox_executor.py tests/unit/test_code_execution_tools.py -q -p no:capture --tb=short`
  - `45 passed`
- `python -m pytest tests/unit/test_opensandbox_executor.py -q -p no:capture --tb=short`
  - `18 passed`
- `python -m pytest tests/unit/test_llm_runtime_audit_service.py tests/unit/test_llm_selectability_service.py -q -p no:capture --tb=short`
  - `10 passed`
- `python -m pytest tests/unit/test_admin_llm_runtime.py -q -p no:capture --tb=short -k "not updates_use_multi_agent_and_resets_services"`
  - `2 passed, 1 deselected`

### Known unrelated/local drift encountered

Not counted as regression from this round:

- `tests/unit/test_opensandbox_health.py`
  - currently blocked by local SQLAlchemy environment mismatch:
    - `ImportError: cannot import name 'DeclarativeBase' from sqlalchemy.orm`
  - failure happens while importing `app.api.v1.health -> chat_history_repository -> app.models.database`
- `tests/unit/test_admin_llm_runtime.py::test_update_llm_runtime_config_updates_use_multi_agent_and_resets_services`
  - same root blocker through `app.services.chat_service -> chat_orchestrator -> session_manager -> chat_history_repository -> app.models.database`

## Sentrux

Command:

- `E:\\Sach\\Sua\\AI_v1\\tools\\sentrux.exe gate .`

Current result:

- `Quality: 4411`
- `Coupling: 0.30`
- `Cycles: 8`
- `God files: 3`
- `Distance from Main Sequence: 0.31`
- `No degradation detected`

## Current largest backend files

Top line counts after this round:

1. `app/core/config/_settings.py` — `1143`
2. `app/engine/multi_agent/graph.py` — `830`
3. `app/services/chat_orchestrator.py` — `825`
4. `app/engine/reasoning/reasoning_narrator.py` — `793`
5. `app/engine/living_agent/emotion_engine.py` — `792`
6. `app/engine/multi_agent/supervisor.py` — `790`
7. `app/engine/living_agent/heartbeat.py` — `790`
8. `app/api/v1/course_generation.py` — `786`
9. `app/engine/model_catalog.py` — `777`
10. `app/engine/agentic_rag/corrective_rag.py` — `771`

## Assessment

Round 28 là một round refactor tốt:

- hai shell quan trọng đã mỏng đi rõ rệt
- patch points cũ vẫn giữ được
- lazy import compatibility tốt hơn
- không có regression nào ở focused suites của chính phạm vi refactor

Điểm còn lại:

- `Sentrux` chưa kéo được cycles xuống dưới `8`
- hotspot lớn nhất bây giờ không còn là `graph_streaming/direct_execution`, mà chuyển dần sang:
  - `_settings.py`
  - `chat_orchestrator.py`
  - `reasoning_narrator.py`
  - `emotion_engine.py`
  - `course_generation.py`

## Recommended next cuts

Ưu tiên vòng tiếp theo:

1. `app/services/input_processor.py`
   - nhưng phải giữ nguyên body marker của `InputProcessor.build_context` vì có source-inspection test
2. `app/services/chat_orchestrator.py`
   - tách request-prep / presenter / persistence seam thêm một nhát nữa
3. `app/engine/reasoning/reasoning_narrator.py`
   - refactor sạch kiến trúc trước khi quay lại sửa `thinking`
4. `app/core/config/_settings.py`
   - blast radius lớn, nên chỉ làm sau khi đã chốt seam của service/runtime
