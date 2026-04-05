# WIII IDENTITY V2 — Local Verification Snapshot

Date: 2026-03-23
Workspace: `E:\Sach\Sua\AI_v1`

## Goal

Verify the recent production-hardening work around:

- Wiii web canonical identity
- LMS/right-sidebar host overlay identity
- org permission semantics
- connected workspace / settings / host-context desktop surfaces

## Backend verification

Command:

```powershell
E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python.exe -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_identity_v2.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_user_router_identity_v2.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_chat_identity_projection.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint30_chat_api.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_organization_api.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint161_org_customization.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_lms_endpoint_identity_v2.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint159_lms_token_exchange.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint175_lms_integration.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint220c_lms_identity.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint157_google_oauth.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint192_auth_hardening.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint222_host_context.py `
  -q -p no:capture
```

Result:

- `331 passed, 1 skipped`

Coverage highlights:

- Identity V2 claims
- Google OAuth canonical projection
- LMS token exchange / LMS identity overlay
- chat sync/stream identity projection
- chat history self-service semantics
- org permissions / org customization
- host context injection for LMS-style plugin flows

## Desktop verification

Commands:

```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm exec vitest run src/__tests__/auth-identity-ssot.test.ts src/__tests__/auth-store.test.ts src/__tests__/auth-user.test.ts src/__tests__/embed-auth-validation.test.ts src/__tests__/embed-auth.test.ts src/__tests__/sprint160b-oauth.test.ts src/__tests__/org-store.test.ts src/__tests__/settings-page.test.ts src/__tests__/context-bridge.test.ts src/__tests__/host-context-actions.test.ts src/__tests__/host-context-store.test.ts src/__tests__/page-context-store.test.ts
npm exec tsc -- --noEmit
```

Results:

- `232 passed`
- TypeScript compile passed

Coverage highlights:

- Wiii web OAuth identity projection
- Embed/sidebar JWT projection
- org switching + org settings fetch
- connected workspaces/settings page
- page-context / host-context / right-sidebar bridge flow

## Confidence level

This is strong local evidence for the current identity hardening slice.

What is now validated well:

- Wiii web does not need to think of users as global `teacher/student/admin`
- LMS host role remains a local overlay
- platform admin remains platform-scoped
- connected workspace and host-context desktop surfaces still behave

What is still not fully proven by this batch:

1. Full browser E2E across:
   - Wiii web login
   - LMS token exchange
   - iframe/right-sidebar embed
   - returning to Wiii web in the same session
2. Staging/prod data migration behavior after applying all Identity V2 migrations

## Verdict

For the current slice, local verification is clean enough to call the work
`local-green` and ready for a stricter E2E/staging pass.
