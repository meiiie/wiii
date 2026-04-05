# Wiii Identity V2 Phase P1 - 2026-03-23

## Scope

This pass continues the Identity V2 migration beyond the initial compatibility layer.

The focus here was:

- preserve additive identity across refresh-token rotation
- expose clearer identity facets back to product/admin surfaces
- keep rollout backward-compatible with databases that have not migrated yet

## Implemented

### 1. Refresh-token continuity for Identity V2

`refresh_tokens` now stores a compact `identity_snapshot` alongside the existing refresh-token data.

Stored fields:

- `role`
- `platform_role`
- `organization_role`
- `host_role`
- `role_source`
- `active_organization_id`
- `connector_id`
- `identity_version`

This lets refreshed access tokens preserve the same host-local and platform-scoped identity context instead of silently collapsing back to legacy `users.role`.

Files:

- `maritime-ai-service/app/auth/token_service.py`
- `maritime-ai-service/alembic/versions/042_add_identity_snapshot_to_refresh_tokens.py`

### 2. Backward-compatible SQL fallback

Rollout is additive.

If the new DB column is not present yet:

- refresh-token insert falls back to the legacy insert
- refresh-token lookup falls back to the legacy select

This avoids the dangerous deploy order problem where new code would otherwise break refresh flows until the migration is applied.

### 3. Admin context now exposes identity facets

`/users/me/admin-context` now returns additive identity fields:

- `platform_role`
- `organization_role`
- `host_role`
- `role_source`
- `active_organization_id`
- `connector_id`
- `identity_version`
- `legacy_role`

This is important because Wiii web and future multi-host UI should not have to infer identity semantics from a single overloaded `role` string.

File:

- `maritime-ai-service/app/auth/user_router.py`

### 4. Self-profile now carries current identity overlay

`/users/me` and `PATCH /users/me` now overlay the current authenticated identity context onto the user profile response, instead of only returning the DB user row.

This means a user can now see:

- who they are canonically in Wiii
- what host role is active in the current session
- what org context is active

without the host redefining Wiii's core identity.

## Verification

Ran:

`.\.venv\Scripts\python.exe -m pytest tests\unit\test_identity_v2.py tests\unit\test_sprint159_lms_token_exchange.py tests\unit\test_sprint176_auth_hardening.py tests\unit\test_sprint181_org_admin.py tests\unit\test_sprint192_auth_hardening.py tests\unit\test_sprint194b_auth_hardening.py tests\unit\test_sprint194c_admin_context.py tests\unit\test_organization_api.py tests\unit\test_course_generation_flow.py tests\unit\test_auth_ownership.py -q -p no:capture`

Result:

- `259 passed`

Also ran:

`mvn -q -DskipTests compile`

Result:

- compile success

## Current Position

After P0 + P1:

- LMS no longer implicitly grants Wiii platform-admin authority
- Wiii can preserve additive identity through refresh-token rotation
- product/admin surfaces can read richer identity semantics
- rollout remains backward-compatible

## What Still Remains

### P2 - Persistent role model cleanup

Still needed:

- stop treating `users.role` as a durable source of truth
- add a first-class persistence model for platform/org/host identity layers

### P3 - Connected workspaces / host session

Still needed:

- first-class multi-host session model
- Wiii web UX for connected workspaces/hosts
- active org + active host visibility

### P4 - Legacy deprecation

Still needed:

- de-emphasize `X-Role`
- treat `X-Host-Role` as canonical host-local role
- clean lower-risk behavior gates that still inspect legacy `role`

## Product Meaning

This phase matters because it moves Wiii closer to the right mental model:

- Wiii is one living multi-platform agent
- LMS is one connected host
- identity is layered, not overwritten

That is the foundation needed for a real multi-web Wiii platform.
