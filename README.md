# Wiii

<p align="center">
  <img src="docs/assets/brand/neko-family-v1/social/wiii-readme-banner.png" alt="Wiii — a workspace for you and Neko" width="100%" />
</p>

<p align="center">
  <a href="https://github.com/meiiie/wiii/releases">Downloads</a> ·
  <a href="docs/releases/WIII_WINDOWS_QUICK_START.md">Windows guide</a> ·
  <a href="https://github.com/meiiie/wiii/issues">Feedback</a> ·
  <a href="LICENSE">AGPL-3.0-only</a>
</p>

Wiii is a local-first desktop workspace for working with Neko, your AI
coworker. Keep projects, conversations, files and tools together, and stay in
control of what the agent can access and change.

Built by **The Wiii Lab**. Vietnamese is the primary interface language.

<p>
  <a href="https://github.com/meiiie/wiii/actions/workflows/test-desktop.yml"><img src="https://github.com/meiiie/wiii/actions/workflows/test-desktop.yml/badge.svg" alt="Desktop tests" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/meiiie/wiii" alt="AGPL-3.0-only license" /></a>
</p>

## Start with a project

1. Install Wiii and [Neko Core](https://neko.holilihu.online/).
2. Open Wiii, choose a project folder and configure your model through Neko Core.
3. Start a conversation. Open **Công cụ** to inspect files, changes and available
   tools alongside the conversation.

A local project does **not** require a Wiii Service account. Model providers
may require their own account, credentials and payment. Wiii Service is optional
and separate from local desktop work.

## Downloads and support

**1.2.0 is being prepared and is not published yet.** The Windows candidate
has been built, but installed-desktop acceptance and the stable publication
gates are still pending. The filename below describes the planned release,
not an installer currently available from GitHub Releases.

Official stable installers are published only on
[GitHub Releases](https://github.com/meiiie/wiii/releases). Check that the release
contains an installer, its SHA-256 sidecar and a release manifest; a source
version or a CI build alone is not a published release.

The **1.2.0 release scope is Windows x64**. Linux and macOS local harness
execution are not supported by this release.

| Component | What to expect |
| --- | --- |
| Wiii | Per-user Windows installer |
| Neko Core | Default harness; install and configure separately for this release |
| Computer | Optional Linux desktop through Docker Desktop; not required for normal local conversations |
| Updates | Install a newer Wiii version manually; Neko Core has its own update mechanism |
| Publisher signature | This Windows release is explicitly **unsigned** |

The installer name is `Wiii-1.2.0-windows-x64-unsigned-setup.exe`.
Unsigned software may be blocked by Windows or an organization's policy.
Checksums verify downloaded bytes, **not** publisher identity or safety.
Do not disable Windows protection globally.

Read the [Windows installation and recovery guide](docs/releases/WIII_WINDOWS_QUICK_START.md)
before installing. Candidate builds include `candidate` and a source commit
in their filenames; they are evaluation builds, not stable releases.

## A calm workspace with visible control

- **Project and Session:** organize conversations around your folders and reopen
  persisted work without recreating the project.
- **Neko first:** Neko Core is the default for new local work. Existing explicit
  harness choices remain intact; Wiii does not silently substitute another
  installed agent when Neko is unavailable.
- **Tools beside the conversation:** resizable panes for files, changes,
  browser, terminal and the optional Computer.
- **Recoverable state:** distinguish a missing harness from a failed check.
  Diagnostics live in **Tổng quan → Quản lý harness**, with technical details
  available when needed.
- **Permission-aware execution:** observation is not control. An interrupted
  action is not automatically repeated when its outcome is unknown.

## Optional Computer

Computer gives Neko a persistent Linux desktop with its own browser profile.
You can sign in inside that desktop, watch Neko work, and take control when
needed. Your existing host browser profile is not copied into it.

The Windows pilot still requires Docker Desktop. Computer is optional,
experimental, and a **same-user workstation**, not a sandbox for hostile apps
or multiple untrusted users.

Taking control cancels Wiii-owned queued input and waits for active input and
held-key cleanup before acknowledging the handoff. It does not undo an email
already sent or stop every independent program inside the desktop.
Unconfirmed cleanup remains blocked instead of pretending the handoff succeeded.

Only explicitly granted project folders belong in the Computer. Back up
important files, review high-consequence actions, and handle sign-in and
CAPTCHA yourself. See the [control boundary](docs/architecture/COMPUTER_CONTROL_ISOLATION.md).

## Build from source

For the Windows desktop, use Node.js 22.12+ (Node 22 is used in CI), a current
stable Rust toolchain and the
[Tauri v2 Windows prerequisites](https://v2.tauri.app/start/prerequisites/).

```powershell
cd wiii-desktop
npm ci
npm run tauri -- dev
```

For frontend-only development, use `npm run dev`. This preview has no native
process, filesystem or Computer authority.

```powershell
# From wiii-desktop
npm test -- --run
npm run build
npm run build:embed
npm run tauri -- build --bundles nsis

# From the repository root
cd ..
python tools/release/wiii_release.py check
```

A local installer is a development artifact, not an official release.
Keep generated builds, profiles and test evidence out of commits.

## Repository map

| Directory | Responsibility |
| --- | --- |
| [wiii-desktop/](wiii-desktop/) | React interface, Tauri host, Neko sessions and Computer |
| [maritime-ai-service/](maritime-ai-service/) | Optional service: FastAPI, retrieval, managed memory and integrations |
| [docs/](docs/) | Architecture, product contracts, operations and research |
| [tools/release/](tools/release/) | Version synchronization, checksums and release verification |

The backend is not required to open a local desktop project.
See the [desktop engineering guide](wiii-desktop/README.md) and
[backend engineering guide](maritime-ai-service/README.md) for development setup.
Research documents describe direction and experiments, not guaranteed shipped
capabilities or performance.

## Feedback, contributions and security

For a bug report, include the Wiii version, Windows version, reproduction steps,
expected result and actual result. Attach a redacted screenshot if useful.
Never upload API keys, browser profiles, private conversations or account tokens.
Use [GitHub Issues](https://github.com/meiiie/wiii/issues) for ordinary feedback;
report security-sensitive findings privately to the maintainers.

Read [AGENTS.md](AGENTS.md) and the
[contribution workflow](docs/operations/WIII_GITHUB_GOVERNANCE.md) before changing
runtime or permission boundaries. Small, reproducible fixes are welcome.

## License

Wiii's core product is **AGPL-3.0-only**, with a separate commercial license
available. Independently implemented code under `sdk/` is **Apache-2.0**.
The code licenses do not grant rights to the Wiii name or branding.

See [LICENSING.md](LICENSING.md), [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md)
and [TRADEMARKS.md](TRADEMARKS.md).
