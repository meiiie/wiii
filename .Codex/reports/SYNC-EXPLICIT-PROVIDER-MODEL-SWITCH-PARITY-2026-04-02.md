# Sync Explicit-Provider Model Switch Parity - 2026-04-02

## Summary
- Fixed a sync-lane bug where an explicit provider failure could be swallowed and turned into a generic direct fallback answer.
- Sync now preserves `ProviderUnavailableError` semantics through the route/direct path so `/api/v1/chat` can surface `PROVIDER_UNAVAILABLE` cleanly with `model_switch_prompt`.

## Root Cause
- `SupervisorAgent.route()` used a broad `except Exception` and fell back to `rule_based` routing.
- `direct_response_node_impl()` also swallowed provider failures and produced a generic fallback answer (`Xin chao! ...`) instead of propagating the provider outage.
- Together, those two catches could make sync look like it “worked” even though the selected provider was no longer available.

## Changes
- Re-raise `ProviderUnavailableError` in:
  - `maritime-ai-service/app/engine/multi_agent/supervisor.py`
  - `maritime-ai-service/app/engine/multi_agent/direct_node_runtime.py`
- If direct lane has an explicit user provider and no LLM can be resolved, it now raises `ProviderUnavailableError` instead of silently falling back.
- Added focused regression tests:
  - `maritime-ai-service/tests/unit/test_supervisor_agent.py`
  - `maritime-ai-service/tests/unit/test_direct_node_provider_errors.py`
- Stabilized presenter test so it no longer depends on live selectability state:
  - `maritime-ai-service/tests/unit/test_chat_endpoint_presenter.py`

## Verification
- Focused backend suite:
  - `60 passed`
- Patched ASGI smoke:
  - request: `/api/v1/chat` with `provider=google`
  - result: `503 PROVIDER_UNAVAILABLE`
  - payload includes:
    - `provider=google`
    - `reason_code=busy`
    - `model_switch_prompt`

## Current Truth
- Stream path was already the primary UX and remained correct.
- Sync explicit-provider path is now much closer to parity with stream for hard provider failure handling.
- This fix is about **truthful failure surfacing**, not about visible thinking quality.
