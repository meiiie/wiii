# Windows public release checklist

Status: Preparing; not published
Owner scope: 2026-09-07, issue #951

## Publication contract

- Official stable GitHub release, Windows x64 only.
- Preserve coordinated VERSION; create an immutable annotated or signed
  wiii-v<version> tag only after the release source passes acceptance.
- NSIS installer, explicit unsigned filename and trust notice, SHA-256
  sidecar, source-bound manifest and GitHub artifact provenance.
- No Linux/macOS availability or automatic-update claim.
- Neko Core is the default harness, separately installed/configured.
  Optional Computer requires Docker Desktop and is an experimental same-user
  desktop, not isolation against hostile guest applications.
- Human takeover cancels Wiii-owned scheduled input before acknowledgement.
  It cannot undo delivered effects or stop arbitrary independent guest programs.

## Must pass before publication

1. Integrate reviewed native, workbench, recovery and input-revocation changes;
   resolve findings with evidence, never count skipped review as approval.
2. Validate exact version/changelog and CI on the assembled source.
3. Build a candidate installer from that source and inspect packaged resources
   for accidental private data, developer paths and missing runtime assets.
4. In an isolated Windows user/VM, install, launch, detect missing/installed
   Neko, create a disposable Project, complete one harmless ACP task and cancel
   another. Restart to verify Project/session persistence.
5. Verify upgrade/uninstall preserve user data and profile recovery.
6. Tag only the accepted source. Verify the resulting stable artifact,
   checksum, manifest and provenance, then publish without replacing bytes.

Unit/component tests, browser previews and native fixtures are complementary
evidence. None alone proves installed desktop or real ACP acceptance.
Do not reuse a developer's signed-in account/profile for release tests.

## Feedback and recovery

Release notes state what changed, required components, unsigned-install
instructions, known limitations, privacy-safe feedback steps and rollback.
Ask for build identity, Windows version, reproduction steps, expected/actual
result and a redacted screenshot; never request passwords or profile dumps.
Do not advise globally disabling Windows protection.
Do not move a published tag. Corrections receive a higher version.
