# Wiii Identity V2 — P3A to P3D Hardening

Date: 2026-03-23
Workspace: `E:\Sach\Sua\AI_v1`
Status: local-green for targeted identity/host-session scope

## Decision checkpoint

This round hardens the architectural rule:

- Wiii web global identity:
  - `platform_role = user | platform_admin`
- Wiii org governance:
  - `organization_role` remains separate and scoped
- Host/plugin roles:
  - `teacher | student | lms_admin | lms_org_admin` are local overlays only
- LMS:
  - reference host/plugin, not Wiii's canonical identity source

In spirit this is similar to making LMS behave like an MCP-style host surface for Wiii, but it is deeper than plain MCP transport:

- durable connector grants
- live host session overlay
- page-aware context
- preview -> confirm -> apply action loop
- auditability
- living-agent identity boundary

## What changed

### 1. Canonical chat identity is now enforced on both sync and streaming

Files:

- `maritime-ai-service/app/api/v1/chat.py`
- `maritime-ai-service/app/api/v1/chat_stream.py`
- `maritime-ai-service/tests/unit/test_chat_identity_projection.py`

Effect:

- request body `user_id` and `role` no longer win over JWT/LMS-auth identity
- streaming now matches sync behavior
- Wiii web does not silently keep using stale local `user_id` in transport semantics

### 2. Host runtime now carries connector/workspace/org overlays end-to-end

Files:

- `maritime-ai-service/app/engine/context/host_context.py`
- `maritime-ai-service/app/engine/context/adapters/lms.py`
- `maritime-ai-service/tests/unit/test_sprint222_host_context.py`
- `wiii-desktop/src/stores/host-context-store.ts`
- `wiii-desktop/src/__tests__/host-context-store.test.ts`
- `wiii-desktop/src/__tests__/context-bridge.test.ts`
- `LMS_hohulili/fe/src/app/features/ai-chat/infrastructure/api/wiii-context.service.ts`
- `LMS_hohulili/fe/src/app/features/ai-chat/infrastructure/api/wiii-context.service.spec.ts`

Effect:

- LMS now sends additive overlay fields:
  - `connector_id`
  - `host_user_id`
  - `host_workspace_id`
  - `host_organization_id`
- Wiii desktop preserves them through the iframe bridge
- backend host-session prompt/runtime now has real workspace identity instead of only generic `host_type=lms`

### 3. Wiii web request shaping is cleaner in OAuth mode

Files:

- `wiii-desktop/src/hooks/useSSEStream.ts`
- `wiii-desktop/src/__tests__/auth-identity-ssot.test.ts`
- `wiii-desktop/src/App.tsx`
- `wiii-desktop/src/components/auth/LoginScreen.tsx`
- `wiii-desktop/src/components/settings/SettingsView.tsx`

Effect:

- OAuth mode now prefers canonical auth user ID over legacy settings `user_id`
- visible request display name prefers OAuth identity instead of stale local fallback
- host role remains a local overlay
- in Wiii web posture, compatibility role is reduced to:
  - `admin` only for `platform_admin`
  - otherwise `student` baseline
- settings connection flows no longer reintroduce legacy `X-Role` semantics in OAuth mode

## Verification

### Backend

- `33 passed`
  - `test_chat_identity_projection.py`
  - `test_identity_v2.py`
  - `test_user_router_identity_v2.py`
  - `test_connector_grants.py`
  - `test_sprint222_host_context.py`
- `23 passed`
  - `test_sprint159_lms_token_exchange.py`
- `15 passed`
  - `test_chat_request_flow.py`

### Wiii desktop

- `74 passed`
  - `auth-identity-ssot.test.ts`
  - `context-bridge.test.ts`
  - `host-context-store.test.ts`
- `43 passed`
  - `settings-page.test.ts`
- `tsc --noEmit`: pass

### LMS frontend

- `wiii-context.service.spec.ts`: `4 SUCCESS`
- `tsc --noEmit -p tsconfig.app.json`: pass

## What this means product-wise

### Wiii web

- user should no longer conceptually "be a teacher" or "be a student" as a global Wiii identity
- user is now closer to:
  - `Wiii User`
  - or `Platform Admin`

### LMS embedded sidebar

- Wiii still works as right sidebar
- Wiii can know:
  - current host = LMS
  - current connector = `maritime-lms`
  - current workspace/org
  - current local host role
  - current page/workflow/action surfaces
- but those facts do not redefine Wiii's core identity

## Remaining work before calling this production-complete

### P3B completion

- continue removing business branches that still think in `users.role = student|teacher|admin`
- especially old LMS data/dashboard routes and old admin/reporting assumptions

### P3C completion

- build first-class connector grant UX:
  - workspace cards
  - revoke/reconnect
  - last-used visibility

### P3D completion

- make host session lifecycle explicit:
  - host connected
  - host disconnected
  - stale session
  - capability refresh

### P3E completion

- polish Wiii web Settings/Profile into a full "Connected Workspaces" surface
- do not show host role as global identity
- do show:
  - workspace name
  - connector
  - recent capabilities
  - last connected/used

## Production recommendation

Safe to continue to next loop on top of this branch because:

- auth source-of-truth is cleaner
- streaming and sync now align
- host overlays survive bridge/runtime correctly
- LMS remains a plugin host, not an identity authority

Not yet "final form" because:

- full legacy role cleanup is still incomplete
- connected workspace UX is not yet fully productized
- some LMS-specific endpoints still use older header-era role assumptions
