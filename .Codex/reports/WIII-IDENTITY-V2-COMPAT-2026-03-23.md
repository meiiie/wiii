# Wiii Identity V2 Compatibility Layer - 2026-03-23

## Summary

This phase implements the first safe, additive step toward a real multi-host identity model:

- Wiii remains the canonical digital being.
- LMS is treated as a host/plugin surface, not as a source of platform authority.
- Host-local roles now travel as context (`host_role`) instead of silently redefining Wiii's global authority.
- Real Wiii platform-admin checks no longer depend on legacy `role == "admin"` in the critical API/auth paths that matter most.

This is **not** the final identity migration. It is a compatibility layer that lets us move forward without breaking the current LMS connection, course generation, or embedded-operator work.

## What Changed

### 1. Identity V2 additive claims

JWT payloads and authenticated user state now support additive identity fields:

- `platform_role`
- `organization_role`
- `host_role`
- `role_source`
- `active_organization_id`
- `connector_id`
- `identity_version`

Legacy `role` remains for compatibility, but it is now treated as a compatibility field, not the only truth.

Files:

- `maritime-ai-service/app/core/security.py`
- `maritime-ai-service/app/auth/token_service.py`

### 2. LMS roles are now host-local by default

LMS token exchange no longer lets host roles silently become platform authority:

- LMS `teacher` -> host role `teacher`, compatibility role `teacher`
- LMS `admin` -> host role `admin`, compatibility role `teacher`
- LMS `org_admin` -> host role `org_admin`, compatibility role `teacher`
- LMS `student` -> host role `student`, compatibility role `student`

This means:

- Wiii still understands that the user is a teacher/admin/org admin **inside LMS**
- but Wiii does **not** accidentally treat them as a global Wiii platform admin

Files:

- `maritime-ai-service/app/auth/lms_token_exchange.py`
- `E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/ai_assistant/infrastructure/wiii/WiiiTokenExchangeAdapter.java`
- `E:/Sach/Sua/LMS_hohulili/backend/src/main/java/com/example/lms/ai_assistant/infrastructure/wiii/WiiiChatAdapter.java`

### 3. Canonical platform-admin checks are now explicit

Critical authorization paths were changed away from raw `auth.role == "admin"` and now use a real helper:

- `is_platform_admin(...)`

Patched areas:

- admin dependencies
- organizations APIs
- course-generation ownership checks
- insights/memories/threads/chat-history ownership checks
- soul bridge/admin context paths

Files include:

- `maritime-ai-service/app/api/deps.py`
- `maritime-ai-service/app/api/v1/admin.py`
- `maritime-ai-service/app/api/v1/organizations.py`
- `maritime-ai-service/app/api/v1/course_generation.py`
- `maritime-ai-service/app/api/v1/insights.py`
- `maritime-ai-service/app/api/v1/memories.py`
- `maritime-ai-service/app/api/v1/threads.py`
- `maritime-ai-service/app/api/v1/chat_history_endpoint_support.py`
- `maritime-ai-service/app/api/v1/knowledge_visualization.py`
- `maritime-ai-service/app/api/v1/org_knowledge.py`
- `maritime-ai-service/app/api/v1/soul_bridge.py`
- `maritime-ai-service/app/auth/user_router.py`

### 4. Direct-call auth safety improved

`require_auth()` now normalizes dependency-marker defaults for direct test/internal calls.

This fixed a subtle bug where omitted `Header(...)` defaults were truthy objects, causing:

- `X-Host-Role` fallback to misbehave
- LMS service auth to downgrade valid teacher-host requests to student in direct-call tests

This is especially important because this code is heavily exercised in unit tests and internal flows, not only through live FastAPI request injection.

### 5. SSE/chat proxy alignment fixed on the LMS side

The LMS streaming adapter still had one legacy `X-Role` mapping path that was inconsistent with the non-streaming path.

That has now been aligned so both chat and streaming send:

- compatibility role via `X-Role`
- host-local role via `X-Host-Role`

This removes a nasty class of bugs where normal chat and SSE chat could behave differently for the same LMS user.

## Verification

### Python

Ran:

`.\.venv\Scripts\python.exe -m pytest tests\unit\test_identity_v2.py tests\unit\test_sprint159_lms_token_exchange.py tests\unit\test_auth_ownership.py tests\unit\test_sprint181_org_admin.py tests\unit\test_organization_api.py tests\unit\test_course_generation_flow.py tests\unit\test_sprint192_auth_hardening.py tests\unit\test_sprint194b_auth_hardening.py -q -p no:capture`

Result:

- `202 passed`

### Java

Ran:

`mvn -q -DskipTests compile`

Result:

- compile success

## Current State by Role

### Teacher

Status: **strong**

Teacher workflows are now in a good place:

- host-aware right sidebar
- course generation from document
- preview/confirm/apply host actions
- lesson/quiz/publish operator flow foundation

Identity-wise, LMS teacher now behaves as a host-local role instead of mutating Wiii's platform authority.

### Student

Status: **good but not final**

Student coach, page-aware context, and safety rails are already meaningful, but identity is still compatibility-based in older places. The role model is safer now, but student behavior is not yet fully expressed through a clean `host_session + capability policy + memory overlay` stack everywhere.

### Org Admin

Status: **partially mature**

Org governance and audit flows are present, but the identity model still needs a proper distinction between:

- Wiii platform admin
- organization admin inside Wiii
- organization admin inside LMS

This phase prevents the dangerous conflation, but the full org-role model still needs a deeper migration.

### Platform Admin

Status: **safer**

The key win in this phase is that platform-admin authority is no longer implicitly granted by LMS host role strings. Real platform-admin checks now rely on an explicit concept instead of generic legacy `admin`.

## What Is Still Not Final

### 1. Legacy `users.role` is still overloaded

Database/user-service level role storage is still compatibility-first.

We have reduced the damage by:

- adding additive identity claims
- shifting API gates to `platform_role`

But the persistence model still needs to become truly split:

- platform role
- organization membership role
- host role

### 2. Refresh-token / long-session identity continuity still needs a clean Phase 2

Access tokens now carry richer identity claims, but the long-lived session story across host transitions and refresh flows still needs a proper review.

### 3. Some non-critical behavior gates still inspect legacy roles

The most dangerous API/auth gates were fixed. Some lower-risk behavior/tier/tool logic may still inspect legacy role strings and should be cleaned in a later pass after the new identity model is fully introduced.

### 4. Cross-host UX is not done yet

The backend is moving toward multi-host identity, but the product still needs a clear user-facing concept such as:

- connected workspaces
- active organization
- current host session
- current host-local role

That is what will make Wiii feel coherent across:

- Wiii web
- LMS right sidebar
- future host integrations

## Production Plan

### Phase P0 - Done now

- Add Identity V2 compatibility fields
- Stop LMS host roles from becoming Wiii platform admin
- Replace critical `role == "admin"` gates with `is_platform_admin(...)`
- Align LMS chat and streaming headers

### Phase P1 - Persistence model cleanup

Goal: stop relying on compatibility role as the durable source of truth.

Do next:

- Add explicit persistent fields or normalized membership sources for:
  - `platform_role`
  - `organization_role`
  - `active_org_id`
- Keep `role` as legacy compatibility output only
- Review `user_service.py`, identity federation, and admin context APIs

### Phase P2 - Host session model

Goal: let Wiii move cleanly across multiple hosts.

Do next:

- introduce a first-class `host_session` or equivalent
- persist:
  - `host_id`
  - `connector_id`
  - `host_role`
  - `host_org_id`
  - `capabilities`
  - `page/session context`
- treat LMS as one connected workspace among others

### Phase P3 - Product UX

Goal: make the model visible and understandable to users/admins.

Do next:

- Connected workspaces UI in Wiii web
- Active org/workspace switcher
- Clear distinction between:
  - platform admin
  - org admin
  - host-local teacher/student/admin
- audit visibility for host-issued actions and connected sessions

### Phase P4 - Legacy cleanup

Goal: retire compatibility-first auth assumptions.

Do next:

- deprecate blind trust in `X-Role`
- make `X-Host-Role` the canonical host-local role header
- clean remaining behavior gates that read legacy role directly
- tighten test coverage around cross-host role transitions

## Architectural Decision

The correct long-term model is:

- `platform_role`: Wiii-wide authority
- `organization_role`: Wiii org authority
- `host_role`: local role inside a host like LMS
- `active_org_id`: current Wiii org context
- `host_session`: current plugin/workspace context

This matches the product direction:

- Wiii is one living multi-platform AI
- LMS is a plugin host
- host context should shape action and workflow, not overwrite identity

## Final Call

This phase is good enough to merge as the **first production-safe compatibility step** for multi-host identity.

It is not the end-state.

The most important outcome is that we are no longer reinforcing the wrong mental model:

- before: LMS role could redefine who Wiii thinks you are
- now: LMS role is treated as host-local context layered on top of Wiii identity

That is the right foundation for a professional, multi-host, living Wiii platform.
