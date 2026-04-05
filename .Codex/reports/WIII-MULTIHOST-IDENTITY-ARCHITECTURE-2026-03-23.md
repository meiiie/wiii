# Wiii Multi-Host Identity Architecture Review — 2026-03-23

## Executive Summary
- The LMS integration is now strong at the workflow layer for teacher/operator actions.
- The identity model is still not correct for a multi-host Wiii.
- The main bug is conceptual: Wiii currently overloads one field, `role`, with three different meanings:
  - platform authority inside Wiii
  - host-local pedagogical role from LMS
  - authorization shortcuts for admin/org access
- This is why the current `student / teacher / admin` checks feel wrong: they are wrong for a cross-host agent platform.

## Current State

### What is already in good shape
- Teacher/operator flows in LMS host context:
  - doc-to-course
  - preview -> confirm -> apply
  - quiz/course authoring
  - audit timelines
- Org-admin host action governance in LMS/Wiii operator surface.
- Student-safe coaching rails for quiz/assignment pages are partially in place.
- Wiii still behaves as an embedded right-sidebar operator in LMS, not as a host-owned personality.

### What is not architecturally complete
- Canonical identity across Wiii web + LMS + future hosts.
- Separation of platform role vs org role vs host role.
- A clean “connected workspaces” model for users who enter Wiii directly on the Wiii web, not only via LMS sidebar.

## Root Problem In Code

### 1. Wiii platform role is still a tri-state LMS-era model
- `AuthenticatedUser.role` is still modeled as `student | teacher | admin` in:
  - `app/core/security.py`
- `users.role` is also constrained to the same triad in:
  - `app/auth/user_service.py`

### 2. LMS token exchange collapses host roles into global Wiii roles
- `ORG_ADMIN -> admin`
- unknown -> `student`
- this happens in:
  - `app/auth/lms_token_exchange.py`
  - `LMS_hohulili/.../WiiiTokenExchangeAdapter.java`
  - `LMS_hohulili/.../WiiiChatAdapter.java`

### 3. Org admin already exists, but only as organization membership logic
- Wiii already has a real org-admin path in:
  - `app/api/v1/organizations.py`
- but JWT/auth and many older endpoints still only understand global `role == "admin"`.

### 4. Host-local role and platform identity are mixed together
- `host_context.user_role` already exists and is the right place for LMS-local role.
- but many older APIs and prompt paths still branch on auth role directly.

## Correct Target Model

### A. Canonical Principal
- Wiii should have one canonical person/principal across all channels and hosts.
- This principal should not become `teacher` or `student` globally just because they opened an LMS.

### B. Platform Role
- Global Wiii authority should be small and stable:
  - `user`
  - `platform_admin`

### C. Organization Role
- Org-scoped authority should live in organization membership, not in global platform role:
  - `member`
  - `org_admin`
  - `owner`

### D. Host Role Overlay
- LMS role should be an overlay on the current host session:
  - `student`
  - `teacher`
  - `admin`
  - `org_admin`
- This role should influence:
  - prompt framing
  - host actions
  - safety policy
  - page skills
- It should not redefine who the user is globally inside Wiii.

## SOTA Alignment
- OpenAI Apps in ChatGPT:
  - user connects apps to their account
  - workspace admins control RBAC, actions, domains, and parameter constraints
  - write actions require confirmation
- Anthropic connectors:
  - tools connect to a user account
  - Claude acts using the permissions of that connected account
  - connectors extend capabilities across Claude surfaces without redefining Claude’s core identity
- MCP Apps / enterprise auth:
  - UI extension, tool auth, and enterprise authorization are separate concerns
- Letta:
  - persistent state and memory belong to the agent identity layer, not to transient UI surfaces

## Recommended Migration

### Phase 1 — Additive Identity V2
- Add new concepts without breaking old code:
  - `platform_role`
  - `active_organization_id`
  - `organization_roles`
  - `host_identity`
  - `host_role`
  - `role_source`
- Keep legacy `role` temporarily for compatibility.

### Phase 2 — Stop LMS From Defining Global Wiii Identity
- LMS token exchange should stop treating LMS role as canonical Wiii account role.
- New LMS-linked users should become:
  - platform role = `user`
- LMS role should be stored as:
  - connector-scoped host identity
  - or host-session overlay

### Phase 3 — Move Authorization To The Right Layer
- Platform admin checks -> `platform_role`
- Org admin checks -> membership/org role
- Teacher/student behavior -> `host_context.user_role`
- Teacher-only LMS authoring APIs should require:
  - host role
  - org membership
  - resource ownership / capability grant

### Phase 4 — Native Wiii Web With Connected Workspaces
- On Wiii web, users should see connected workspaces/hosts:
  - Personal / default Wiii workspace
  - LMS orgs they belong to
  - future hosts
- If they are not inside LMS sidebar:
  - Wiii can still know they belong to an LMS org
  - but it must not assume current page context or DOM control
  - mutating host actions should require a live host bridge or explicit remote connector path

### Phase 5 — Deprecate Legacy Role Checks
- Replace `student/teacher/admin` branches in:
  - auth
  - chat prompt role framing
  - delete-history shortcuts
  - course-generation auth shortcuts
  - LMS dashboard data APIs

## Practical Product Posture
- LMS should remain a host/plugin.
- Wiii web should remain the canonical home of Wiii.
- Embedded LMS sidebar should be one strong surface, not the identity source of Wiii.
- The user experience should feel like:
  - “This is still Wiii”
  - “Wiii currently knows I am inside LMS org X”
  - “Wiii currently sees me as teacher/student on this LMS page”
  - not:
  - “My Wiii account has become a teacher account globally”

## Next Action
- Do not hotfix this by only changing string mappings.
- Start with Identity V2 schema and compatibility layer, then migrate auth and host-aware authorization in phases.
