# Getting Help with Wiii

Thanks for using Wiii. Before filing a new issue, please pick the right channel — most help requests are routed faster outside the issue tracker.

## What belongs where

| Need | Channel |
|---|---|
| "How do I set up Wiii locally?" | `README.md` → Quick Start, then `CONTRIBUTING.md` |
| "I think I found a bug." | Open a `Bug Report` issue (`.github/ISSUE_TEMPLATE/bug_report.yml`) |
| "Can Wiii do X / I want Wiii to do Y." | Open a `Feature Request` issue |
| "I need an operational change / hygiene / CI task." | Open an `Operations` issue |
| "I'm an AI agent and I found something." | Open an `Agent Finding` issue (`.github/ISSUE_TEMPLATE/agent_finding.yml`) |
| "I think I found a security vulnerability." | **Do not open a public issue.** Follow `SECURITY.md` |
| "I want to discuss an idea before filing a feature." | GitHub Discussions (if enabled) or a `Feature Request` marked "discussion only" |
| "My code of conduct concern is…" | Email **conduct@wiii.lab** privately |

## Before opening an issue

Please confirm each of the following. Issues that skip this usually get closed or redirected:

1. **Search existing issues.** Filter by `state:any`. The problem may already be tracked or intentionally deferred.
2. **Reproduce on `main`.** If you're on an older branch, rebase onto `main` and confirm the problem still happens.
3. **Attach evidence.** Backend logs, desktop DevTools console output, exact prompt and response, screenshot, or recording. `cat`-able text is best.
4. **State the environment.** OS, browser, running via Tauri desktop vs web vs iframe embed, Docker Compose vs bare uvicorn, and which commit hash you're on.

## Issue templates and how to pick one

- **Bug Report** — something is broken relative to documented or recent behavior. You can reproduce it.
- **Feature Request** — you want a capability that doesn't exist, or behavior that is inconsistent with how the product should work.
- **Operations** — cleanup, governance, CI, documentation, dependency, or infrastructure work. The outcome is operational, not product.
- **Agent Finding** — an AI agent (Codex, Claude, or other) produced a signal worth filing but the work hasn't been scoped by a human yet. Includes provenance fields so maintainers can triage agent output.

## For AI agents filing issues

Use the `Agent Finding` template. Fill in:

- Agent name and model.
- Confidence level.
- Source of signal (audit run, test failure, review comment, code scan).
- Suggested owner path (so CODEOWNERS routing works).

Do **not** file the same finding under multiple templates. If a human takes ownership, they will convert it to the right type.

## Response expectations

- Bug reports with `severity: P0 / P1` are acknowledged within 1 working day.
- P2 / P3 bugs and feature requests enter triage weekly.
- Operations issues move as capacity allows; security issues override the queue.

## Support questions outside the issue tracker

- Project contact: **meokhp888@gmail.com** (maintainer, The Wiii Lab)
- Security: follow `SECURITY.md`
- Conduct: conduct@wiii.lab

Please keep usage help out of the issue tracker. The tracker is for actionable engineering work — issues without a clear outcome tend to accumulate and drown the real signal, especially when multiple AI agents are filing in parallel.
