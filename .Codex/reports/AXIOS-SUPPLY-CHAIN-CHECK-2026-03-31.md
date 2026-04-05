# Axios Supply-Chain Check - 2026-03-31

## Scope

- Workspace: `E:\Sach\Sua\AI_v1`
- Primary JS app: `E:\Sach\Sua\AI_v1\wiii-desktop`
- Date checked: `2026-03-31`

## External Incident Verification

Independent 2026 incident writeups confirm a live npm compromise affecting:

- `axios@1.14.1`
- `axios@0.30.4`
- injected dependency `plain-crypto-js@4.2.1`

Sources reviewed:

- StepSecurity: `axios Compromised on npm - Malicious Versions Drop Remote Access Trojan`
  - https://www.stepsecurity.io/blog/axios-compromised-on-npm-malicious-versions-drop-remote-access-trojan
- Socket: `Supply Chain Attack on Axios Pulls Malicious Dependency from npm`
  - https://socket.dev/blog/axios-npm-package-compromised

Both sources state that if a system installed the affected versions, it should be treated as potentially compromised.

## Local Repo Findings

### 1. Direct dependency check

File checked:

- `E:\Sach\Sua\AI_v1\wiii-desktop\package.json`

Result:

- No direct `axios` dependency
- No direct `plain-crypto-js` dependency

### 2. Lockfile check

File checked:

- `E:\Sach\Sua\AI_v1\wiii-desktop\package-lock.json`

Result:

- No `axios` entry
- No `plain-crypto-js` entry

### 3. Installed dependency tree check

Command run from `E:\Sach\Sua\AI_v1\wiii-desktop`:

```powershell
npm ls axios --all
npm ls plain-crypto-js --all
```

Observed output:

```text
wiii-desktop@1.0.0 E:\Sach\Sua\AI_v1\wiii-desktop
`-- (empty)
```

for both packages.

Interpretation:

- The actual installed tree for the app does not include `axios`
- The actual installed tree for the app does not include `plain-crypto-js`

### 4. Source/workspace usage search

Checked source/manifests/docs in the workspace while excluding:

- `node_modules`
- `.venv`
- `.Codex/external`
- `.Codex/tmp`
- build/dist/coverage directories

Result:

- No workspace match for `axios`
- No workspace match for `plain-crypto-js`

## Important Nuance

Earlier noisy hits came from package metadata inside `node_modules`, such as other packages' own `package.json` development metadata. That does **not** mean Wiii depends on `axios` at runtime. The authoritative checks are:

- app manifest
- app lockfile
- `npm ls`

All three came back clean for the live Wiii desktop app.

## Conclusion

At the time of this audit, the main Wiii workspace checked here does **not** use `axios` in its app dependency graph, and there is no evidence that `plain-crypto-js` is present in the installed app tree.

Because neither package is present in the active dependency graph:

- there is nothing to remove right now
- there is nothing to pin or freeze right now

## Recommendation

Keep monitoring, but no emergency package removal is required for the checked Wiii desktop app based on the current dependency graph.
