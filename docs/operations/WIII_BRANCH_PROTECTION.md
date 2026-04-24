# Wiii Branch Protection Policy

Status: Active

Owner: Project leadership

Last updated: 2026-04-24

Applies to: `main`, release branches, hotfix branches, merge-queue config, required checks, review requirements, agent PR hygiene

## Why this document exists

Branch protection is configured in GitHub's UI, not in a file. If the UI config drifts from policy, the repo quietly loses its guarantees. This document is the single source of truth: maintainers reconcile GitHub settings against this file, and any change to policy must land here first.

This matters more for Wiii than for a typical repo because multiple AI agents (Codex, Claude, CodeRabbit, and more in future) file pull requests in parallel. Without branch protection that is explicit and strict, agent-volume alone can merge unreviewed behavioral changes.

## `main` — Required Settings

Configure under **Settings → Branches → Branch protection rules → `main`**.

### Review requirements

- **Require a pull request before merging**: ✅
- **Required approving reviews**: **1 minimum** (2 for any PR that touches `app/auth/**`, `app/core/**`, `alembic/**`, or `.github/workflows/**`)
- **Dismiss stale reviews when new commits are pushed**: ✅
- **Require review from Code Owners**: ✅
- **Restrict who can dismiss reviews**: maintainers only
- **Allow specified actors to bypass required pull requests**: ❌ (even hotfixes go through a PR — use a fast path with reduced review count, never a bypass)

### Status check requirements

- **Require status checks to pass before merging**: ✅
- **Require branches to be up to date before merging**: ✅
- **Required status checks** (exact names must match the workflow jobs):
  - `Lint` (from `ci.yml`)
  - `Unit Tests` (from `ci.yml`)
  - `Docker Build` (from `ci.yml`)
  - `test-backend` (from `test-backend.yml`)
  - `test-desktop` (from `test-desktop.yml`)
  - `CodeRabbit` commit status (set by `.coderabbit.yaml`'s `fail_commit_status: true`)

### Merge rules

- **Require conversation resolution before merging**: ✅ (CodeRabbit-suggested conversations count)
- **Require signed commits**: ✅ (humans use GPG/SSH signing; agents sign with an attributable identity — see _Agent identity_ below)
- **Require linear history**: ✅ (squash or rebase — no merge commits)
- **Require deployments to succeed before merging**: ❌ (deployments are manual for now)
- **Lock branch**: ❌
- **Do not allow bypassing the above settings**: ✅ (applies to admins too — bypass becomes an explicit policy change via PR to this file)

### Push rules

- **Restrict who can push to matching branches**: ✅ (only merge-queue automation or maintainer-triggered merge)
- **Allow force pushes**: ❌
- **Allow deletions**: ❌

### Merge queue (recommended once agent PR volume > ~20/week)

- **Require merge queue**: ✅
- **Merge method**: Squash
- **Build concurrency**: 5
- **Minimum group size**: 1 (one PR per queue entry — merging groups risks coupling unrelated changes)
- **Maximum group size**: 3
- **Wait time before merging**: 5 minutes (lets CodeRabbit finish async review)

## Release branches (`release/*`, `hotfix/*`)

Same rules as `main`, except:

- Only maintainers can create or merge
- Backports must link to the original `main` PR
- Hotfix branches must include a rollback note in the PR body

## Branch naming — enforced via CODEOWNERS and workflow

Branch prefixes and their meaning live in `docs/operations/WIII_GITHUB_GOVERNANCE.md` (`codex/`, `fix/`, `feature/`, `chore/`, `docs/`, `hotfix/`). Mergeable PRs must originate from one of these prefixes.

## Agent identity and attribution

Automated agents that push commits or open PRs must:

1. Use a **dedicated bot GitHub account** (recommended: `wiii-codex[bot]`, `wiii-claude[bot]`). Shared real-human credentials are prohibited.
2. **Sign commits** using the bot account's verified key.
3. Record the producing model in the commit trailer, for example:
   ```
   Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
   Co-Authored-By: Codex gpt-5-mini <noreply@openai.com>
   ```
4. Open PRs as the bot account. A human PR owner declares themselves in the PR template's `PR owner` field and is accountable for the final diff.

Why: agent-produced commits under a human's account distort attribution and make post-incident review harder. A bot account with a verified key is explicit and revocable.

## Bypass and emergency repair

- Bypassing branch protection requires a human maintainer to temporarily disable the rule, perform the change, then re-enable.
- Every bypass event must:
  - Be logged in `docs/operations/BYPASS_LOG.md` within 24 hours.
  - Include: date, actor, branch, reason, linked incident ticket, re-enable confirmation.
- Repeated bypasses (3+ per quarter) trigger a policy review PR to this file.

## Dependabot and automated PRs

- Dependabot PRs inherit the same review gate (1 reviewer, CodeRabbit) but may use a reduced check set (lint + unit tests only) to let security patches merge quickly.
- Auto-merge is permitted **only** for:
  - Patch updates
  - Security-only updates
  - Grouped updates explicitly allow-listed in `.github/dependabot.yml`
- Any major-version Dependabot PR must be reviewed manually.

## Review escalation for sensitive paths

For PRs touching any of these paths, require 2 approvals and explicit CodeRabbit sign-off:

- `maritime-ai-service/app/auth/**` — identity, tokens, OAuth flows
- `maritime-ai-service/app/core/security*.py` — authorization, role resolution
- `maritime-ai-service/alembic/**` — database schema and migrations
- `.github/workflows/**` — CI / automation surface
- `maritime-ai-service/app/mcp/**` — external tool exposure

These paths are also flagged in `.coderabbit.yaml` `path_instructions` for deeper review.

## Reconciliation checklist (run quarterly)

Maintainer re-walks this list each quarter and opens an `Operations` issue for any drift:

1. GitHub UI `main` rule matches the _Required Settings_ section above.
2. `CODEOWNERS` file is current (no orphaned teams, all paths have at least one owner).
3. `.github/workflows/*.yml` job names still match the _Required status checks_ list.
4. `.coderabbit.yaml` is present and has not been disabled.
5. Dependabot auto-merge allowlist has not silently expanded.
6. No bypass events were unlogged.
7. Bot accounts still have their signing keys valid.

## Related Documents

- `docs/operations/WIII_GITHUB_GOVERNANCE.md` — the broader GitHub workflow policy.
- `docs/operations/WIII_MULTI_AGENT_MAINTAINER_PROTOCOL.md` — agent ownership rules.
- `CODE_OF_CONDUCT.md` — contributor behavior baseline.
- `SECURITY.md` — vulnerability disclosure.
- `CONTRIBUTING.md` — branching, commits, review expectations for contributors.
