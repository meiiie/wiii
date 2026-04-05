# Wiii Identity V2 P3B - LMS Endpoint Cleanup

Date: 2026-03-23

## Summary

This phase cleaned up the remaining LMS data/dashboard endpoints that still
treated `X-Role` and `X-User-ID` as if LMS were the source of truth for user
identity.

Wiii now treats:

- `platform_role` as the global Wiii role (`user | platform_admin`)
- `organization_role` as Wiii org governance
- `host_role` as a local overlay from the current host/plugin session

LMS remains a host/plugin surface, not the identity authority for Wiii.

## What Changed

### 1. LMS data endpoints now use canonical auth

Files:

- `maritime-ai-service/app/api/v1/lms_data.py`

Changes:

- Switched endpoint auth from raw `X-User-ID` / `X-Role` headers to `RequireAuth`
- Added host-overlay role resolution:
  - platform admin bypass
  - teacher/admin/org_admin host overlays allowed
  - student self-access resolved via `resolve_lms_identity(...)`
- Added connector/workspace binding checks so a student cannot use an unrelated
  LMS connector silently
- Preserved `lms_service` trusted proxy behavior for direct LMS backend calls

### 2. LMS dashboard endpoints now use canonical auth

Files:

- `maritime-ai-service/app/api/v1/lms_dashboard.py`

Changes:

- Switched endpoint auth from raw `X-Role` to `RequireAuth`
- Teacher/admin access is now derived from `host_role` overlay or
  `platform_admin`
- Org overview allows:
  - platform admin
  - LMS host admin/org_admin
  - Wiii `organization_role in {admin, owner}` as additive governance
- Connector resolution now prefers explicit header, then auth connector, then
  safe default

### 3. Profile semantics are clearer for client code

Files:

- `maritime-ai-service/app/auth/user_router.py`
- `wiii-desktop/src/api/types.ts`

Changes:

- Added additive `legacy_role` field to profile/admin-context responses
- This clarifies that `role` is compatibility baggage, while `platform_role`
  is the real Wiii-global identity signal

## Verification

- `test_sprint175_lms_integration.py`
- `test_lms_endpoint_identity_v2.py`
- `test_sprint220c_lms_identity.py`
- `test_sprint159_lms_token_exchange.py`
- `test_user_router_identity_v2.py`

Result:

- `113 passed`
- `wiii-desktop` TypeScript compile: pass

## Architectural Note

This direction is MCP-like in spirit, but deeper than plain MCP:

- durable connector grants
- host session overlay
- page-aware context
- preview/confirm/apply actions
- audit trails
- identity separation between platform/org/host

In other words: LMS is not just "a tool". It is becoming a governed host
surface that Wiii can work through safely.

## Remaining Production Loops

1. Continue retiring `users.role` as a source-of-truth mental model.
2. Keep shifting behavior to `capabilities + host context`, not role strings.
3. Clean legacy admin/user management surfaces that still speak in
   `student/teacher/admin` terms when they really mean:
   - platform role
   - org role
   - host overlay role
4. Add broader E2E coverage for Wiii web <-> LMS plugin identity continuity.
