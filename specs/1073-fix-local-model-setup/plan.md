# Implementation Plan: Local model setup

**Branch**: `devin/1795443222-904-dogfood-model-setup` | **Date**: 2026-11-23 | **Spec**: [spec.md](spec.md)

## Summary

Add one Vietnamese model dialog to Overview, ProjectHome and File menu. Main-only IPC writes canonical Neko1.9.5 user configuration; no Service, provider engine, runtime upgrade or automatic Send. Save is explicitly unverified and applies to new chats.

## Technical Context

- React19/TypeScript, Tauri2, Rust1.90+, Linux/macOS/Windows desktop.
- Existing serde_json/sha2/uuid/windows-sys; at most add a Windows API feature, no new package/version.
- Store: `USERPROFILE || HOME || platform home` + `.neko-core/config.json`. Private plaintext, not browser persistence or an advertised OS vault.
- Bounded2MiB reads, blocking filesystem work off UI thread, no render/save network requests.
- Tests: native unit/security contract, focused Vitest/tsc, genuine Tauri/WebKitGTK Light800/Dark1200, CI and independent Review.

## Constitution Check

Pre/post-design PASS. Neko remains runtime sovereign. No generic JSON/path/process/environment authority or changed tool/approval defaults. Draft/history/streaming, Service and tenant boundaries remain intact. Explicit loading/saving/error states; no telemetry carrying request bodies. No governance exception.

## Project Structure

- `wiii-desktop/src-tauri/src/neko/local_models.rs`: bounded config operations/tests.
- `wiii-desktop/src-tauri/src/commands/local_models.rs`: main-only status/save IPC.
- `wiii-desktop/src-tauri/capabilities/workbench-models.json`, handler/build manifest/generated permissions and security_contract.
- `wiii-desktop/src/lib/local-model-setup.ts`: typed bridge.
- `wiii-desktop/src/neko-chill/components/LocalModelSetupDialog.tsx`: shared native dialog.
- `wiii-desktop/src/neko-chill/NekoChillApp.tsx`, existing Overview/ProjectHome/Menu components: explicit status/dialog/profile-refresh props, no composer remount.

## Data Flow, Failure Modes And Risk

1. Read-only status returns configured/presets, never stored keys. Fresh Overview offers setup. Project first Send opens it when unconfigured and retains the draft; browser previews get no native action.
2. Explicit request supplies preset/model/custom address/key, not a filesystem path or arbitrary provider JSON. Presets inherit canonical builtin profile ids/defaults; custom OpenAI-compatible connections use stable wiii-prefixed ids. z.ai Coding Plan only. Keys/URLs/model identifiers have native bounds and injection checks; HTTPS outside loopback, no URL userinfo/query/fragment.
3. Preserve unrelated JSON/providers/MCP. Migrate unambiguous legacy top-level connection fields to their prior owner before activating the new profile. Refuse mixed legacy/scoped connection records rather than reproduce Core1.9.5's endpoint/key recombination; never overwrite a prior credential binding. Reject malformed/non-object/linked/unsafe files and higher-priority legacy home configuration that would shadow a save. Never repair existing data or reuse a saved key across changed endpoints. Keyless saves require Core's exact local-host boundary; remote custom servers require a key.
4. App-scoped save lock; exclusive private sibling temp, sync, rename; on failure remove only owned temp and retain original. Unix0600/new-dir0700; Windows protected owner/System DACL before writing. Static Vietnamese errors, no raw parser/OS/provider response.
5. Return profile id/model/provider only. Parent refreshes/selects without draft remount. Changes apply to new chats; first explicit user Send validates authentication. Keys clear from ephemeral UI state on close/success. Disclose plaintext local storage accurately.

## Rollback And Verification

Revert UI/IPC/capability; canonical saved profiles remain usable by Neko. Never automatically delete user configuration/keys. No migration, release or binary publication.

Run focused dialog/bridge/entry/menu tests, tsc, native module/security tests, formatting, scoped hooks and diff check. Testing agent owns all native setup/build after source freeze and preserves actual running `/proc/<pid>/exe` before shared-target rebuild. Fresh no-env/config/history acceptance covers fields/errors/focus/drafts, saved selection, actual File-menu Quit/reopen. Real Coding Plan response requires a separately authorized credentialed pass. Audit original protected records/Computer authority, keep evidence outside git, require native/CI/Devin Review clean before delegated merge.

## Tooling Substitution

PowerShell is absent. The setup-plan/setup-tasks scripts only resolve feature.json, validate paths, copy templates and list docs; equivalent Python/template operations are used, without installing tooling or changing governance.
