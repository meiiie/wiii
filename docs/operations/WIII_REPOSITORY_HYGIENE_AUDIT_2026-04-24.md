# Wiii Repository Hygiene Audit

Status: Active audit

Date: 2026-04-24

Scope: repository hygiene, cleanup verification, retained local artifacts, rebuild instructions

Non-scope: runtime bug fixes, application refactors, database migration repair

## Executive State

The repository cleanup pass is complete for documentation sprawl, generated artifacts, dependency folders, and untracked scratch output.

Current verified state:

- `git ls-files --others --exclude-standard` returns no files.
- Legacy tracked report trees have been removed from source control.
- Large local dependency/build outputs have been removed.
- Remaining dirty worktree entries are pre-existing modified source and test files; they are not cleanup residue.
- Remaining ignored files are either local configuration, local skills, MCP tooling, referenced data, or user/workspace-local material.

## Verification Snapshot

Commands used:

```powershell
git status --short --branch
git ls-files --others --exclude-standard
git ls-files -oi --exclude-standard
git diff --cached --check
```

Observed result:

- No untracked files remain.
- The cleanup PR contains documentation/governance changes and report-tree deletions.
- No unrelated modified source files were staged by the cleanup pass.

## Removed From Source Control

The following non-canonical report trees were removed from git:

- `.Codex/reports/`
- `.claude/reports/`
- `maritime-ai-service/.claude/reports/`
- `maritime-ai-service/.Codex/reports/`

Rationale:

- They were working-report locations, not stable product documentation.
- Durable findings were promoted into `docs/operations/`.
- Keeping thousands of report lines and screenshots in git made review, search, and release hygiene worse.

## Removed Locally

Generated or rebuildable local artifacts removed:

- `wiii-desktop/src-tauri/target`
- `wiii-desktop/node_modules`
- `wiii-desktop/dist`, `dist-embed`, `dist-web`
- `wiii-desktop/test-results`
- `wiii-desktop/playwright/screenshots`
- `maritime-ai-service/.venv`
- `.Codex/external`
- `.Codex/tmp`
- Python `__pycache__` directories
- `.ruff_cache`, `.pytest_cache`, `.hypothesis`
- logs and one-off smoke/test outputs

One-off local artifacts removed after inspection:

- Mojibake Vietnamese encoding debugger note.
- Mojibake COLREG markdown seed file.
- One-off local COLREG ingestion script.
- Local Playwright smoke/real-prompt configs and specs with mojibake prompts.
- Unreferenced sample PDFs.
- Unused local helper binaries `cloudflared.exe` and `sentrux.exe`.

## Retained Ignored Local Items

These are intentionally retained for now:

| Path | Reason |
|---|---|
| `tools/bin/rivemcp-win-x64.exe` | Local MCP binary used by `.mcp.json`; `.mcp.json` was corrected to point to this path. |
| `maritime-ai-service/data/VanBanGoc_95.2015.QH13.P1.pdf` | Referenced by ingestion and multimodal test scripts. |
| `.agents/` | Local Codex skills used by this workspace. |
| `AGENTS.md` | User-provided workspace instructions; ignored but currently used by the agent workflow. |
| `.env`, `.env.local`, `.env.production`, `.env.render`, `.env.soul-agi` | Environment and secret-bearing local configuration. |
| `.vscode/` | Local IDE task/launch/settings configuration. |
| `Documents/` | User/workspace research material outside product runtime. |

Do not delete these through broad cleanup commands.

## Known Residue

Several root `pytest-cache-files-*` directories remain at `0 KB`. Windows denied access to them during cleanup.

Handling:

- They are ignored by git.
- They do not materially affect disk usage.
- Retry after reboot or ACL correction if a completely empty filesystem view is required.

## Rebuild Instructions

Frontend dependencies were removed.

```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm install
npm run dev
```

Backend virtualenv was removed.

```powershell
cd E:\Sach\Sua\AI_v1\maritime-ai-service
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Do not run broad tests until dependencies are restored.

## Cleanup Guardrails

Avoid these commands in this repository unless there is an explicit reviewed plan:

```powershell
git clean -xfd
git clean -fdX
Remove-Item -Recurse -Force E:\Sach\Sua\AI_v1
```

Reason:

- Ignored paths include `.env*`, local skills, MCP tools, user documents, local data, and workspace instructions.
- A broad clean can delete required local runtime configuration.

Preferred controlled checks:

```powershell
git status --short --branch
git ls-files --others --exclude-standard
git ls-files -oi --exclude-standard
```

Preferred deletion policy:

- Delete only verified generated artifacts.
- Use explicit `-LiteralPath` targets.
- Verify resolved paths remain under `E:\Sach\Sua\AI_v1`.
- Keep source-like files until inspected.

## Follow-Up Decisions

Recommended next decisions:

- Decide whether `tools/bin/rivemcp-win-x64.exe` should remain local-only or be documented as an external prerequisite.
- Replace `VanBanGoc_95.2015.QH13.P1.pdf` script coupling with a documented fixture policy.
- Fix the pre-existing modified source/test files in separate implementation PRs.
- Resolve the Alembic `047` drift before any database schema work.
- Rebuild dependencies only when local testing resumes.
