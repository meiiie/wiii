# Failover Hardening - 2026-04-02

## Scope
- Harden runtime failover so Gemini outages do not collapse Wiii into `rule_based` too early.
- Keep supervisor house routing as a **preferred primary**, not a strict provider pin.
- Expand invoke-time failover beyond quota/timeout into auth/provider-down failures.

## What Changed

### 1. Supervisor house routing no longer pins failover
- File: `maritime-ai-service/app/engine/multi_agent/supervisor.py`
- Change:
  - `SupervisorAgent._get_llm_for_state()` now calls:
    - `AgentConfigRegistry.get_llm(..., provider_override=house_provider, strict_provider_pin=False)`
- Result:
  - House routing still prefers the best runtime provider for Wiii's conductor layer.
  - But if that provider fails during invocation, downstream failover can still switch to `zhipu/openrouter/ollama`.

### 2. Agent config now supports provider preference without strict pinning
- File: `maritime-ai-service/app/engine/multi_agent/agent_config.py`
- Changes:
  - Added `strict_provider_pin: bool = True` to `AgentConfigRegistry.get_llm(...)`
  - Non-strict override path now:
    - treats `provider_override` as a preferred primary
    - resolves runtime provider via `_resolve_auto_provider(...)`
    - does **not** force `strict_pin=True`
  - `_resolve_auto_provider(...)` now does a second pass with `allow_degraded_fallback=True` if no selectable provider exists.
- Result:
  - Auto/runtime routing can land on degraded-but-routable fallback providers instead of blindly staying on dead Google.

### 3. Invoke-time failover now recognizes auth/provider-down failures
- Files:
  - `maritime-ai-service/app/engine/llm_failover_runtime.py`
  - `maritime-ai-service/app/engine/llm_pool.py`
- Changes:
  - Added `is_failover_eligible_error_impl(...)`
  - `ainvoke_with_failover_impl(...)` now fails over on:
    - timeout
    - rate-limit/quota
    - provider unavailable
    - auth/permission errors
    - host/transport/service-unavailable errors
- Result:
  - Cases like `401 invalid API key`, `permission denied`, `connection refused`, `service unavailable` now trigger cross-provider failover in auto mode.

## Tests Added / Updated
- `maritime-ai-service/tests/unit/test_llm_failover.py`
  - added invalid API key failover coverage
- `maritime-ai-service/tests/unit/test_agent_config.py`
  - added non-strict provider preference coverage
- `maritime-ai-service/tests/unit/test_supervisor_agent.py`
  - added house routing non-pin coverage
- `maritime-ai-service/tests/unit/test_structured_invoke_service.py`
  - updated native->JSON fallback regression to match current runtime policy

## Verification
Command:

```powershell
python -m pytest tests/unit/test_llm_failover.py tests/unit/test_agent_config.py tests/unit/test_supervisor_agent.py tests/unit/test_structured_invoke_service.py -q
```

Result:

```text
133 passed in 53.71s
```

## Current Truth
- This patch hardens the **runtime path** so that when Gemini fails at call time, Wiii has a much better chance of falling into another provider cleanly.
- Live quality still depends on:
  - fallback providers actually being configured (`zhipu/openrouter/ollama`)
  - runtime process picking up the right env vars
- If Google key is expired and no secondary provider is configured/selectable, Wiii will still degrade. This patch only stops the system from giving up **too early** when a viable fallback exists.
