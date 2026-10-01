# Plan

1. Reproduce the default Linux bundle behavior on unmodified source.
2. Build against Rust and GTK/WebKit dependencies; distinguish host/toolchain
   errors from repository errors before changing runtime code.
3. Add a Linux-only Tauri bundle overlay and regression tests; document native
   build/run and fail-closed bubblewrap requirements.
4. Validate the branded Neko Core version contract to reject same-name programs;
   preserve bounded probing, proven cleanup, and later PATH candidate discovery.
5. Compile and attempt native startup with a fresh local data directory; record
   visual evidence only if the native window actually renders.

Constitution: no framework/runtime ownership, auth, persistence format, branding
or security-policy changes. Keep this one Linux contributor-build slice.
Risk: automatic Linux bundling now downloads/uses packagers instead of silently
selecting no supported package types. Use --no-bundle for a binary-only build.
Rollback: remove the Linux overlay and guide/test additions; no data migration.
Local portable sysroot is a verification aid, not a redistributable release or
an Ubuntu 22.04 compatibility claim. Release CI remains the governed baseline.

Provider risk: this is a compatibility check, not code signing or executable
authentication. Current Neko Core CLI prints `neko-core <version>`; unrecognized
output fails closed without reflecting raw probe output into diagnostics.
Bundled mismatch never falls back silently. Other providers are unchanged.
Rollback of the provider check restores the old false-positive behavior; do not
recommend rollback as a way to launch an unrelated executable.


## Design review decisions (2026-10-01)

- Keep the version-output contract at the native provider boundary; React and
  the process-containment implementation do not gain Neko-specific branches.
- Share one pure parser between bundled and installed discovery. Leave checksum
  verification and bundled-first precedence with their existing owners.
- Extract only the installed-candidate loop. It accepts resolved paths so real
  subprocess regression tests need no global PATH mutation or new dependency.
- Preserve stop-on-post-spawn-error semantics. Only a successful, fully reaped
  probe with an incompatible brand may continue to the next installed path.
- Avoid formatting unrelated code or adding a generic provider framework.

References informing these decisions (not certification of the whole product):

- [Robert C. Martin: The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html):
  keep boundary mechanisms from leaking into higher-level policy.
- [John Ousterhout: A Philosophy of Software Design, official second-edition extract](https://web.stanford.edu/~ouster/cgi-bin/aposd2ndEdExtract.pdf),
  sections 6.7-6.9 and 9.8-9.9: split by information hiding and total complexity,
  not an arbitrary function-length target.
- [Google: What to look for in a code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html):
  inspect design, scope, error paths and whether regressions actually fail.
- [Ham Vocke: The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html):
  complement parser tests with narrow integration tests at the subprocess boundary.
- [Tauri configuration files](https://v2.tauri.app/develop/configuration-files/):
  use the supported platform overlay rather than host-specific runtime branching.

The CLI contract was checked in both the pinned bundled Neko source
[`c03012a`](https://github.com/meiiie/neko-core/blob/c03012af31b81d04b13b8f65757f0f23d3cafe51/bin/neko.ts)
and current source
[`1cdd298`](https://github.com/meiiie/neko-core/blob/1cdd298579d2f9b07f65b3e94f42cebaf5ed5b72/bin/neko.ts).
Both print `neko-core <version>` for `--version`. This is a branding/token check,
not strict semantic-version parsing and not executable authentication.

## Verification limits

The full native suite has four pre-existing Signal Inbox failures after its
fixed 2026-09-30 fixture expiry. This change neither disables them nor changes
runtime expiry semantics. Full-suite formatting also has pre-existing drift;
no repository-wide formatting is included. Record current CI on the PR.
A local Debian debug build is not proof of Ubuntu 22.04, AppImage, Windows,
macOS, clean-install/upgrade or authenticated model-chat compatibility.
