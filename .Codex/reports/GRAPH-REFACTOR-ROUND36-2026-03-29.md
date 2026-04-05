# Graph Refactor Round 36 — Security Module Decomposition

Date: 2026-03-29

## Summary

This round refactored `app.core.security` by separating:
- pure role/authority mapping logic
- auth data contracts

The request dependency flow stayed in `security.py` so the existing patch points
used by auth tests remain stable.

## Changes

### 1. Extract role normalization + authority helpers

Added:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\security_roles.py`

Moved into this module:
- `DEFAULT_LEGACY_ROLE`
- `DEFAULT_PLATFORM_ROLE`
- `PLATFORM_ADMIN_ROLE`
- `normalize_role_source`
- `normalize_platform_role`
- `normalize_host_role`
- `normalize_legacy_role`
- `map_host_role_to_legacy_role`
- `resolve_interaction_role`
- `derive_platform_role_from_legacy_role`
- `is_platform_admin`

These functions are pure and were a clean seam for extraction.

### 2. Extract auth data contracts

Added:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\security_models.py`

Moved into this module:
- `TokenPayload`
- `AuthenticatedUser`

This leaves request dependency code in `security.py` focused on:
- secret verification
- org membership checks
- `require_auth`
- `optional_auth`

### 3. Keep compatibility through the public module

Modified:
- `E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\security.py`

`security.py` now imports/re-exports the same public names while still owning
the mutable/test-patched auth flow functions:
- `verify_jwt_token`
- `verify_api_key`
- `verify_lms_service_token`
- `_validate_org_membership`
- `require_auth`
- `optional_auth`

This was intentional to avoid breaking tests that patch:
- `app.core.security.settings`
- `app.core.security.verify_api_key`
- `app.core.security._validate_org_membership`

## Line Count Impact

- `app/core/security.py`: `615 -> 450`
- `app/core/security_roles.py`: `142`
- `app/core/security_models.py`: `45`

Net effect:
- `security.py` is no longer mixing pure role semantics with dependency logic
- role rules now have a single dedicated home
- auth data contracts are isolated from request handling

## Validation

### Compile

Passed:

```powershell
python -m py_compile `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\security.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\security_roles.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\app\core\security_models.py
```

### Focused tests

Passed:

```powershell
python -m pytest tests/unit/test_security_timing.py tests/unit/test_identity_v2.py tests/unit/test_auth_ownership.py -v -p no:capture --tb=short
```

Result:
- `24 passed`

Passed:

```powershell
python -m pytest tests/unit/test_sprint192_auth_hardening.py -v -p no:capture --tb=short -k "verify_jwt_token or verify_api_key or require_auth or optional_auth or AuthenticatedUser or _validate_org_membership"
```

Result:
- `4 passed`
- `44 deselected`

Passed:

```powershell
python -m pytest tests/unit/test_runtime_endpoint_smoke.py -v -p no:capture --tb=short
```

Result:
- `7 passed`

Notes:
- warnings about short JWT HMAC test keys are from existing test fixtures
- no regression linked to this extraction was observed

## Sentrux

Command:

```powershell
E:\Sach\Sua\AI_v1\tools\sentrux.exe gate E:\Sach\Sua\AI_v1\maritime-ai-service\app
```

Result:
- `Quality: 4501`
- `Coupling: 0.30`
- `Cycles: 7`
- `God files: 0`
- `No degradation detected`

## Why This Round Matters

Before this round, `security.py` owned:
- platform/legacy/host role semantics
- Pydantic auth payload models
- secret validation
- org membership checks
- auth dependencies

That made even small auth changes reopen a file that mixed policy, models, and
request wiring.

After this round:
- role policy lives in one place
- auth payload contracts live in one place
- the dependency shell is smaller and easier to reason about
- future refactors can target auth flow separately from role semantics

## Recommended Next Cuts

High-ROI follow-ups:
1. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\api\v1\course_generation_runtime.py`
2. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\engine\semantic_memory\temporal_graph.py`
3. `E:\Sach\Sua\AI_v1\maritime-ai-service\app\services\chat_orchestrator.py`

Rationale:
- all three are below god-file threshold now
- but they still own multiple concerns and are good clean-architecture seams
