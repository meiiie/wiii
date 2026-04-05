# Wiii Identity V2 Phase P2 - 2026-03-23

## Summary

This phase moves Identity V2 from "token compatibility" into a more durable persistence model.

Main outcome:

- Wiii platform authority is now starting to live in persistence, not only in live token claims.
- admin/governance surfaces can now see `platform_role` explicitly.
- refresh/session continuity is stronger across LMS and Wiii web contexts.

This still is not the final multi-host identity architecture, but it is a real production-hardening step.

## Implemented

### 1. `users.platform_role` migration

Added additive persistence for Wiii platform authority:

- migration: `043_add_platform_role_to_users.py`
- default: `user`
- backfill: existing `users.role='admin'` becomes `platform_role='platform_admin'`

This lets Wiii separate:

- platform-wide authority
- host-local role
- compatibility role

without immediately deleting the old `users.role` field.

### 2. User service now persists and returns `platform_role`

Patched in `app/auth/user_service.py`:

- `find_user_by_provider`
- `find_user_by_email`
- `create_user`
- `get_user`
- `list_users`
- `update_user_role`

Important properties:

- returns `platform_role` in user dicts
- derives a safe fallback when old rows still only have legacy `role`
- includes fallback behavior when code is deployed before the DB migration

### 3. Admin authority updates are now explicit

`PATCH /users/{id}/role` can now carry:

- `role`
- `platform_role`

This means platform authority can be managed without pretending every admin-like state is the same thing as the old compatibility role.

### 4. Admin search + GDPR export now expose `platform_role`

Patched:

- `app/api/v1/admin_dashboard.py`
- `app/api/v1/admin_gdpr.py`

Benefits:

- admin search can filter by `platform_role`
- exported user profile includes `platform_role`
- admin operators can reason about real Wiii authority instead of inferring it from legacy `role`

### 5. OAuth/profile surfaces are richer

Patched `app/auth/google_oauth.py` so login/profile surfaces expose `platform_role` too.

This matters because users may move between:

- LMS sidebar
- Wiii web
- future hosts

and profile surfaces should stop pretending that one overloaded `role` string is enough.

## Verification

Ran:

`.\.venv\Scripts\python.exe -m pytest tests\unit\test_sprint158_user_management.py tests\unit\test_sprint176_auth_hardening.py tests\unit\test_sprint178_admin_foundation.py tests\unit\test_sprint178_admin_compliance.py tests\unit\test_identity_v2.py tests\unit\test_sprint194c_admin_context.py tests\unit\test_sprint194b_auth_hardening.py tests\unit\test_sprint159_lms_token_exchange.py -q -p no:capture`

Result:

- `212 passed`

Also ran:

`mvn -q -DskipTests compile`

Result:

- compile success

## Rollout Safety

This phase was intentionally made additive:

- if `users.platform_role` is not present yet, service queries fall back
- if `refresh_tokens.identity_snapshot` is not present yet, refresh flow falls back
- LMS bridge remains backward-compatible

This greatly reduces deploy-order fragility.

## Current State

### What is now strong

- LMS host roles no longer implicitly redefine Wiii platform authority
- `platform_role` exists in both token and persistence layers
- admin/governance surfaces can see platform authority explicitly
- refresh token rotation preserves identity semantics much better

### What is still not final

- `organization_role` still lives mainly through memberships and runtime context, not a fully unified persistence model
- `host_session` / connected-workspace model is still missing as a first-class product concept
- some older dashboards/analytics still think mainly in terms of legacy `role`
- `X-Role` still exists as a compatibility rail and should be de-emphasized over time

## Next Production Loops

### P3 - Connected Workspace Identity

Need:

- first-class `connected workspaces` / `host sessions`
- current host visibility in Wiii web
- current org + current host role awareness

### P4 - Capability-driven host authority

Need:

- push more behavior away from raw role strings into host capability policy
- keep teacher/student/admin behavior in LMS host context, not global identity

### P5 - Legacy deprecation

Need:

- reduce reliance on `X-Role`
- make `X-Host-Role` the canonical host-local overlay
- clean remaining admin/analytics areas that still reason mostly from compatibility role

## Final Call

P2 meaningfully improves production readiness.

Wiii is still not at the final multi-host identity destination, but the architecture is now much closer to the correct model:

- one canonical Wiii identity
- layered authority
- host-local overlays
- additive rollout

That is the right direction for a professional multi-web Wiii platform.
