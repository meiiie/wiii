# Neko Core inside the Wiii installer

Status: local implementation; owner approved investigation/integration 2026-10-01.
Owner subsequently requested the published Neko 1.7.0 runtime and an OpenCode
Space Bunny Free test. The bundle lock now pins the immutable v1.7.0 assets and
source commit 16860b031197b0df5ecf3613b72df7e10de4981e.
Issue: https://github.com/meiiie/wiii/issues/994

Depends on PR #993 for native Linux build defaults and provider identity checks.

## Outcome
A supported Wiii installer contains the reviewed, compatible Neko Core runtime.
First use does not require separately installing Neko, Node, Bun, or PATH edits.
Credentials/model configuration remain a separate user-controlled setup step.

## Acceptance
- Prepare exactly the version/target/bytes in the checked-in Neko bundle lock.
- Reject missing, truncated, oversized, corrupted or wrong-target bundles.
- Enable the bundle config in all governed installer build commands.
- Keep the bundled runtime under Wiii ownership and prevent its background
  self-update in child processes without modifying shared user settings.
- Preserve existing process-tree containment and bundled-first fail-closed rules.
- Prove native version discovery and ACP initialization without model calls.
- Test first run without a provider on PATH; keep account/history data untouched.

## Limits
A binary existing for an OS does not establish native provider containment.
Linux still requires usable bubblewrap; macOS remains host-unsupported until a
separate reviewed process-ownership implementation exists. No safety bypass.
No release publication, credentials, merge, or independent runtime updater.
