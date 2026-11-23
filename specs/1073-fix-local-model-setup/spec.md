# Feature Specification: Local model setup in Wiii

**Feature Branch**: `devin/1795443222-904-dogfood-model-setup`
**Created**: 2026-11-23
**Status**: Specified
**Linked work**: #904
**Input**: Hùng requires a new desktop user to add a model or API key inside Wiii, without a terminal or Wiii Service. Native first-use dogfood confirmed that existing routes only select built-in profiles, detect the runtime, or open optional Service authentication.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start using a model after installation (Priority: P1)

A new desktop user can discover model setup, choose a provider, enter the model and its API key, save, and send the first message without leaving Wiii.

**Why this priority**: A model picker alone cannot make an unconfigured installation usable.

**Independent Test**: Start without model configuration, credentials or history; complete setup through the visible desktop UI and receive a real response using an authorized test key.

**Acceptance Scenarios**:
1. **Given** a first-use desktop, **when** the user opens Overview or a new chat, **then** model setup is discoverable before an avoidable authentication failure.
2. **Given** valid provider details, **when** the user saves, **then** the chosen model is selected for the next chat; no terminal, configuration-file editing or Service account is required.
3. **Given** saved details, **when** the user sends a message, **then** a real response establishes connection success; merely saving or displaying a model is not called a verified connection.

### User Story 2 - Correct a key without losing work (Priority: P1)

A user can reopen local model setup from the project/chat entry surface and replace incorrect details while preserving the unsent draft.

**Why this priority**: The first configuration can be mistyped or become invalid.

**Independent Test**: Keep a draft, open and cancel setup, reopen and save corrected details; verify the draft and selected model.

**Acceptance Scenarios**:
1. **Given** an existing draft, **when** setup opens or closes, **then** the draft remains unchanged and focus returns predictably.
2. **Given** invalid or unsavable details, **when** save fails, **then** an actionable Vietnamese message appears without secrets, partial writes or loss of existing configuration.

### User Story 3 - Keep local setup across restart (Priority: P2)

A user who saved model details can quit and reopen Wiii without entering them again.

**Why this priority**: A connection that disappears at exit is not complete onboarding.

**Independent Test**: Save in an isolated profile, use the real File-menu Quit, reopen, then verify the selected configuration and a bounded actual model response.

**Acceptance Scenarios**:
1. **Given** a saved model, **when** Wiii reopens, **then** its details remain usable without shell environment changes.
2. **Given** unrelated local settings, history and provider configuration, **when** a model is saved, **then** those records and their credential ownership remain intact.

### Edge Cases

- Empty key/model; unsupported or malformed address; embedded credentials in an address.
- A local model server that needs no API key.
- A malformed existing configuration, symbolic link, denied write or interrupted save.
- Existing top-level legacy connection fields must not override the newly selected model or leak an old key to another endpoint.
- Existing configured installations must not be forced through onboarding again.
- Browser preview cannot claim local filesystem or credential authority.
- Keyboard-only use, reduced motion, compact800 and wide1200 layouts in Light/Dark.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Wiii MUST offer visible local model setup from Overview and the project/new-chat entry surface.
- **FR-002**: Setup MUST support an API-key provider and a custom OpenAI-compatible/local model address without Service authentication.
- **FR-003**: Setup MUST require only connection details, not terminal commands or runtime terminology.
- **FR-004**: Saving MUST persist locally, select the saved model, and leave actual sending under the user's control.
- **FR-005**: Saving MUST NOT be described as verified authentication; real validation failures MUST remain recoverable.
- **FR-006**: Keys MUST be masked during entry and excluded from browser persistence, logs, returned metadata, recordings and error details.
- **FR-007**: The UI MUST accurately disclose local credential storage; it MUST NOT claim encryption or OS-keychain protection that is not implemented.
- **FR-008**: Saving MUST preserve unrelated local configuration and bind each key to its intended provider/address.
- **FR-009**: Unsafe, malformed or unwritable configuration MUST fail without truncating, repairing or replacing existing data.
- **FR-010**: Untrusted content, browser previews and non-main windows MUST NOT receive setup authority.
- **FR-011**: z.ai setup and authorized testing MUST use Coding Plan endpoints, never the pay-per-call route.
- **FR-012**: Work, Service authentication, runtime authority defaults, releases and binary publication MUST remain out of scope.

### Key Entities

- **Local model connection**: Provider/protocol, address, model identifier and intended credential binding.
- **Connection secret**: Locally stored API key; never returned to the interface after save.
- **Setup state**: First-use discovery, editing, saving, saved-but-unverified and recoverable failure.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A credential-free fresh install reaches a real authorized model response with zero terminal commands and zero Service authentication actions.
- **SC-002**: Saved configuration survives one genuine Quit/reopen cycle and remains usable.
- **SC-003**: Opening, cancelling and completing setup preserve the exact unsent draft and existing conversation data.
- **SC-004**: Native Light/Dark compact/wide acceptance, relevant CI and independent review are clean before merge.
- **SC-005**: No key appears in returned metadata, persisted browser state, logs or delivered evidence.

## Assumptions

- Users supply a valid provider key or already have a local model server; Wiii does not provision paid accounts or embed shared credentials.
- Existing Neko1.9.5 configuration compatibility is retained; no Neko release or bundle modification is required.
- Existing local-runtime credential storage is private configuration, not an advertised encrypted vault.
- Scope is desktop; hosted web and Service retain their current boundaries.
