# Embedded Operator Preview + Audit Hardening — 2026-03-23

## Scope
- Real preview panel UI for teacher-facing LMS host actions
- Audit logging for `preview_created`, `apply_confirmed`, `publish_confirmed`
- LMS-side browser tests for `lesson patch`, `quiz commit`, `quiz publish`

## What Changed

### 1. Wiii desktop preview panel now renders host action previews clearly
- Added a dedicated `host_action` preview type and card renderer.
- `useSSEStream` now turns LMS host-action preview responses into actual preview items and opens the preview panel automatically.
- Preview metadata shown in the panel includes:
  - preview kind
  - target label
  - lesson / quiz / course ids when present
  - changed fields
  - question count
  - preview token
  - next step / confirmation hint

### 2. Audit trail for operator actions
- Added backend endpoint: `POST /api/v1/host-actions/audit`
- Added backend helper to persist audit events through the existing auth audit channel.
- Events currently covered:
  - `host_action.preview_created`
  - `host_action.apply_confirmed`
  - `host_action.publish_confirmed`
- Preview tokens are hashed before persistence.

### 3. LMS host action contract hardened
- `WiiiContextService` preview/apply methods now return richer semantic payloads for UI and follow-up context:
  - `lesson_title`
  - `quiz_title`
  - `question_count`
  - `course_id`
  - `target_label`
- Fixed Angular-compiler issues in `wiii-context.service.ts`:
  - corrected deep relative imports
  - replaced index-signature property access with bracket access where required

### 4. LMS tests added
- New Angular spec:
  - `wiii-context.service.spec.ts`
- Covered flows:
  - preview + apply lesson patch
  - preview + commit quiz
  - preview + publish quiz

## Verification

### Backend
Command:
```powershell
cd E:\Sach\Sua\AI_v1\maritime-ai-service
.\.venv\Scripts\python.exe -m pytest tests/unit/test_host_action_audit.py tests/unit/test_sprint222_host_context.py tests/unit/test_sprint222_graph_injection.py tests/unit/test_sprint222b_action_tools.py tests/unit/test_sprint234_capability_policy.py tests/unit/test_sprint234_student_safe_coach.py -q -p no:capture
```
Result:
- `58 passed`

### Wiii desktop
Commands:
```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npx vitest run src/__tests__/host-context-actions.test.ts src/__tests__/host-action-sse.test.ts src/__tests__/preview-panel.test.ts src/__tests__/preview-cards.test.ts
npm exec tsc -- --noEmit
```
Results:
- `65 passed`
- TypeScript compile passed

### LMS frontend
Commands:
```powershell
cd E:\Sach\Sua\LMS_hohulili\fe
npm exec tsc -- --noEmit
npm exec ng test -- --watch=false --browsers=ChromeHeadless --include=src/app/features/ai-chat/infrastructure/api/wiii-context.service.spec.ts
```
Results:
- TypeScript compile passed
- Angular browser test: `3 SUCCESS`

## Important Note
- `ChromeHeadlessCI` currently failed to launch when passed explicitly to `ng test`, even though `karma.conf.js` defines it.
- `ChromeHeadless` works correctly on this machine and was used to verify the new LMS spec.
- This looks like a local Karma/Angular launcher resolution issue rather than a failure in the preview/apply/publish flow itself.

## Files Touched

### Wiii backend
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\models\schemas.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\context\host_action_audit.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\host_actions.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\__init__.py`
- `E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_host_action_audit.py`

### Wiii desktop
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\api\types.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\api\host-actions.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\hooks\useSSEStream.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\previews\HostActionPreviewCard.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\previews\index.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\layout\PreviewPanel.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\preview-cards.test.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\preview-panel.test.ts`

### LMS frontend
- `E:\Sach\Sua\LMS_hohulili\fe\src\app\features\ai-chat\infrastructure\api\wiii-context.service.ts`
- `E:\Sach\Sua\LMS_hohulili\fe\src\app\features\ai-chat\infrastructure\api\wiii-context.service.spec.ts`

## Outcome
- Teacher-facing preview/apply/publish flows are now visible, auditable, and test-covered.
- LMS remains a host/plugin layer only; none of these changes alter Wiii's identity model.
- Doc/course-generation pipeline was not modified by this slice.
