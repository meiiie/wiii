# WIII IDENTITY V2 P3C — Embed + Interaction Cleanup

Date: 2026-03-23
Workspace: `E:\Sach\Sua\AI_v1`

## Summary

This loop tightened the boundary between:

- `Wiii web canonical identity`
- `host-local overlay identity` for LMS/right-sidebar embed
- `conversation compatibility role` used by legacy prompt paths

The goal was to stop plain Wiii web sessions from silently inheriting LMS-era
role semantics while still preserving the right host-local behavior when Wiii
is embedded into LMS.

## What changed

### 1. Desktop/embed identity projection

Updated:

- `wiii-desktop/src/lib/auth-user.ts`
- `wiii-desktop/src/EmbedApp.tsx`
- `wiii-desktop/src/__tests__/auth-user.test.ts`
- `wiii-desktop/src/__tests__/auth-identity-ssot.test.ts`

Key changes:

- Added JWT decoding helper that understands Identity V2 claims and preserves:
  - `legacy_role`
  - `platform_role`
  - `host_role`
  - `role_source`
  - `active_organization_id`
  - `connector_id`
  - `identity_version`
- Embed/sidebar flow now builds the same `AuthUser` shape as Wiii web instead
  of using a stripped-down `{ id, email, name, role }` projection.
- Embed compatibility role now prefers local host overlay signals:
  - `config.role`
  - `user.host_role`
  - `user.legacy_role`
- `org_admin` / `owner` now map to `teacher` only as a compatibility role,
  not as a platform identity.

### 2. Backend conversational role projection

Updated:

- `maritime-ai-service/app/core/security.py`
- `maritime-ai-service/app/api/v1/chat.py`
- `maritime-ai-service/app/api/v1/chat_stream.py`
- `maritime-ai-service/tests/unit/test_chat_identity_projection.py`

Key changes:

- Added `resolve_interaction_role(auth)` to separate:
  - host-local role overlays that should affect the turn
  - platform identity that should not rewrite Wiii's general stance
- New behavior:
  - if a host role exists, it wins for the turn
  - LMS/API-key compatibility flows may keep their explicit local role
  - plain Wiii web JWT/Google sessions fall back to neutral `student`
- This prevents a `platform_admin` Wiii account from automatically becoming an
  `admin persona` during normal chat just because legacy compatibility data is
  present.
- `chat.py` and `chat_stream.py` now use the same host-aware interaction-role
  projection for request canonicalization.
- `get_context_info()` system-prompt preview now uses the same resolved
  interaction role instead of raw `auth.role`.

## Verification

### Backend

Command:

```powershell
E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python.exe -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_chat_identity_projection.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint157_google_oauth.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint192_auth_hardening.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_lms_endpoint_identity_v2.py `
  -q -p no:capture
```

Result:

- `76 passed, 1 skipped`

### Desktop

Commands:

```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm exec vitest run src/__tests__/auth-user.test.ts src/__tests__/auth-store.test.ts src/__tests__/auth-identity-ssot.test.ts
npm exec tsc -- --noEmit
```

Results:

- `75 passed`
- TypeScript compile passed

## Production meaning

This does **not** finish the whole production migration, but it removes one of
the most dangerous identity drifts:

- Wiii web account type no longer has to behave like LMS role semantics
- LMS sidebar keeps local role/context behavior without owning Wiii's identity
- host-role remains a local overlay, not a platform truth

## Remaining gaps

1. Continue replacing raw `auth.role` usage in older endpoints where behavior
   should really depend on:
   - `platform_role`
   - `organization_role`
   - `host_context` / host overlay
2. Finish the `connected workspace` UX so Wiii web presents LMS as a connected
   workspace instead of an identity mode.
3. Add E2E continuity tests that cover:
   - Wiii web login
   - LMS token exchange
   - embed/sidebar chat
   - return to Wiii web with the same canonical identity

## Decision status

- `platform_role = user | platform_admin` remains the right canonical model.
- `teacher/student/admin/org_admin` remain host- or org-local overlays.
- Wiii remains one living digital being; hosts/workspaces add context and
  capabilities, not a new personality.
