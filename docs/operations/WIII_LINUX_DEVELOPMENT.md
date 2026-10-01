# Wiii native Linux development

Status: contributor build/run path; not a published Linux release claim.
The governed release baseline remains Ubuntu 22.04 x64. See
[release standard](../releases/WIII_RELEASE_STANDARD.md) for publication gates.

## Prerequisites (Debian/Ubuntu)

Use a normal graphical desktop session, Node.js 22.12+ (Node 22 in release CI),
Rust stable >= 1.89, and the [Tauri Linux prerequisites](https://v2.tauri.app/start/prerequisites/#linux).
Install only from your distribution's supported repositories:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends \
  build-essential pkg-config libwebkit2gtk-4.1-dev libgtk-3-dev \
  libssl-dev libxdo-dev libayatana-appindicator3-dev librsvg2-dev \
  patchelf xdg-utils bubblewrap
```

`bubblewrap` is required for local provider process ownership, not for compiling
React. Its presence alone does not establish that namespaces work in a managed
container. Wiii deliberately reports the host unavailable if the capability
probe fails. Do not disable this check, WebKit sandboxing, CSP, or operating-system
security settings to make a test appear successful.

Neko Core is separately installed/configured. A Wiii Service account is not
required for a local desktop project. No provider credentials are needed just
to compile Wiii or inspect its initial window.

## Build and run

```sh
cd wiii-desktop
npm ci
pkg-config --modversion gtk+-3.0 webkit2gtk-4.1
rustc --version
npm run tauri -- dev
```

`npm run dev` alone is the browser frontend: it has no native filesystem,
process or Computer authority. `tauri dev` runs the Vite server and native host
in the same desktop environment. A remote browser's localhost may refer to a
different environment than the build process.

For a native binary with embedded frontend assets and no installer:

```sh
npm run tauri -- build --debug --no-bundle
```

The CLI prints the built binary path. Run that exact path from the graphical
session; quote paths containing spaces. Do not assume a bare `cargo build`
embeds the frontend: Tauri's build command selects the custom-protocol feature.

For Linux packages:

```sh
npm run tauri -- build
# Explicit equivalent, also used by the release workflow:
npm run tauri -- build --bundles deb,appimage
```

`src-tauri/tauri.linux.conf.json` overrides only bundle targets on Linux. It
preserves the shared application identity and security configuration. Windows
continues to use NSIS. AppImage construction may need additional packaging
tools/downloads and suitable FUSE support when launching. A binary-only build
is the smaller first diagnostic step.

## Verify in layers

1. Frontend: `npm run build` and the relevant Vitest suites.
2. Native compilation/tests: `cargo test --locked` from `src-tauri`.
3. Native startup: observe splash transition and the actual main window.
4. UI: open settings, return to workspace, minimize/restore and quit; verify
   restart without corrupting state. Use a fresh test profile and no private data.
5. Provider: verify host containment, install/configure an approved provider,
   then separately test a harmless conversation, cancellation and resume.
6. Packaging: test the generated deb/AppImage on the supported release baseline.

Passing one layer does not prove the next. A shell process or HTTP 200 is not
proof of a rendered native window. Report exactly which layers ran.

## Troubleshooting

- `pkg-config` missing GTK/WebKit: install the development packages above.
- No display: launch in a desktop session with a working DISPLAY/Wayland setup;
  headless compilation is not an interactive startup test.
- Neko Core probe failed despite a `neko` executable: unrelated programs
  (including remote-desktop servers and NekoVM) use that name. The supported
  Neko Core CLI identifies itself with `neko-core <version>`. Review PATH
  precedence and install the intended provider; do not rename an unrelated
  executable or treat this check as publisher authentication.
- Native provider unavailable: check bubblewrap installation and the host's
  namespace policy; retain the fail-closed behavior.
- Compiles but fails to load shared libraries: check the executable's loader
  diagnostics and distro compatibility. Do not ship a portable development
  sysroot as a production installer.
- Linux package command exits successfully without producing a package: ensure
  the Linux overlay is present, or explicitly use `--bundles deb,appimage`.

Do not commit profiles, provider tokens, generated binaries or local sysroots.
