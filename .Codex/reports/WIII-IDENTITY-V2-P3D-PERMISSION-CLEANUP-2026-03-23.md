# WIII IDENTITY V2 P3D — Permission + Legacy Role Cleanup

Date: 2026-03-23
Workspace: `E:\Sach\Sua\AI_v1`

## Summary

This loop finished the next high-risk cleanup after embed/chat canonicalization:

- removed role-gated self-service behavior that still assumed
  `student/teacher/admin` was the global truth
- moved Wiii org-permission resolution to the intended Identity V2 model:
  - `platform_role` decides platform-tier authority
  - `organization_role` adds org-local elevation
  - legacy LMS-style roles no longer shape Wiii web org permissions

## What changed

### 1. Chat history self-service no longer depends on legacy role strings

Updated:

- `maritime-ai-service/app/api/v1/chat_history_endpoint_support.py`
- `maritime-ai-service/app/api/v1/chat.py`
- `maritime-ai-service/tests/unit/test_sprint30_chat_api.py`

Behavior now:

- platform admin may delete any user history
- any authenticated user may delete their own history
- unknown/legacy role strings no longer block self-deletion

This matches the canonical identity model better: self-service ownership should
not depend on whether a compatibility role string looks like `student`.

### 2. Org permissions now use Wiii-native permission tiers

Updated:

- `maritime-ai-service/app/api/v1/organizations.py`
- `maritime-ai-service/app/core/org_settings.py`
- `maritime-ai-service/tests/unit/test_organization_api.py`
- `maritime-ai-service/tests/unit/test_sprint161_org_customization.py`
- `wiii-desktop/src/api/types.ts`

Behavior now:

- `permission_role = admin` only for true `platform_admin`
- all other Wiii-web users resolve to the normal user-tier base role
  (`student` compatibility tier)
- `org_role` still adds org-local elevation (`admin` / `owner`)
- response payload remains backward compatible via:
  - `role`
  - `org_role`
- and is now clearer via additive fields:
  - `permission_role`
  - `legacy_role`
  - `platform_role`

This removes another important identity leak: a legacy host-shaped role such as
`teacher` no longer changes Wiii web org governance semantics.

## Verification

### Backend targeted

```powershell
E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python.exe -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint30_chat_api.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_organization_api.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_chat_identity_projection.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_lms_endpoint_identity_v2.py `
  -q -p no:capture
```

Result:

- `93 passed`

### Backend regression around Identity V2 + org customization

```powershell
E:\Sach\Sua\AI_v1\maritime-ai-service\.venv\Scripts\python.exe -m pytest `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_identity_v2.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_user_router_identity_v2.py `
  E:\Sach\Sua\AI_v1\maritime-ai-service\tests\unit\test_sprint161_org_customization.py `
  -q -p no:capture
```

Result:

- `44 passed`

### Desktop

```powershell
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm exec vitest run src/__tests__/auth-user.test.ts src/__tests__/auth-identity-ssot.test.ts src/__tests__/org-store.test.ts src/__tests__/settings-page.test.ts
npm exec tsc -- --noEmit
```

Results:

- `118 passed`
- TypeScript compile passed

## Remaining accepted legacy-role usages

After a final grep pass, the remaining app-layer `auth.role` usages are now
acceptable and intentional:

1. **Host-local LMS routes**
   - `app/api/v1/lms_dashboard.py`
   - `app/api/v1/lms_data.py`
   These are allowed to reason from host-local overlay semantics.

2. **Compatibility payloads**
   - `app/auth/google_oauth.py`
   - `app/auth/user_router.py`
   These return `legacy_role` explicitly for compatibility.

3. **Logging only**
   - `app/api/v1/memories.py`

## State of the system now

- Wiii web identity is much closer to the intended production model.
- LMS is correctly behaving more like a connected workspace/plugin surface.
- Connected workspaces are already surfaced in Wiii web settings and no longer
  conceptually imply a separate Wiii identity.
- Wiii remains one living digital being; hosts contribute context and actions,
  not a new self.

## Remaining production gaps

1. Add end-to-end tests for:
   - Wiii web login
   - LMS token exchange
   - right-sidebar embed chat
   - return to Wiii web with the same canonical identity
2. Continue reducing raw compatibility assumptions in older docs/readmes.
3. Decide whether to keep `teacher` in org permission defaults forever as a
   compatibility tier or collapse it fully in a later schema cleanup.
