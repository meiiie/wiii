# Embedded Operator Platform V1 — 2026-03-22

## Scope
- Implement additive operator foundation for Wiii x LMS without breaking the existing document/course-generation pipeline.
- Ship `HostContext/HostCapabilities V2`, `OperatorSessionV1`, role/stage-aware LMS runtime skills, and direct-lane host action wiring.

## Implemented
### Backend
- Extended host context contracts with:
  - `user_role`
  - `workflow_stage`
  - `selection`
  - `editable_scope`
  - `entity_refs`
  - `HostCapabilities.version`
  - `HostCapabilities.surfaces`
- Added `OperatorSessionV1` and operator prompt compilation.
- Injected both `host_capabilities_prompt` and `operator_context_prompt` into:
  - direct lane
  - tutor
  - rag
  - memory
  - supervisor synthesis
- Wired host-declared actions into direct lane as generated LangChain tools.
- Added safe tool-name sanitization for dotted host action names.
- Preserved host action metadata:
  - `requires_confirmation`
  - `mutates_state`
  - `surface`
- Refreshed LMS adapter prompt formatting for:
  - course editor
  - analytics/admin
  - selection/editable scope/entity refs
  - visible action flags

### Runtime LMS skills
- Added new runtime product skills under `app/engine/context/skills/lms/`:
  - `teacher-course-editor`
  - `teacher-doc-to-course`
  - `teacher-lesson-experience`
  - `teacher-quiz-orchestrator`
  - `student-study-coach`
  - `org-admin-governance`
  - `system-admin-ops`
- Enabled role/stage filtering in `ContextSkillLoader`.

### Desktop / Host bridge
- Preserved backend-generated host action request IDs from SSE to postMessage bridge.
- Threaded `host_capabilities` into outgoing chat requests.
- Preserved operator-oriented page context fields in stores and request payloads:
  - `action`
  - `user_role`
  - `workflow_stage`
  - `selection`
  - `editable_scope`
  - `entity_refs`

### LMS frontend bridge
- Enriched capability declarations with:
  - `input_schema`
  - `requires_confirmation`
  - `mutates_state`
  - `surface`
  - `result_schema`
- Kept current teacher-first host actions as read/open surfaces, not silent data mutation.

## Verification
- Backend targeted tests:
  - `74 passed`
- Backend routing regression:
  - `test_graph_routing.py`: `36 passed`
- Desktop targeted tests:
  - `37 passed`
- Desktop TypeScript compile:
  - pass
- LMS Angular TypeScript compile:
  - pass

## Sanity checks
- Real runtime skill loading now resolves as intended:
  - `course_editor + teacher + authoring` → teacher operator skills
  - `lesson + student + learning` → student coach skills
  - `analytics + admin + governance` → governance/admin ops skills

## Notes
- This slice intentionally does **not** alter the Docling/course-generation core workflow.
- Current LMS host actions remain “open/preview/navigate” actions. True mutating publish/admin host actions can be added later behind stronger confirmation + audit policies.

## Next best steps
1. Add true structured host actions for lesson patch / quiz commit / publish with explicit preview-confirm-apply envelopes.
2. Add org-level capability policy overlays so different LMS orgs can whitelist/disable teacher/admin action families.
3. Add student-safe assignment/quiz coach behaviors on real page flows, including anti-answer leakage evals.
4. Generalize LMS host contract into a reusable host plugin kit for non-LMS web apps.
