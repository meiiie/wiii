# Wiii Local Demo Runbook

Status: Active

Owner: Wiii maintainers

Last updated: 2026-04-28

Tracking issue: #168

## Purpose

This runbook defines the local demo path that maintainers should use before
showing Wiii to reviewers, judges, or stakeholders.

The goal is not only to make the UI load. The goal is to prove that the demo
uses the same session contract as the desktop app:

```text
local frontend
-> dev-login JWT
-> authenticated user profile
-> admin/org permissions
-> sync chat
-> SSE V3 stream completion
```

## Expert Operating Principle

High-reliability agent systems such as ChatGPT, Claude Code, and the OpenAI
Agents SDK avoid magical demo state. They make identity, session, runtime
steps, tools, guardrails, and traces explicit.

For Wiii local demos this means:

- Use dev-login JWT for localhost demos, not a hand-entered API key.
- Treat API keys as service-to-service credentials, not the browser demo login.
- Confirm the active user has platform admin and organization owner/admin
  permissions before presenting admin features.
- Confirm both sync chat and SSE V3 stream finish successfully before judging
  frontend chat quality.
- Fail loudly when a provider key, stream event, auth state, or organization
  permission is wrong.

## Local Login Contract

Recommended local demo login:

1. Open the local frontend at `http://127.0.0.1:1420/`.
2. Click `DEV - Dang nhap nhanh - Local Dev`.
3. Confirm the active user is `dev@localhost`.
4. Confirm the user has `platform_role=platform_admin`.
5. Confirm the target organization, normally `default`, reports
   `org_role=owner` or `org_role=admin`.

Do not use a random API key in the frontend for local judge/demo sessions. A
stale or invalid API key can make the UI look broken even when the JWT path is
healthy.

Production note:

- Dev-login must stay disabled in production.
- Production user login should use approved OAuth/LMS identity flows.
- Production service clients may use API-key or LMS service-token paths only
  where those paths are explicitly intended.

## One-Command Smoke Gate

From `maritime-ai-service/`:

```bash
python scripts/local_demo_smoke.py
```

Useful variants:

```bash
python scripts/local_demo_smoke.py --skip-frontend
python scripts/local_demo_smoke.py --provider google --model gemini-2.5-flash
python scripts/local_demo_smoke.py --org-id maritime-lms
python scripts/local_demo_smoke.py --skip-chat --skip-stream
```

Default checks:

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `GET /api/v1/health`
- frontend reachability at `http://127.0.0.1:1420/`
- `GET /api/v1/auth/dev-login/status`
- `POST /api/v1/auth/dev-login`
- `GET /api/v1/users/me`
- `GET /api/v1/users/me/admin-context`
- `GET /api/v1/organizations/{org_id}/permissions`
- `POST /api/v1/chat`
- `POST /api/v1/chat/stream/v3`

The smoke gate is intentionally live. If it fails, the local demo is not ready.
Use `--skip-chat` or `--skip-stream` only when isolating infrastructure from
provider/LLM failures.

## Browser State Recovery

If the frontend still sends an old API key or appears logged in as the wrong
identity, clear only Wiii local state in the browser console:

```js
localStorage.removeItem("wiii:auth_state");
localStorage.removeItem("wiii:wiii_auth_tokens");
localStorage.removeItem("wiii:app_settings");
location.reload();
```

Then use the dev-login button again.

## OpenAI Agents SDK Lessons For Wiii

The OpenAI Agents SDK is a good design reference, but Wiii should not add it as
a runtime dependency while WiiiRunner is already active.

Reference: https://openai.github.io/openai-agents-python/

Patterns Wiii should adopt over time:

- Runner contract: one explicit run loop with max turns, handoff decisions,
  tool execution, and final output conditions.
- Model provider contract: provider lookup, stream and non-stream calls, and
  provider override via run config.
- Session contract: persisted conversation/session items separated from model
  input filtering.
- Tool contract: schema, timeout, approval, input guardrail, output guardrail,
  and clear failure behavior live with the tool definition.
- Guardrail contract: input, output, and tool guardrails should be explicit and
  fail closed when they protect privacy, tenant boundaries, or safety.
- Tracing contract: each run should expose spans for agent steps, model calls,
  tools, handoffs, guardrails, and finalization.

Recommended Wiii sequence:

1. Stabilize local demo and runtime smoke gates.
2. Add `WiiiRunConfig` and `WiiiModelProvider` contracts inspired by the SDK.
3. Add tool policy/guardrail/timeouts before expanding MCP/tool surfaces.
4. Add trace spans before deleting more compatibility/runtime shells.
5. Continue LangGraph cleanup only after golden chat, stream, memory, tool, and
   provider parity tests are green.

## Failure Triage

If health fails:

- Check Docker services and backend logs first.
- Do not debug the frontend until backend readiness is green.

If dev-login status is disabled:

- Confirm local environment flags enable dev-login.
- Do not bypass by using a frontend API key.

If admin context fails:

- Confirm `dev@localhost` has `platform_admin`.
- Confirm organization membership exists for the demo org.

If org permissions fail:

- Confirm the demo org id is correct.
- Confirm the user has `owner` or `admin` in `user_organizations`.

If sync chat or stream fails:

- Inspect provider configuration and model availability.
- Re-run with an explicit provider/model if needed.
- Treat missing SSE `done` as a real stream contract failure.

## Rollback

This runbook and `scripts/local_demo_smoke.py` are operational aids only. To
rollback, remove them from the PR. No database migration or production runtime
change is involved.
