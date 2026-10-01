# Implementation plan

1. Build a standard-library preparation/check tool with streamed size/hash
   verification, same-directory staging and idempotent reuse of a valid bundle.
2. Wire preparation and the existing resource overlay into the release matrix.
3. Propagate bundled origin into process-local update policy; keep external CLI
   settings, executable ownership and user configuration unchanged.
4. Exercise the pinned Linux artifact, native loader and ACP initialization in
   a fresh local profile. Add negative package and policy regression tests.
5. Verify Windows/macOS packaging in their own environments before any release
   claim; document unsupported runtime hosts, not just artifact availability.

One owner writes this branch. Do not change Neko Core source or merge team work
without reconciling its handoff. Keep this slice separate from PR #993.
The owner highlighted Neko 1.7.0: validate its published assets and exact tag
commit, then advance the lock only after the real Linux ACP fixture passes.
Rollback restores previous installer recipes; no data migration is proposed.


## Verification checkpoint

Neko 1.7.0 was verified against the immutable official GitHub release's asset
sizes/digests and annotated tag's peeled source commit. Linux bytes were streamed
and SHA-256 verified; other target metadata is pinned, not runtime-tested.

- Release tooling: 41 tests passed; provider/loader: 23 + 3 tests passed.
- Focused desktop UI/control tests: 58 passed; TypeScript and Clippy passed.
- Repository tests: 445 passed; aggregate harness: 5/5 passed.
- Native build and .deb preparation succeeded; extracted runtime matches lock.
- Native UI identified the supplied runtime. The reusable Linux smoke executes
  initialize/session-new/prompt against the real Neko and a loopback fake model.
  This validates transport, not model quality or external authentication.
- Full native baseline remains 151 passed, 4 failed, 4 ignored after this slice;
  the four failures are the known expired Signal Inbox fixtures also failing #993.
- Windows/macOS execution, AppImage, system installation/upgrade and real account
  inference are unverified. macOS provider containment remains unsupported.

A direct public Space Bunny Free API probe returned HTTP 200, the requested
short response and cost 0. The same model through Neko 1.7.0's Zen adapter fails
its allowlisted-family routing before dispatch. Account OAuth uses a distinct
catalog-driven adapter and must be evaluated after explicit user sign-in. No
credential, account identifier or private prompt is part of this source change.


The Neko team has already added the exact `space-bunny-free` transport mapping
in draft neko-core PR #77 (head 55bf32bb41617583cde69224b0233a623c875f39).
Do not duplicate that fix or mislabel a candidate as immutable v1.7.0. Paired
acceptance must use a clearly identified candidate or a supported account route.


The owner approved an isolated OpenCode Account login. The device flow could
start, but the cloud executor subsequently denied outbound access to OpenCode
while polling authorization. No login file was created in the test profile.
Do not describe the real Wiii/Bunny demo as successful, repeat login blindly or
route around the environment restriction. No credentials are included here.
