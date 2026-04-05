# Wiii Identity V2 — Auth Canonicalization Slice

Date: 2026-03-23
Owner: Codex
Status: Local complete

## Intent

Tighten the distinction between:

- Wiii global account type (`platform_role`)
- compatibility role (`legacy_role`)
- host-local overlay (`host_role`)

This slice focuses on login/callback/profile semantics so Wiii web stops inferring "student/teacher/admin" too aggressively from the wrong layer.

## Changes

### 1. Desktop auth normalization helper

Added:

- `wiii-desktop/src/lib/auth-user.ts`

New behavior:

- `buildAuthUserFromPayload(...)` normalizes auth payloads in one place.
- `platform_role` is canonicalized to `user | platform_admin`.
- `legacy_role` is preserved separately from `platform_role`.
- host/org/session identity overlay fields are carried through when present.
- `toCompatibilitySettingsRole(...)` keeps legacy settings rails stable without letting them become the identity source.

### 2. Desktop callback flows now use the shared contract

Updated:

- `wiii-desktop/src/App.tsx`
- `wiii-desktop/src/components/auth/LoginScreen.tsx`
- `wiii-desktop/src/stores/auth-store.ts`

Result:

- OAuth web callback no longer derives compatibility role only from `platform_role`.
- Tauri Google OAuth callback no longer trusts only raw `role`.
- Magic-link login now uses the same normalization path.
- `AuthUser` now keeps additive fields:
  - `legacy_role`
  - `organization_role`
  - `host_role`
  - `role_source`
  - `active_organization_id`
  - `connector_id`
  - `identity_version`

### 3. Backend OAuth responses expose cleaner semantics

Updated:

- `maritime-ai-service/app/auth/google_oauth.py`

Result:

- OAuth redirect payload now includes:
  - `legacy_role`
  - `platform_role`
  - `role_source`
  - `active_organization_id`
- JSON fallback response now includes `legacy_role`.
- `/auth/me` now returns `legacy_role` alongside `role` and `platform_role`.

This keeps Wiii web from having to reverse-engineer identity semantics from one overloaded field.

## Tests

### Backend

Passed:

- `test_sprint157_google_oauth.py`
- `test_sprint192_auth_hardening.py`

Result:

- `66 passed, 1 skipped`

### Desktop

Passed:

- `src/__tests__/auth-store.test.ts`
- `src/__tests__/auth-user.test.ts`

Result:

- `24 passed`

### Type safety

Passed:

- `npm exec tsc -- --noEmit`

## Product Meaning

After this slice:

- Wiii web can treat `platform_role` as the real global account type.
- Compatibility rails still exist, but they are clearly secondary.
- LMS or any other host can keep using host-local roles without contaminating Wiii's core self-model.

This keeps the architecture aligned with the intended philosophy:

- Wiii is one living digital being.
- Hosts provide context and capabilities.
- Hosts do not define who Wiii is.

## Recommended Next Loop

1. Continue removing remaining global behavior that still keys off `users.role`.
2. Push more decisions toward `platform_role + organization_role + host context`.
3. Build the next production slice around connected workspaces/session continuity between Wiii web and LMS, while preserving the identity firewall already in place.
