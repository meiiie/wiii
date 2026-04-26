# Wiii GitHub Hardening Checkpoint

Status: Active

Owner: Project leadership

Last updated: 2026-04-26

Applies to: GitHub repository settings, branch protection, automated review, CI gates, dependency security, code scanning, and secret scanning.

## Executive Summary

This checkpoint records the GitHub hardening baseline applied on 2026-04-26 for a multi-agent development model.

The goal is to make automated changes safer by combining branch protection, human ownership, CodeRabbit, Codex Review, stable merge gates, dependency security, and code scanning. These controls reduce the chance that agent-authored work can bypass review, weaken sensitive paths, or merge without a reproducible verification signal.

## Settings Applied Directly

The following repository settings were applied through the GitHub API:

- Dependabot vulnerability alerts enabled.
- Dependabot automated security fixes enabled.
- Auto-merge enabled, gated by branch protection.
- Squash merge enabled.
- Merge commits disabled.
- Rebase merge disabled.
- Delete branch on merge enabled.
- Update branch button enabled.
- Secret scanning enabled.
- Secret scanning push protection enabled.

The following branch protection controls are active on `main`:

- Pull request required before merge.
- One approving review required.
- CODEOWNERS review required.
- Stale approvals dismissed on new commits.
- Last push approval required.
- Conversation resolution required.
- Branch must be up to date before merge.
- CodeRabbit required as a status check.
- Admin enforcement enabled.
- Linear history required.
- Force pushes disabled.
- Branch deletion disabled.

## Version-Controlled Hardening

This PR adds:

- `.github/workflows/merge-gate.yml`: an always-on gate with stable `Gate Summary` status.
- `.github/workflows/codeql.yml`: CodeQL analysis for Python and JavaScript/TypeScript.
- Explicit workflow permissions and concurrency controls for existing workflows.
- Stricter CodeRabbit policy: assertive profile, failed commit status on review failures, draft review, and incremental review.

## Required Check Rollout

Do not add `Gate Summary` to branch protection until `.github/workflows/merge-gate.yml` is merged into `main`.

Post-merge required checks should be:

- `CodeRabbit`
- `Gate Summary`

Optional later required checks, once stable across several PRs:

- `CodeQL Analyze (python)`
- `CodeQL Analyze (javascript-typescript)`

## Secret Scanning Operations

Secret scanning alerts must be handled as incident-grade work:

1. Identify the provider and credential type in the GitHub Security tab.
2. Revoke or rotate the credential in the provider console.
3. Remove the credential from the current tree if it still exists.
4. Decide whether history rewrite is worth the operational risk. For already-public secrets, rotation is mandatory even if history is later rewritten.
5. Resolve the GitHub alert only after rotation is confirmed.
6. Record the rotation in private operational notes, not in public docs or issues.

Do not mark an alert as false positive or resolved only because the secret is old.

## Operating Policy

For multi-agent PRs:

- Keep one owner responsible for merge readiness.
- Declare agent ownership in the PR body.
- Require CodeRabbit and Codex Review for security-sensitive changes.
- Resolve or explicitly defer all P0/P1 automated findings.
- Prefer squash merge so agent-authored intermediate commits do not become long-lived history.
- Use `Gate Summary` as the stable branch protection CI context after this workflow lands on `main`.

## Follow-Up

- Add `Gate Summary` to required branch protection checks after this PR is merged.
- Watch the first three PRs after rollout for false positives or excessive runtime.
- Keep CodeQL advisory at first; make CodeQL required only after it is consistently green.
- Rotate any active credentials reported by secret scanning before resolving those alerts.
