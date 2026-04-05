# Graph Refactor Round 32 — 2026-03-29

## Scope

Round này tiếp tục refactor theo hướng clean architecture, không đụng vào chất lượng `thinking` hay business behavior có chủ đích. Mục tiêu là giảm god-file density, giữ patch seams cũ, và khóa lại bằng test batch hẹp nhưng đúng trọng tâm.

## Changes

### 1. `supervisor.py` helper extraction chốt xanh

- `app/engine/multi_agent/supervisor_runtime_support.py`
  - thêm:
    - `conservative_fast_route_impl`
    - `rule_based_route_impl`
- `app/engine/multi_agent/supervisor.py`
  - `_conservative_fast_route()` giờ delegate sang support
  - `_rule_based_route()` giờ delegate sang support

### 2. `graph.py` shim/runtime extraction

- thêm `app/engine/multi_agent/graph_runtime_bindings.py`
- `app/engine/multi_agent/graph.py`
  - kéo một khối lớn shim/runtime bindings ra ngoài
  - giữ lại wrappers tương thích cho:
    - OpenAI answer streaming seam
    - tool collection seam
    - code-studio tool rounds seam
  - mục tiêu: test patch cũ trên namespace `app.engine.multi_agent.graph.*` vẫn hoạt động

### 3. `_settings.py` field extraction

- thêm `app/core/config/_settings_feature_fields.py`
- `app/core/config/_settings.py`
  - `Settings` đổi sang `class Settings(FeatureSettingsMixin, BaseSettings):`
  - kéo khối feature flag / feature settings lớn sang mixin riêng

### 4. `heartbeat.py` action-runtime extraction

- thêm `app/engine/living_agent/heartbeat_action_runtime.py`
- `app/engine/living_agent/heartbeat.py`
  - kéo `_action_check_goals`, `_action_browse`, `_action_learn`, `_action_reflect`, `_action_journal`, `_action_check_weather`, `_action_send_briefing`, `_action_reengage`, `_action_deep_reflect`, `_action_review_skill`, `_self_answer_quiz`, `_notify_discovery` sang support impl
  - giữ nguyên method seam cũ trong `HeartbeatScheduler`
  - khôi phục time-window methods (`_is_active_hours`, `_is_morning`, `_is_briefing_time`, `_is_reflection_time`, `_is_journal_time`) ngay trong `heartbeat.py` để giữ tương thích với test patch `app.engine.living_agent.heartbeat.datetime`

### 5. `emotion_engine.py` support extraction

- thêm `app/engine/living_agent/emotion_engine_support.py`
- `app/engine/living_agent/emotion_engine.py`
  - kéo prompt/persistence/serialization/circadian mapping sang support:
    - `build_behavior_modifiers_impl`
    - `compile_emotion_prompt_impl`
    - `restore_state_from_dict_impl`
    - `serialize_state_to_dict_impl`
    - `save_state_to_db_impl`
    - `load_state_from_db_impl`
    - `apply_circadian_modifier_impl`
  - giữ patch seam `datetime` trong `emotion_engine.py`

### 6. `course_generation.py` helper extraction

- thêm `app/api/v1/course_generation_support.py`
- `app/api/v1/course_generation.py`
  - kéo helper cuối file sang support:
    - `_utcnow`
    - `_derive_generation_thread_id`
    - `_compute_expand_progress`
    - `_without_failed_chapters`
    - `_cleanup_outline_source_file`
    - `_ensure_teacher_matches_auth`
    - `_require_generation_job_access`
    - `_normalize_approved_chapters`
    - `_merge_completed_chapters`
    - `_without_failed_chapter`
    - `_upsert_failed_chapter`
    - `_dedupe_failed_chapters`
    - `_build_partial_failure_summary`
  - giữ nguyên wrapper names để test/import cũ không gãy

## Verification

### Compile

- `py_compile` pass cho:
  - `supervisor.py`
  - `supervisor_runtime_support.py`
  - `graph.py`
  - `graph_runtime_bindings.py`
  - `_settings.py`
  - `_settings_feature_fields.py`
  - `heartbeat.py`
  - `heartbeat_action_runtime.py`
  - `emotion_engine.py`
  - `emotion_engine_support.py`
  - `course_generation.py`
  - `course_generation_support.py`

### Tests

- `test_supervisor_agent.py` + `test_supervisor_routing_reasoning.py`: `51 passed`
- `test_graph_routing.py`: `73 passed`
- graph-focused batch:
  - `test_graph_routing.py`
  - `test_sprint154_tech_debt.py`
  - `test_graph_visual_widget_injection.py`
  - `test_supervisor_agent.py`
  - result: `196 passed`
- config/living:
  - `test_config_validators.py`: `31 passed`
  - `test_living_agent_integration.py`: `28 passed`
- heartbeat/living:
  - `test_living_agent.py`
  - `test_living_agent_integration.py`
  - `test_sprint171_approval.py`
  - `test_sprint171b_messenger.py`
  - `test_sprint173_facebook_browse.py`
  - `test_sprint177_skill_learning.py`
  - `test_sprint208_living_wiring.py`
  - `test_sprint210_living_continuity.py`
  - `test_sprint213_soul_bridge.py`
  - result: `413 passed`
- emotion-engine-focused:
  - `test_living_agent.py`
  - `test_living_agent_integration.py`
  - `test_sprint176_soul_agi.py`
  - `test_sprint188_soul_deployment.py`
  - `test_sprint210c_relationship_tiers.py`
  - result: `246 passed`
- course generation:
  - `test_course_generation_flow.py`
  - `test_course_generation_source_preparation.py`
  - result: `25 passed`

## Metrics

### Sentrux

- Before overall campaign:
  - `Quality: 3581`
  - `Coupling: 0.36`
  - `Cycles: 8`
  - `God files: 9`
- After this round:
  - `Quality: 4509`
  - `Coupling: 0.30`
  - `Cycles: 7`
  - `God files: 1`
  - verdict: `No degradation detected`

### Notable line count drops

- `app/engine/multi_agent/graph.py`: about `491`
- `app/engine/multi_agent/supervisor.py`: about `742`
- `app/engine/living_agent/heartbeat.py`: `790 -> 586`
- `app/engine/living_agent/emotion_engine.py`: `792 -> 632`
- `app/api/v1/course_generation.py`: `786 -> 737`
- `app/core/config/_settings.py`: `780`

## Notes

- `test_sprint210d_llm_sentiment.py` và `test_sprint210f_memory_equity.py` vẫn bị chặn bởi drift môi trường local cũ:
  - `ImportError: cannot import name 'DeclarativeBase' from sqlalchemy.orm`
  - đây không phải regression do refactor round này
- `God files: 1` vẫn còn, nên phase refactor chưa hoàn tất. Ứng viên hợp lý tiếp theo:
  - `app/core/config/_settings.py`
  - hoặc `app/engine/agentic_rag/corrective_rag.py`
