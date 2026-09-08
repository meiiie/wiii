# Wiii on Windows

Release target: 1.2.0 · Windows x64 · unsigned installer

Status: preparing; not published. These instructions describe the planned
stable installer. Candidate builds are for acceptance testing only.

## Install

1. Download the installer and its matching `.sha256` file from
   [Wiii Releases](https://github.com/meiiie/wiii/releases).
   Check that the release is stable; do not substitute an Actions artifact.
2. Compare the checksum before opening the installer:

   ```powershell
   $package = 'Wiii-1.2.0-windows-x64-unsigned-setup.exe'
   $expected = (Get-Content "$package.sha256").Split()[0]
   $actual = (Get-FileHash $package -Algorithm SHA256).Hash
   if ($actual -ne $expected) { throw 'Wiii checksum mismatch' }
   ```

3. Run the installer for your Windows user. Setup may need internet access
   if the Microsoft Edge WebView2 runtime is absent.
4. Install/configure [Neko Core](https://neko.holilihu.online/) using its official
   Windows instructions. Restart Wiii after installation or a PATH change.
5. Open **Tổng quan → Quản lý harness** and check Neko Core readiness.
   Choose a project folder, then send your first message.

A successful executable check does not prove model authentication is configured.
Keep account setup and credentials in Neko Core's own supported setup flow.

The installer is not Authenticode-signed. A checksum does not establish
publisher identity. If Windows or company policy blocks it, consult the release
source and your administrator; never globally disable Windows protection.

## If Neko is not ready

- **Not installed:** install Neko Core, restart Wiii and check again.
- **Check failed:** inspect the harness details and retry. This is not evidence
  that Neko is missing; avoid repeated reinstalls.
- **Model/account unavailable:** finish Neko Core configuration. Do not paste
  credentials into a bug report.
- **Linux/macOS:** local harness execution is not supported in this release.
  A frontend preview on another OS is not native runtime support.

This release does not promise automatic Neko installation, repair, removal or
background updates. Wiii does not silently fall back to a different harness.

## Computer is optional

Normal local conversations do not require Docker. To use **Computer**, install
and start Docker Desktop with its Linux engine, then use Wiii's Computer setup.
Download size and startup time depend on the pack, disk, network and resources.

Computer has a persistent profile separate from your host browser. Sign in
manually inside it if required. Taking control does not delete the profile;
do not use reset/remove as routine troubleshooting.

Computer is a same-user Linux environment, not hostile-app isolation. A
successful takeover stops Wiii-owned input after cleanup, not arbitrary
programs or already-completed external effects.

## Update, uninstall and recover

- Close Wiii before installing a newer official version. Back up important work.
- Desktop automatic updates are not enabled. Download Wiii updates from
  GitHub Releases; update Neko Core separately.
- Remove Wiii through Windows **Installed apps**. Neko Core and Docker Desktop
  are separate installations and must not be silently removed with Wiii.
- Removing the application and intentionally deleting projects or Computer
  profiles are different actions. Do not delete app-data or Docker volumes
  unless you intend to erase those records.
- If an upgrade fails, retain the data and report the error. Older software may
  not understand newer state; do not assume data-format downgrade is safe.

## Report an issue

Include the release/version, Windows version, failing step, expected result and
actual result. Add a redacted screenshot or error code if possible.
Do not attach profiles, cookies, API keys or private conversation dumps.

[Report a bug](https://github.com/meiiie/wiii/issues) ·
[Release standard](WIII_RELEASE_STANDARD.md)
