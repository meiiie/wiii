# Feature Specification: Quiet desktop UX

**Created**: 2026-11-21
**Status**: Accepted for implementation
**Input**: Hùng requests better native desktop UX: “làm nhiều nói ít”; replace explanatory and defensive copy with components and clear actions.

## User Scenarios & Testing

### User Story 1 — Start work (P1)
Users can start a chat or open a project directly from home.

**Independent Test**: In the native desktop with no projects, choose Chat mới and reach the composer without creating a project or signing in to Wiii Service.

**Acceptance Scenarios**:
1. Given a fresh desktop, home presents chat and project actions above diagnostics.
2. Given saved projects, selecting a home project shortcut opens its composer.
3. Given saved sessions, the home catalog can continue an existing session.

### User Story 2 — Compose without ceremony (P1)
The project heading, composer and starter actions form one readable group.

**Independent Test**: Open a project, insert a starter, edit it and send. Switching away and back retains unsent text.

**Acceptance Scenarios**:
1. Given a ready Neko agent, no setup paragraph interrupts composing.
2. Given an unavailable agent, a short status and recovery action remain visible.
3. Given a compact window, the composer and send controls remain reachable.

### User Story 3 — Inspect setup when needed (P2)
Runtime configuration stays available without dominating everyday work.

**Independent Test**: Open the agent disclosure; invoke agent management from an unavailable project and verify it opens and receives focus.

### Edge Cases
- Discovery failure must not appear as a missing installation or enable sending.
- Unsupported hosts retain an explicit status; drafts and saved sessions remain intact.
- Long project names and many projects must not overflow the window.
- Reduced motion, keyboard focus, permissions and session stop behavior remain unchanged.

## Requirements
### Functional Requirements
- FR-001: Home MUST expose separate chat and project actions without requiring a managed account.
- FR-002: Home MUST show project shortcuts and allow saved-session continuation.
- FR-003: Runtime details MUST be collapsed by default and expand when explicitly requested.
- FR-004: The ready composer MUST omit repetitive setup explanations and preserve selected context, model and agent controls.
- FR-005: Errors MUST retain a concrete recovery action and on-demand diagnostic detail.
- FR-006: Keyboard navigation and compact layouts MUST preserve all primary actions.

### Key Entities
- Project: named source roots and preferred agent, unchanged.
- Session: saved conversation and runtime state, unchanged.
- Draft: unsent composer content, unchanged.

## Success Criteria
### Measurable Outcomes
- SC-001: New chat is reachable from home in one action without a project dialog.
- SC-002: A ready start screen shows zero setup or safety-explanation paragraphs.
- SC-003: Runtime management occupies one collapsed row until requested.
- SC-004: Native checks demonstrate home, project compose and session continuation at normal and compact window sizes.

## Assumptions
- Existing local chat, draft, permission and session contracts are reused.
- Installer work, provider/runtime changes, the retired web UI and LMS embed are outside this change.
- Approved Neko assets and Vietnamese-first voice are preserved.
