# Course Generation Hardening

Date: 2026-03-22  
Role: LEADER  
Scope: Immediate fixes agreed after final review

## Fixed Now

### 1. Wiii ownership and tenant enforcement

Implemented auth-backed access control for course-generation endpoints in:

- [course_generation.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/api/v1/course_generation.py)

Changes:

- Added `Depends(require_auth)` to `outline`, `expand`, `retry`, and `status`.
- Enforced `teacher_id == auth.user_id` for non-admin users.
- Enforced job access by stored `teacher_id`.
- Enforced org isolation by comparing job `organization_id` with `auth.organization_id` for non-admin users.
- Stored `organization_id` from authenticated context instead of trusting free-form route/body data.

Result:

- A user can no longer expand/retry/read another teacher’s generation job just by knowing `generation_id`.
- Org-scoped jobs now require matching authenticated org context.

### 2. LMS idempotent chapter push

Implemented duplicate-chapter protection for AI chapter push in:

- [ChapterRepositoryPort.java](E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/course_authoring/domain/repository/ChapterRepositoryPort.java)
- [ChapterJpaRepository.java](E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/course_authoring/infrastructure/persistence/repository/ChapterJpaRepository.java)
- [ChapterRepositoryAdapter.java](E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/course_authoring/infrastructure/persistence/ChapterRepositoryAdapter.java)
- [GenerateCourseFromAiUseCase.java](E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/course_authoring/application/usecase/GenerateCourseFromAiUseCase.java)

Changes:

- Added lookup by `courseId + orderIndex`.
- Before inserting a new AI chapter, the use case checks whether that chapter already exists.
- If present, it returns the existing chapter with status `ALREADY_EXISTS` and skips chapter/lesson/section creation.

Result:

- Retries after timeout or duplicate delivery no longer create duplicate chapters for the same `orderIndex`.

## Added/Updated Tests

### Wiii

- [test_course_generation_flow.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_course_generation_flow.py)

Added coverage for:

- teacher/auth mismatch rejection
- cross-org job rejection
- admin bypass behavior
- expand/retry flow guards already added in prior pass

### LMS

- [GenerateCourseFromAiUseCaseTest.java](E:/Sach/Sua/LMS_hohulili/backend/src/test/java/com/example/lms/course_authoring/application/usecase/GenerateCourseFromAiUseCaseTest.java)

Added coverage for:

- existing chapter at same `orderIndex` returns `ALREADY_EXISTS`
- no new chapter/lesson/content creation occurs on duplicate push

## Verification

### Wiii

- `pytest test_course_generation_flow.py test_sprint222_host_context.py test_sprint223_structured_context.py`
  - Result: `42 passed`
- `py_compile app/api/v1/course_generation.py`
  - Result: pass

### LMS

- `mvn -q "-Dtest=CreateChapterUseCaseV3Test,GenerateCourseFromAiUseCaseTest" test`
  - Result: pass
- `mvn -q -DskipTests compile`
  - Result: pass

## Still Deferred

These remain intentionally deferred from this immediate hardening pass:

1. Resumable background execution beyond FastAPI `BackgroundTasks`
2. Refactor `QUIZ_PLACEHOLDER` away from HTML coupling
3. Stronger DB-level idempotency/uniqueness if the team wants race-proof guarantees rather than application-level dedupe only

## Recommendation

This feature is materially safer now for staging and merge-candidate use.

The two highest-priority immediate risks from the previous review are now addressed:

- ownership/tenant escape
- duplicate chapter creation on retry
