# Changelog

All notable changes to Wiii are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/). `VERSION` is the repository's
coordinated release target, not proof of publication. A stable release tag is
always `wiii-v<version>` and requires a dated matching section below.

## [Unreleased]

### Fixed

- (none yet)

## [1.2.0] - 2026-09-22

First public **stable** desktop release. Supersedes pre-release
`wiii-candidate-1.2.0-5ce57a2f`. Coordinated product version remains `1.2.0`.
Public installer scope is **Windows x64**, explicitly unsigned.

### Added

- A host-aware Workbench bootstrap shared by desktop and hosted web, with
  explicit local-process, workspace, native-window, secret-store, and remote
  runtime capabilities.
- Codex App Server integration with provider-owned sign-in, model/reasoning
  controls, durable threads, streamed turns, approvals, interrupt, and resume.
- Optional Wiii Knowledge retrieval for local agent sessions, including source
  provenance and durable model-visible context replay.
- Neko Chill, a desktop-first agent workspace with durable ACP sessions,
  session replay, model/profile/reasoning controls, slash commands, and explicit
  handling of mutations whose outcome is unknown after a crash.
- A live workspace pane for files, diffs, previews, and artifacts beside the
  conversation.
- The Neko mascot family, Peek application icon, motion research lab, and a
  coherent visual identity across the desktop app, installer, repository, and
  social surfaces.
- A repository-wide release tool for synchronized versions, release notes,
  checksums, and machine-readable artifact manifests.
- An optional persistent Linux Computer through Docker Desktop, with separate
  browser profiles, explicit Project grants and a human/agent control handoff.
- A Windows installation and recovery guide covering Neko Core setup, unsigned
  package checks, manual updates and privacy-safe feedback.
- Linux local Neko via bubblewrap containment when building/running the desktop
  on Linux (`#981`); stable spawn thread for PDEATHSIG (`#987`). No public
  Linux/macOS installer in this release.

### Changed

- Public stable desktop release is scoped to Windows x64 with an explicitly
  unsigned installer. Linux/macOS packages remain deferred; Windows publication
  retains review, installer acceptance, integrity and provenance gates.
- Desktop opens local-first; empty/stale auth metadata no longer opens Wiii
  Service. Hosted web remains remote-authority-only.
- Authentication surface reframed as the optional Wiii Service gateway, with
  managed-capability benefits, a return to local Wiii, and custom endpoints in
  advanced connection setup.
- Public release artifacts and manifests use the product name `Wiii`. Windows
  filenames state unsigned vs Authenticode-signed; stable internal executable
  and bundle identifiers remain unchanged for in-place upgrades.
- Repositioned Wiii as an open AI workbench and runtime. LMS support goes
  through Wiii Connect adapters rather than defining the product.
- Desktop information architecture rebuilt around sessions, workspaces,
  inspectable artifacts, and resilient local-first interaction.
- Backend package/runtime and desktop metadata unified under repository
  `VERSION`. Stable publication verifies filenames, sidecars, manifest
  version/commit bindings and declared Windows trust state.
- Neko Core is the default harness without silently replacing an existing
  explicit choice. Harness diagnosis belongs in Overview.
- Soft polish: searchable model picker, Stop-while-dispatching, calm overview
  hero, hydrate recovery skeleton, session composer IME/submitting parity,
  keyboard footer honesty, Tools/Files honesty and breadcrumb titles
  (`#967`–`#989`).

### Fixed

- Prevented a Vite 8 React/Zustand chunk cycle that could leave the production
  hosted-web surface blank.
- Preserved fast Codex turn-completion notifications delivered before the UI
  installs its turn waiter.
- Window controls route through native Tauri commands with explicit
  minimize, maximize/restore, and close behavior.
- ACP sessions survive process restarts and recover checkpoint metadata,
  provider continuation state, usage, tool calls, and cursor-based replay.
- Tool calls are checkpointed before side effects; interrupted mutations are
  restored as `unknown_outcome` and are never silently replayed.
- Provider stdin backpressure, session-discovery frame bounds, and event-pump
  shutdown wake reliability.
- Preserved drafts and recoverable Project/dialog state after failed actions.
- Honest gated UI when folder picker, connections, coworker computer, or tools
  invoke are unavailable; honest provider exit banner (signal vs clean, empty
  turn); bounded Neko stderr capture on exit; Coworker project cards no longer
  auto-grant like Chill (`#968`–`#986`, `#983`, `#989`).
- GTK folder start-path + Project Home starters; empty-workspace Project
  onboarding clarity (`#982`, `#967`).

### Security

- Browser hosts fail closed for native process, filesystem, tray, and local
  secret-store authority.
- Retrieved knowledge must cross the durable model-input barrier before a
  provider can observe it; a failed write blocks dispatch.
- Subscription and API credentials remain owned by their providers; Wiii does
  not copy Codex account tokens and does not imitate unsupported Claude
  subscription login.
- Durable session storage uses a single-writer lease, backup checkpoint
  recovery, and process-scoped permission grants.
- Computer control uses a private root-peer socket instead of a guest-accessible
  TCP control port. Revocation invalidates queued actions, interrupts owned
  input and waits for held-key cleanup before acknowledging takeover.
- Browser and Terminal execution reject a revoked Project grant.
- Release policy explicitly discloses unsigned Windows packages and requires
  provenance plus checksums. An unsigned stable release does not establish
  Authenticode publisher identity.
- Linux bwrap containment is a same-user local harness boundary for Neko, not a
  malicious-guest sandbox.

### Known limitations

- Public installer: Windows x64 only. Linux/macOS installers are not published
  in this release. Linux desktop source builds may run local Neko via bubblewrap
  when `bwrap` is available; that path is not a supported public package.
- Neko Core requires separate installation and model/account configuration.
  Automatic Wiii and Neko installation/updates are not enabled together.
- Computer is an optional experimental same-user workstation, not a sandbox
  for hostile apps. Revocation cannot undo delivered effects or stop arbitrary
  independent guest programs.
- No human-level benchmark, universal app coverage or end-to-end latency SLA
  is claimed. Background-app and load-sensitive follow-ups remain tracked in
  [#964](https://github.com/meiiie/wiii/issues/964).

[Unreleased]: https://github.com/meiiie/wiii/commits/main
[1.2.0]: https://github.com/meiiie/wiii/compare/wiii-candidate-1.2.0-5ce57a2f...wiii-v1.2.0
