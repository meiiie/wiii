# Wiii Identity V2 - P3B Analytics + Auth Cleanup

Date: 2026-03-23
Workspace: `E:\Sach\Sua\AI_v1`

## Summary

This loop continued the production-hardening path for `Identity V2` with two goals:

1. make Wiii web/admin analytics tell the correct story (`platform_role` first, legacy roles second)
2. ensure Wiii web auth state can retain canonical `platform_role` instead of only a compatibility role

LMS remains a host/plugin workspace. Wiii remains the canonical digital self.

## Changes

### 1. Admin analytics semantics cleaned up

Updated:

- `maritime-ai-service/app/api/v1/admin_analytics.py`
- `maritime-ai-service/tests/unit/test_sprint178_admin_flags_analytics.py`

Behavior:

- `GET /admin/analytics/users` now returns additive fields:
  - `role_distribution` (legacy compatibility)
  - `legacy_role_distribution`
  - `platform_role_distribution`
  - `organization_role_distribution`
- When `org_id` is present, `total_users`, `new_users_period`, and user growth are now org-aware instead of counting the whole system.
- `organization_role_distribution` is only meaningful inside an org scope and is returned as a separate overlay.

### 2. Wiii desktop admin analytics UI updated

Updated:

- `wiii-desktop/src/components/admin/AnalyticsTab.tsx`
- `wiii-desktop/src/api/types.ts`
- `wiii-desktop/src/__tests__/admin-panel.test.ts`
- `wiii-desktop/src/__tests__/analytics-tab.test.tsx`

Behavior:

- Analytics now presents:
  - `Loai tai khoan Wiii`
  - `Vai tro tuong thich (legacy)`
  - `Vai tro trong to chuc dang loc`
- Canonical account type is now the primary narrative on Wiii web.

### 3. OAuth auth state now retains platform role

Updated:

- `wiii-desktop/src/stores/auth-store.ts`
- `wiii-desktop/src/App.tsx`
- `wiii-desktop/src/components/auth/LoginScreen.tsx`
- `wiii-desktop/src/__tests__/auth-store.test.ts`

Behavior:

- `AuthUser` now keeps additive `platform_role?: "user" | "platform_admin"`.
- OAuth callback and magic-link login now preserve `platform_role` in client auth state.
- Compatibility `role` is still kept for legacy rails, but it is no longer the only identity signal in auth state.

### 4. Semantics docs/comments cleaned where they matter most

Updated:

- `maritime-ai-service/app/api/deps.py`
- `maritime-ai-service/app/api/v1/admin.py`

Meaning:

- admin-only APIs are documented as canonical Wiii platform-admin surfaces
- host-local LMS roles are explicitly not treated as global admin authority

## Verification

Backend:

- `python -m pytest maritime-ai-service/tests/unit/test_sprint178_admin_flags_analytics.py -q -p no:capture`
- Result: `38 passed`

Desktop:

- `npm exec vitest run src/__tests__/admin-panel.test.ts src/__tests__/auth-store.test.ts src/__tests__/analytics-tab.test.tsx`
- Result: `79 passed`

- `wiii-desktop/node_modules/.bin/tsc.cmd --noEmit -p wiii-desktop/tsconfig.json`
- Result: pass

## State After This Loop

Better:

- Wiii web is more explicit that global account type is `Wiii User` vs `Platform Admin`
- analytics no longer implies `teacher/student/admin` are Wiii-global roles
- client auth state is less likely to drift back into LMS-first semantics

Still not final:

- some docs/legacy compatibility rails still mention `X-Role` without the newer host-overlay explanation
- some client compatibility paths still need to carry `platform_role` deeper so fewer decisions rely on compatibility `role`
- connected workspace + host session UX still needs one more production polish loop

## Recommended Next Loop

1. continue documentation and compatibility cleanup around `X-Role` and trusted host headers
2. push more UI surfaces from `role` wording to `account type / org role / host role`
3. review `connected workspace` UX and `host_session` overlay end-to-end on Wiii web + LMS sidebar
