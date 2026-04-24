# Wiii GitHub Governance

Status: Active

Owner: Project leadership

Last updated: 2026-04-24

Applies to: issues, pull requests, branch protection, reviews, CodeRabbit, labels, merge readiness, release hygiene

## Executive Policy

GitHub is the operational control plane for Wiii engineering work.

Every non-trivial change must be traceable from issue to branch to pull request to verification evidence. The default standard is not "code exists"; the standard is "reviewers can understand scope, risk, validation, and rollback without reconstructing the investigation from chat history."

For multi-agent work, also follow `WIII_MULTI_AGENT_MAINTAINER_PROTOCOL.md`.

## Required Flow

1. Open or link an issue for non-trivial work.
2. Create a branch from `main` using an explicit prefix.
3. Keep commits scoped and reviewable.
4. Open a draft PR early for visibility.
5. Move to ready-for-review only after verification evidence is present.
6. Merge only when branch protection, review, and risk gates pass.

## Branch Naming

Use these prefixes:

| Prefix | Use |
|---|---|
| `codex/` | Codex-authored implementation, docs, cleanup, or analysis work. |
| `fix/` | Human-authored production bug fix. |
| `feature/` | Product feature work. |
| `chore/` | Tooling, dependencies, cleanup, or build maintenance. |
| `docs/` | Documentation-only work. |
| `hotfix/` | Urgent production repair. Requires explicit issue and rollback note. |

Branch names should be short and outcome-based, for example `codex/docs-governance-cleanup`.

## Issue Rules

Use issue forms rather than blank issues.

Required issue properties:

- Clear problem or objective.
- Severity or category.
- Scope and non-scope.
- Acceptance criteria.
- Verification plan.
- Risk notes for auth, identity, memory, tenant isolation, migrations, provider/runtime behavior, or data exposure.

Do not use issues as vague reminders. If an issue cannot define success, it is not ready for implementation.

## Pull Request Rules

Every PR must include:

- Summary of user/system outcome.
- Linked issue or explicit reason no issue exists.
- In-scope and out-of-scope boundaries.
- PR owner, agents involved, owned paths, and conflict risk when multiple agents contribute.
- Exact verification commands and results.
- Rollback or recovery notes.
- Reviewer focus areas.

Every PR must avoid:

- Mixed unrelated changes.
- Hidden local environment changes.
- Secrets, tokens, real private data, or `.env*` files.
- Broad cleanup mixed with runtime behavior changes.
- Database schema changes without migration notes.

## Review Gates

Minimum review expectations:

- One approving review for normal changes.
- Owner review for auth, identity, memory, migration, tenant isolation, provider runtime, deployment, or GitHub governance changes.
- CodeRabbit review/check resolved or explicitly documented as not applicable.
- Screenshot or recording evidence for frontend-visible changes.
- Explicit test evidence or explicit explanation when tests are not run.

High-risk PRs require extra scrutiny:

- Auth/JWT/OAuth/LMS token exchange.
- Cross-tenant data access.
- Semantic memory or long-term user memory.
- Streaming persistence and chat history.
- Alembic migrations and schema changes.
- Provider selection/failover behavior.
- MCP/tool exposure.
- Release/deployment configuration.

## Branch Protection Recommendation

Configure `main` with:

- Require pull request before merge.
- Require at least one approval.
- Dismiss stale approvals when new commits are pushed.
- Require CODEOWNERS review.
- Require last push approval when available.
- Require conversation resolution before merge.
- Require the `CodeRabbit` status check.
- Require CI checks after backend/desktop/image workflows are stable on `main`.
- Require branches to be up to date before merge when practical.
- Block force pushes.
- Block branch deletion.
- Restrict who can bypass protections.

Recommended required checks:

- CodeRabbit.
- Backend unit tests.
- Desktop unit tests.
- Production image build when deployment files change.
- Lint/type checks when available.

Do not require currently failing CI checks until they are made consistently green on `main`; otherwise branch protection becomes noise instead of a control.

## CodeRabbit Policy

CodeRabbit is configured through `.coderabbit.yaml`.

Repository policy:

- Review draft PRs and incremental pushes.
- Use assertive review profile for security, correctness, and maintainability.
- Keep generated/dependency/local artifacts out of review scope.
- Apply path-specific instructions for auth, core config, multi-agent graph, RAG, living agent, MCP, migrations, frontend, GitHub automation, and operational docs.
- Suggest labels and reviewers, but do not auto-apply or auto-assign.
- Keep `request_changes_workflow` disabled until the team confirms CodeRabbit false-positive rate on real PRs.

Maintainers must resolve, defer, or explicitly reject CodeRabbit findings before merge. CodeRabbit does not replace human ownership.

## CODEOWNERS Policy

`CODEOWNERS` starts conservative with the repository owner as default owner.

As the team grows, split ownership by area:

- Backend platform.
- Frontend desktop.
- Auth/security.
- Data/migrations.
- AI runtime/provider layer.
- Documentation/governance.

Do not add fictional teams or inactive owners. CODEOWNERS must route reviews to people who can actually approve.

## Label Taxonomy

Recommended labels:

| Label | Meaning |
|---|---|
| `bug` | Defect or regression. |
| `enhancement` | Product or platform improvement. |
| `maintenance` | Cleanup, governance, tooling, dependency, or operational work. |
| `needs-triage` | Issue needs prioritization and ownership. |
| `priority:P0` | Release blocker, security/data risk, or production outage. |
| `priority:P1` | Major path broken or high-impact regression. |
| `priority:P2` | Important but workaround exists. |
| `area:backend` | Backend API/service/runtime. |
| `area:frontend` | Desktop/web UI. |
| `area:memory` | Semantic memory, core memory, identity continuity. |
| `area:auth` | Auth, OAuth, JWT, LMS token exchange. |
| `area:rag` | Retrieval, ingestion, embeddings, citations. |
| `area:mcp-tools` | MCP, tool registry, tool execution. |
| `area:docs` | Documentation and governance. |
| `risk:migration` | Database/schema risk. |
| `risk:security` | Security/privacy/tenant-isolation risk. |

Labels should clarify routing and risk. Avoid label sprawl.

## Commit Standard

Use concise conventional-style subjects:

- `fix: guard service identity memory writes`
- `feat: add host action capability matrix`
- `docs: add repository hygiene audit`
- `chore: remove legacy report artifacts`
- `test: cover stream cancellation persistence`

Commit rules:

- One logical change per commit.
- Do not commit generated caches or local dependency folders.
- Do not commit unrelated worktree changes.
- Do not amend shared commits unless explicitly agreed.

## Merge Strategy

Default strategy:

- Squash merge for multi-commit feature/docs/cleanup PRs.
- Rebase merge only for clean linear human-curated commits.
- Merge commit only when preserving branch topology matters.

PR title should become the squash commit title.

## Release Readiness

A PR is release-ready only when:

- Issue acceptance criteria are satisfied.
- Verification evidence is present.
- Documentation is updated when behavior, operations, or public contracts change.
- Rollback path is documented.
- Feature flags and defaults are understood.
- No unrelated modified files are included.

## Cleanup and Generated Artifacts

Repository hygiene rules:

- Do not commit `.Codex/reports/`, `.Codex/tmp/`, `.Codex/external/`, `.claude/reports/`, dependency folders, caches, logs, screenshots, or local test outputs.
- Promote durable findings into `docs/operations/` or the relevant product docs.
- Keep cleanup PRs separate from behavior changes.
- Use explicit deletion targets instead of broad clean commands.

## Emergency Work

For urgent production fixes:

1. Open a `hotfix/` branch.
2. Link an incident or bug issue.
3. Keep scope minimal.
4. Include exact rollback.
5. Backfill tests and documentation immediately after stabilization.

Hotfix urgency does not waive review. It changes review speed, not review quality.
