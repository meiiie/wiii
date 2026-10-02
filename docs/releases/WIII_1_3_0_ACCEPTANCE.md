# Wiii 1.3.0 acceptance checklist

Status: owner-authorized official release preparation, 2026-10-02. Publication is not complete until the governed workflow succeeds.
Tracking: #951. Product integration: #997, on the foundations in #993 and #995.

## Source and verification

- [x] Preserve the received task-v1 handoff and validated UI changes
- [x] Frontend integration: 3,703 tests in 240 files after the diagnostic-rendering regression correction
- [x] Linux native fixture acceptance recorded separately from installer acceptance
- [x] Keep source version metadata synchronized using the governed release tool
- [x] Correct generated release-note copy to describe the bundled runtime
- [x] #997 merged at dca6e1dbc2cac4e528cfe937cb44bef3935e0dd6 after all applicable checks and review threads passed
- [ ] Verify the exact release-preparation head through required GitHub checks

## Owner decision and known runtime limitation

The immutable published Neko Core v1.7.0 is the current bundle pin. It does not
advertise the opt-in ACP task protocol used by the received Work integration.
The local native acceptance used upstream source
`8b3354fcb5b76c55061b9e439c241faf7ecbbcae`; this is not the immutable v1.7.0 artifact.
A source version string alone is not proof of the necessary capabilities.

The owner explicitly requested official publication with the existing Neko pin
instead of waiting for a compatible Neko release. This is a scoped product
compatibility waiver, not a waiver of checksum, provenance, branch checks,
permission or task-identity validation. Release notes must prominently state
that Work flows requiring task-v1 are unsupported with bundled Neko 1.7.0.

Follow-up acceptance work (not claimed complete by this release):

- [ ] Obtain an upstream published immutable release containing the compatible task contract
- [ ] Review the source/tag and update the per-platform artifact pins and SHA-256 values
- [ ] Verify ACP initialize advertises `_meta["neko.taskProtocol"]` with version `1` and mode `fixed-active-task`
- [ ] Verify task-scoped session/new, receipt/root binding, prompt, cancellation, clean close and cold resume using the exact bundled bytes
- [ ] Verify unknown outcomes and unavailable writer recovery remain fail-closed without deleting user leases or silently retrying work

No legacy fallback may silently remove task-scope validation merely to obtain
a successful build. Do not substitute the local candidate for released 1.7.0
under the same public artifact identity.

## Installer and platform gates

The canonical planned stable scope remains Windows x64. Broader candidate
artifacts do not establish supported Linux/macOS installed-package acceptance.

- [ ] Clean install with no separately installed Neko CLI in an isolated user/VM
- [ ] Verify the expected bundled runtime is selected and integrity failure is terminal
- [ ] Verify provider configuration, chat, Work, queue, Stop, restart and saved data
- [ ] Verify upgrade preserves existing settings, history, drafts and task mappings
- [ ] Check package checksums, manifest/source/version binding, explicit Windows trust and provenance
- [ ] Record any broader-platform acceptance separately; do not advertise untested support

## Publication gate

The 1.3.0 changelog is dated for the owner-authorized release and includes the
runtime limitation and incomplete Windows GUI/provider-account/upgrade acceptance.
Merge the reviewed release commit only after its required source checks pass,
create its immutable annotated (or signed) tag, run the governed Desktop Release
workflow, and inspect the published asset inventory. Do not claim any unchecked
acceptance item above passed. A green source PR is not proof of publication or
installation success. Automatic desktop updates and publisher-key custody remain
unchanged.
