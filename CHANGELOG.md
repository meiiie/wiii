# Changelog

All notable changes to Wiii are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/). `VERSION` is the repository's
coordinated release target, not proof of publication. A stable release tag is
always `wiii-v<version>` and requires a dated matching section below.

## [Unreleased]

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

### Changed

- The initial public stable desktop release is scoped to Windows x64 with an
  explicitly unsigned installer. Linux/macOS are deferred; planned Windows
  publication retains review, installer acceptance, integrity and provenance
  gates without using the emergency publication route.

- Desktop now opens local-first while existing managed-account intent migrates
  additively; empty/stale auth metadata no longer opens Wiii Service, while
  hosted web remains remote-authority-only.
- Reframed the authentication surface as the optional Wiii Service gateway,
  with explicit managed-capability benefits, a prominent return to local Wiii,
  and custom endpoints moved into advanced connection setup.
- Public release artifacts and manifests now use the product name `Wiii`.
  Candidate identities include their source commit, and Windows filenames state
  whether the installer is unsigned or Authenticode-signed; stable internal
  executable and bundle identifiers remain unchanged for in-place upgrades.
- Repositioned Wiii as an open AI workbench and runtime. Learning-management
  systems are supported through Wiii Connect adapters rather than defining the
  product itself.
- Rebuilt the desktop information architecture around sessions, workspaces,
  inspectable artifacts, and resilient local-first interaction.
- Unified backend package/runtime and desktop metadata under the repository
  `VERSION` source of truth.
- Desktop release validation runs before packaging; stable publication attests
  and verifies the exact artifact inventory for the declared release scope.
- Stable publication now verifies exact filenames, sidecars, manifest
  version/commit bindings and the declared Windows trust state (including the
  signer thumbprint for Authenticode builds), with a protected
  and publicly disclosed Windows-only break-glass path for hosted-runner
  outages.
- Neko Core is the default harness without silently replacing an existing
  explicit choice. Harness diagnosis belongs in Overview; a failed probe is
  distinguished from a missing installation.
- Refined desktop menus, resizable tool panes, Project dialogs and keyboard
  focus recovery, with reduced-motion support.

### Fixed

- Prevented a Vite 8 React/Zustand chunk cycle that could leave the production
  hosted-web surface blank.
- Preserved fast Codex turn-completion notifications delivered before the UI
  installs its turn waiter.
- Window controls now route through native Tauri commands with explicit
  minimize, maximize/restore, and close behavior.
- ACP sessions survive process restarts and recover checkpoint metadata,
  provider continuation state, usage, tool calls, and cursor-based replay.
- Tool calls are checkpointed before side effects; interrupted mutations are
  restored as `unknown_outcome` and are never silently replayed.
- Prevented provider stdin backpressure from blocking its timeout, bounded
  session-discovery frames while reading, and made event-pump shutdown wake
  reliably.
- Preserved drafts and recoverable Project/dialog state after failed actions.

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

### Known limitations

- Windows x64 only; Linux/macOS local harness execution is not supported.
- Neko Core requires separate installation and model/account configuration.
  Automatic Wiii and Neko installation/updates are not enabled together.
- Computer is an optional experimental same-user workstation, not a sandbox
  for hostile apps. Revocation cannot undo delivered effects or stop arbitrary
  independent guest programs.
- No human-level benchmark, universal app coverage or end-to-end latency SLA
  is claimed. Background-app and load-sensitive follow-ups remain tracked in
  [#964](https://github.com/meiiie/wiii/issues/964).

[Unreleased]: https://github.com/meiiie/wiii/commits/main
