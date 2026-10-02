# Linux native build readiness

Status: proposed for review

Issue: https://github.com/meiiie/wiii/issues/992

## Goal
A Linux contributor can build the native Wiii application and request Linux
packages without accidentally inheriting the Windows-only NSIS default.
A successful frontend build or HTML response is not native startup evidence.

## Acceptance
- Linux platform overlay selects deb/AppImage; Windows default remains NSIS.
- Shared application identity, security capabilities, CSP and provider lifetime
  containment are unchanged.
- Instructions distinguish development, embedded-frontend native build,
  packaging, and Neko provider availability.
- Exact local compile/startup evidence and remaining limits are reported.
- An unrelated Linux program named `neko` must not be offered as Neko Core or
  become eligible for profile/ACP calls just because `--version` exits zero.

## Non-goals
No public release, merge, provider credentials, sandbox bypass, model
installation, Windows changes or promise of universal Linux support.
