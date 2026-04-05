# Embedded Operator Timeline + Preview Diff Hardening

Date: 2026-03-23
Workspace: `E:\Sach\Sua\AI_v1`

## Scope

This slice completes the next teacher/admin-facing layer on top of the host-action operator flow:

- clearer visual preview for `lesson patch`, `quiz commit`, and `publish`
- admin-visible host-action timeline
- tighter verification across Wiii backend, Wiii desktop, and LMS frontend

The work remained additive and identity-safe:

- LMS stays a host/plugin context
- Wiii keeps its own character/soul boundaries
- no changes were made to the Docling-based document ingestion or course-generation pipeline semantics

## What Changed

### 1. Admin host-action timeline

Added a dedicated host-action audit view in the Wiii desktop admin UI:

- new `host_actions` audit sub-tab
- timeline rendering for preview/apply/publish events
- event metadata shown in a teacher/admin-readable format:
  - preview kind
  - summary
  - action
  - target
  - surface
  - request id
  - organization id
  - changed fields
  - question counts where present

Backend admin audit filtering now supports:

- `provider`
- `org_id`

This allows the desktop to query only `provider=host_action` and render a clean timeline without inventing a separate audit storage path.

### 2. Teacher preview diff quality

Extended LMS-side preview payloads so the teacher sees meaningful before/after detail instead of a thin action shell:

- `lesson patch` preview now includes:
  - `lesson_before`
  - `lesson_after`
  - title
  - description
  - content excerpt
- `quiz commit` preview now includes:
  - `quiz_plan`
  - mode
  - title
  - description
  - question count
  - time limit
  - attempts
  - passing score
- `publish` preview now includes:
  - `publish_plan`
  - quiz id
  - lesson id
  - title
  - status

The Wiii desktop preview panel now renders those details directly:

- lesson before/after cards
- quiz plan summary block
- publish plan summary block

### 3. Contract continuity

The SSE bridge and audit bridge now persist the richer preview metadata:

- `request_id`
- `summary`
- lesson snapshots
- quiz plan
- publish plan

This keeps the preview surface and audit surface semantically aligned instead of forcing the UI to reconstruct state later.

## Files Touched

### Wiii backend

- `maritime-ai-service/app/api/v1/admin_audit.py`
- `maritime-ai-service/tests/unit/test_sprint178_admin_compliance.py`

### Wiii desktop

- `wiii-desktop/src/api/admin.ts`
- `wiii-desktop/src/stores/admin-store.ts`
- `wiii-desktop/src/components/admin/AuditLogsTab.tsx`
- `wiii-desktop/src/hooks/useSSEStream.ts`
- `wiii-desktop/src/components/layout/PreviewPanel.tsx`
- `wiii-desktop/src/__tests__/preview-panel.test.ts`
- `wiii-desktop/src/__tests__/admin-panel.test.ts`
- `wiii-desktop/src/__tests__/admin-panel-complete.test.ts`

### LMS frontend

- `LMS_hohulili/fe/src/app/features/ai-chat/infrastructure/api/wiii-context.service.ts`
- `LMS_hohulili/fe/src/app/features/ai-chat/infrastructure/api/wiii-context.service.spec.ts`

## Verification

### Backend targeted pytest

Command:

```powershell
cd E:\Sach\Sua\AI_v1\maritime-ai-service
.\.venv\Scripts\python.exe -m pytest tests/unit/test_sprint178_admin_compliance.py tests/unit/test_host_action_audit.py tests/unit/test_sprint222_host_context.py tests/unit/test_sprint222_graph_injection.py tests/unit/test_sprint222b_action_tools.py tests/unit/test_sprint234_capability_policy.py tests/unit/test_sprint234_student_safe_coach.py -q -p no:capture
```

Result:

- `89 passed`

### Wiii desktop TypeScript

Command:

```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm exec tsc -- --noEmit
```

Result:

- pass

### Wiii desktop targeted Vitest

Command:

```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npx vitest run src/__tests__/admin-panel.test.ts src/__tests__/admin-panel-complete.test.ts src/__tests__/preview-panel.test.ts src/__tests__/preview-cards.test.ts
```

Result:

- `155 passed`

### LMS frontend TypeScript

Command:

```powershell
cd E:\Sach\Sua\LMS_hohulili\fe
npm exec tsc -- --noEmit
```

Result:

- pass

### LMS Angular browser spec

Command:

```powershell
cd E:\Sach\Sua\LMS_hohulili\fe
npm exec ng test -- --watch=false --browsers=ChromeHeadless --include=src/app/features/ai-chat/infrastructure/api/wiii-context.service.spec.ts
```

Result:

- `3 SUCCESS`

## Outcome

Local status for this slice is now:

- preview/apply/publish flows are easier to inspect visually
- admin can review host-action activity through a real timeline UI
- preview metadata is richer and consistent across preview and audit surfaces
- no regression detected in the current host-action/operator foundation

## Remaining Good Next Steps

1. Add a dedicated LMS-side diff renderer for lesson block-level changes, not only excerpt snapshots.
2. Persist host-action audit events into a first-class table if filtering/query volume outgrows the current auth-event provider pattern.
3. Add end-to-end UI tests for the full `preview -> confirm -> apply` teacher loop across iframe bridge boundaries.
4. Introduce org-admin audit filtering and saved views so organization operators can inspect only their own courses/actions.
