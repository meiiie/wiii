# Wiii Branch Protection Bypass Log

Required by `docs/operations/WIII_BRANCH_PROTECTION.md`, section "Bypass and emergency repair".

Every bypass event is appended here within 24 hours. Format:

```
### <date> — <actor> — <branch>

- Reason:
- Linked incident / ticket:
- Protection change applied:
- Merged PRs / commits produced during bypass:
- Re-enable confirmation:
- Follow-up:
```

---

## 2026-04-24 — @meiiie — main

- **Reason**: Initial self-merge after branch protection was activated on `main` (CodeRabbit required status, 1 approving review, code owner review, require-last-push-approval). The repo had a single code owner (@meiiie) who was also the author of both PRs. GitHub forbids a PR author from self-approving, so the protection could not be satisfied by any in-workflow action. Two PRs were blocked.
- **Linked incident / ticket**: None (initial setup — PRs were #6 and #7). Future events should link a GitHub issue.
- **Protection change applied**: `DELETE /repos/meiiie/wiii/branches/main/protection` to temporarily remove all rules. Original config was captured via `GET` before the delete and restored verbatim after the merges via `PUT`.
- **Merged PRs / commits produced during bypass**:
  - PR #6 — `docs + chore: governance gap close + naming migration (CoC, Dependabot, agent template, branch protection)` — merged as squash commit `4c29c4e`.
  - PR #7 — `fix + feat: demo stabilization bundle (Gemini 2.5 compat, magic-link dev, admin embed, SOTA search)` — merged as squash commit `db0efe2`.
- **Re-enable confirmation**: `PUT /repos/meiiie/wiii/branches/main/protection` succeeded with the exact pre-bypass payload. `gh api repos/meiiie/wiii/branches/main/protection` post-restore shows `required_status_checks.contexts: ["CodeRabbit"]`, `enforce_admins.enabled: true`, `required_pull_request_reviews.required_approving_review_count: 1`, `require_last_push_approval: true`, `require_code_owner_reviews: true`, `required_conversation_resolution.enabled: true`. Configuration matches pre-bypass verbatim.
- **Follow-up**:
  - Add a second code-owner account (human or dedicated maintainer bot) so future PRs from @meiiie can satisfy review requirements without bypass. Tracked in `docs/operations/WIII_BRANCH_PROTECTION.md` "Agent identity and attribution" section — suggested accounts: `wiii-codex[bot]`, `wiii-claude[bot]`.
  - Until a second owner exists, future self-authored PRs will need the same documented bypass. Three bypasses per quarter triggers a protection-policy review per `WIII_BRANCH_PROTECTION.md`.
  - Open an Ops issue for "provision secondary code owner for main".

---
