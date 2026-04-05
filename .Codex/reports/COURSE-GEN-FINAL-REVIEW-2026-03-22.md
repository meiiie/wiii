# AI Course Generation Final Review

Date: 2026-03-22  
Role: LEADER (Codex)  
Scope: Final review and hardening for "AI Course Generation from Documents" across LMS + Wiii AI

## Executive Summary

The feature is materially closer to mergeable after this review pass.

I fixed the most immediate correctness issues in the Wiii workflow and the LMS/Wiii integration bridge:

- Wiii now persists `markdown` and `section_map` from outline phase so expand/retry do not lose grounded source context.
- Docling parsing and LMS push now have async-safe paths instead of blocking the event loop.
- Expand/retry logic now normalizes approved chapter indices, preserves partial failures, and avoids stale-state overwrites on retry.
- LMS frontend now preserves `generate_lesson` intent, uses the correct `/teacher/courses/:id/editor/*` route family, validates screenshot bridge origin/source, and cleans up resize listeners.
- LMS backend now fails closed when the service token is missing, and chapter creation no longer bypasses ownership by hardcoding admin mode.

## Files Changed In This Review

### Wiii AI

- [course_generation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py)
- [course_generation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/workflows/course_generation.py)
- [push_service.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/integrations/lms/push_service.py)
- [docling_parser.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/adapters/docling_parser.py)
- [host_context.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/context/host_context.py)
- [lms.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/context/adapters/lms.py)
- [page-context-store.ts](E:/Sach/Sua/AI_v1/wiii-desktop/src/stores/page-context-store.ts)
- [test_course_generation_flow.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_course_generation_flow.py)

### LMS Frontend

- [wiii-context.service.ts](E:/Sach/Sua/LMS_hohulili/fe/src/app/features/ai-chat/infrastructure/api/wiii-context.service.ts)
- [chat-widget.component.ts](E:/Sach/Sua/LMS_hohulili/fe/src/app/features/ai-chat/presentation/components/chat-widget/chat-widget.component.ts)
- [course-curriculum.component.ts](E:/Sach/Sua/LMS_hohulili/fe/src/app/features/teacher/course-editor/pages/course-curriculum/course-curriculum.component.ts)

### LMS Backend

- [WiiiServiceAuthFilter.java](E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/shared/integration/WiiiServiceAuthFilter.java)
- [GenerateCourseFromAiUseCase.java](E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/course_authoring/application/usecase/GenerateCourseFromAiUseCase.java)

## New Regression Coverage

Added [test_course_generation_flow.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_course_generation_flow.py) to lock in:

- `ExpandRequest` dedupe and negative-index rejection
- `_normalize_approved_chapters()` out-of-range rejection
- LMS host-context bridge preserving `action` and extra metadata
- LMS adapter prompt injection of `requested_action=generate_lesson`
- `_run_expand_phase()` retaining partial failures and surfacing summary error
- `_run_retry_chapter()` merging latest repository state instead of clobbering stale state

## Verification Run

### Wiii AI

- `python -m pytest maritime-ai-service/tests/unit/test_course_generation_flow.py -q -p no:capture`
  - Result: `7 passed`
- `python -m pytest maritime-ai-service/tests/unit/test_sprint222_host_context.py maritime-ai-service/tests/unit/test_sprint223_structured_context.py -q -p no:capture`
  - Result: `32 passed`
- `python -m py_compile` on the changed Wiii files
  - Result: pass

### LMS

- `cd fe && npx tsc --noEmit`
  - Result: pass
- `cd backend && mvn -q -DskipTests compile`
  - Result: pass

## Fixed Findings

### Fixed

1. Source-grounding was lost after outline phase on Wiii.
2. Docling conversion and LMS push were blocking async execution paths.
3. Retry logic used stale job snapshots and could overwrite newer chapter state.
4. Partial chapter failures could be swallowed without being preserved in job state.
5. LMS frontend routed to the wrong teacher editor URL shape.
6. `generate_lesson` sidebar intent was dropped before reaching Wiii.
7. Screenshot bridge accepted arbitrary `postMessage` senders and replied with wildcard origin.
8. LMS resize listeners leaked if the page unmounted mid-drag.
9. LMS integration auth failed open when `wiii.service-token` was blank.
10. LMS AI chapter push bypassed ownership guard by forcing admin mode.
11. Title length validation in LMS AI requests could exceed DB constraints and fail late.

## Remaining Risks Before Production Merge

These are still open and should be called out explicitly in merge notes:

1. Wiii course-generation jobs still do not enforce ownership or tenant scoping on `GET /expand /retry /status`.
   - The repository already stores `organization_id`, but the API does not enforce caller/job matching yet.
2. Wiii crash recovery is still only partial.
   - Job state is persisted, but work is still executed via FastAPI `BackgroundTasks`; there is no resume worker or recovery loop after process restart.
3. LMS chapter push is still not idempotent.
   - Retries can duplicate chapters if the same push is replayed after timeout or ambiguous failure.
4. Wiii course-generation tools remain agent-facing stubs.
   - They do not yet start the real persisted workflow.
5. Some enum/type mapping remains permissive and can drift from the design contract.

## Merge Readiness

My recommendation is:

- Safe to merge for continued staging/integration testing
- Not yet ideal for full production rollout without tracking the 5 residual risks above

If the team wants the strictest bar, I would require at least one more phase before full production:

1. add Wiii job ownership enforcement
2. define crash-recovery strategy beyond `BackgroundTasks`
3. make LMS chapter push idempotent

## Coordination Note For Claude Team

This pass focused on code-quality and edge-case hardening, not architecture redesign.

The design spec still stands. The remaining issues are mostly production-hardening concerns:

- auth/ownership
- resumability
- idempotency
- contract strictness

Nothing in this review suggests the feature should be re-architected before the next merge candidate.
