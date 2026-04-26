# Wiii Codex Review Setup

Status: Proposed

Owner: Project leadership

Last updated: 2026-04-26

Applies to: Codex GitHub code review, ChatGPT Codex settings, pull request review policy, AI review triage

Related issue: https://github.com/meiiie/wiii/issues/121

## Purpose

This document defines how Wiii should enable and operate native Codex Review on GitHub without weakening the existing CodeRabbit, CODEOWNERS, branch protection, and human-maintainer review model.

Codex Review is useful for a second AI reviewer that can focus on production-impacting issues, especially auth, tenant isolation, semantic memory, streaming, RAG, MCP/tool exposure, migrations, and GitHub automation. It is not a substitute for maintainers.

## Official Setup Flow

OpenAI's GitHub integration documentation defines the setup path:

1. Set up Codex cloud for the ChatGPT account or workspace.
2. Open Codex Settings: https://chatgpt.com/codex/settings
3. Turn on `Code review` for `meiiie/wiii`.
4. To request a manual review, comment on a pull request with:

```text
@codex review
```

5. Optional: turn on `Automatic reviews` in Codex Settings so Codex reviews every PR opened for review.

Official references:

- Codex GitHub integration: https://developers.openai.com/codex/integrations/github
- Codex availability by ChatGPT plan: https://help.openai.com/en/articles/11369540-codex-in-chatgpt

Important limitation: repository files cannot enable the ChatGPT-side toggle. A signed-in ChatGPT/Codex user with GitHub access to `meiiie/wiii` must enable it in Codex Settings.

## Current Repository Readiness

As of 2026-04-26:

- Repository: `meiiie/wiii`
- Default branch: `main`
- GitHub account used for setup inspection: `meiiie`
- Permission: `ADMIN`
- Existing review automation: CodeRabbit via `.coderabbit.yaml`
- Existing code ownership: `.github/CODEOWNERS`
- Existing PR template: `.github/PULL_REQUEST_TEMPLATE.md`
- Added by this setup work: top-level `AGENTS.md` with Wiii-specific `## Review guidelines`

## Recommended Operating Policy

Use Codex Review in this order:

1. Enable `Code review` for `meiiie/wiii`.
2. Keep `Automatic reviews` off for the first few PRs if the team wants a low-noise rollout.
3. Request manual Codex review on sensitive PRs with a focused prompt:

```text
@codex review for auth, tenant isolation, memory persistence, streaming correctness, RAG source handling, MCP/tool exposure, migrations, and GitHub governance regressions
```

4. After three to five useful reviews with acceptable noise, consider enabling `Automatic reviews`.
5. Keep CodeRabbit enabled. CodeRabbit remains the required status-check automation; Codex Review is an additional review signal unless maintainers decide otherwise later.

## PR Author Expectations

For PRs where Codex Review is requested or automatic review is enabled:

- Resolve real P0/P1 findings before merge.
- If a finding is false positive or intentionally deferred, document the rationale in the PR conversation.
- If Codex does not run, state `Codex Review: not run` in the PR body and explain why when the PR is high risk.
- Do not merge sensitive changes solely because automated reviewers are quiet. Human ownership still applies.

Sensitive paths include:

- `maritime-ai-service/app/auth/**`
- `maritime-ai-service/app/core/**`
- `maritime-ai-service/app/engine/**`
- `maritime-ai-service/app/repositories/**`
- `maritime-ai-service/app/mcp/**`
- `maritime-ai-service/alembic/**`
- `wiii-desktop/src/**` when changes affect auth, streaming, persistence, admin, org, memory, or embed behavior
- `.github/**`

## Rollout Checklist

- [ ] Merge the repository-side setup PR that adds `AGENTS.md` and this runbook.
- [ ] Open https://chatgpt.com/codex/settings with the ChatGPT account that has access to `meiiie/wiii`.
- [ ] Enable `Code review` for `meiiie/wiii`.
- [ ] Open or use a small PR and comment `@codex review`.
- [ ] Confirm Codex reacts and posts a GitHub code review.
- [ ] Record first-review outcome in the PR conversation.
- [ ] Decide whether to enable `Automatic reviews`.

## Noise Control And Rollback

If Codex reviews are noisy:

1. Turn off `Automatic reviews` first.
2. Keep manual `@codex review` available for sensitive PRs.
3. If manual review is still not useful, disable `Code review` for `meiiie/wiii` in Codex Settings.
4. Revert this docs/governance setup only if the team decides not to use Codex Review at all.

## Maintainer Notes

Codex reads the closest `AGENTS.md` file to changed files and follows `## Review guidelines`. Start with the top-level file. Add package-level `AGENTS.md` only if a subtree needs materially different review rules.

Codex Review currently should not be added as a required GitHub status check for Wiii. Treat it as a code-review signal, while CodeRabbit remains the configured required automated check.
