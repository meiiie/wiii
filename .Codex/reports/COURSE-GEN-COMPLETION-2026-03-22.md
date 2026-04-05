# Course Generation Completion - 2026-03-22

## Scope completed in this pass

### Wiii backend
- Locked teacher/org ownership checks for course-generation outline, expand, retry, and status endpoints.
- Replaced non-resumable request-scoped `BackgroundTasks` flow with persisted in-process dispatch backed by startup recovery.
- Added atomic recovery claiming for `course_generation_jobs` so workers do not double-run the same job during startup.
- Added stale recovery lease handling for `RECOVERING_*` phases to avoid reclaiming freshly claimed jobs while still allowing recovery after crashes.
- Wired course-generation recovery into `app.main` startup and closed the dedicated asyncpg pool on shutdown.

### LMS backend
- Made chapter push idempotent by `courseId + orderIndex`.
- Fixed AI-generated lesson block contract to persist text content under `data.content` instead of `data.html`.
- Reworked quiz placeholder storage to structured metadata:
  - `kind`
  - `isQuizPlaceholder`
  - `message`
  - `ctaLabel`
  - `content` fallback
- Exposed `structuredContent` on section responses for downstream rendering/UX refinement.

### LMS frontend
- Extended learning section model with optional `structuredContent` so the placeholder metadata is available without another contract break later.

## Verification

### Python
- `pytest maritime-ai-service/tests/unit/test_course_generation_flow.py -q -p no:capture`
  - `12 passed`
- `py_compile`
  - `app/api/v1/course_generation.py`
  - `app/repositories/course_generation_repository.py`
  - `app/main.py`

### Java
- `mvn -q -Dtest=GenerateCourseFromAiUseCaseTest test`
  - pass
- `mvn -q -DskipTests compile`
  - pass

### TypeScript
- `npm exec tsc -- --noEmit`
  - pass

## Remaining Phase 2 items
- Replace in-process recovery/dispatch with a true worker/executor or Taskiq-based durable execution path if production load justifies it.
- Add first-class frontend rendering for quiz placeholder metadata if the LMS team wants a richer card instead of content fallback.
- Consider durable source-document storage for outline recovery beyond temp-file lifetime.

## Merge readiness
- Ownership enforcement: fixed
- Idempotent chapter push: fixed
- Crash recovery at startup: improved and wired
- AI lesson block contract mismatch (`html` vs `content`): fixed
- Quiz placeholder raw inline-style HTML coupling: reduced to structured metadata + content fallback
