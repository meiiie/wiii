# Local Google OAuth Redirect Fix — 2026-03-17

## Problem

Local browser preview at `http://localhost:1420` started failing Google login with:

- `400: redirect_uri_mismatch`

At the same time, chat/local preview had previously been redirected toward backend port `8001`.

## Root Cause

The local browser contract had drifted:

- frontend/browser preview defaults were migrated to `http://localhost:8001`
- backend OAuth callback URI is derived from the backend request base URL in [`google_oauth.py`](E:/Sach/Sua/AI_v1/maritime-ai-service/app/auth/google_oauth.py)

That meant local Google login was generating a callback like:

- `http://localhost:8001/api/v1/auth/google/callback`

but the Google OAuth app local setup is aligned to the long-standing local contract on port `8000`.

## Fix

Restored the local browser contract to:

- frontend: `http://localhost:1420`
- backend: `http://localhost:8000`

Updated frontend defaults and migrations so stale local settings are normalized back to `localhost:8000`.

## Files Changed

- [`constants.ts`](E:/Sach/Sua/AI_v1/wiii-desktop/src/lib/constants.ts)
- [`settings-store.ts`](E:/Sach/Sua/AI_v1/wiii-desktop/src/stores/settings-store.ts)
- [`client.ts`](E:/Sach/Sua/AI_v1/wiii-desktop/src/api/client.ts)
- [`LoginScreen.tsx`](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/auth/LoginScreen.tsx)
- [`SettingsPage.tsx`](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/settings/SettingsPage.tsx)
- [`SettingsView.tsx`](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/settings/SettingsView.tsx)
- [`local-preview-bootstrap.test.ts`](E:/Sach/Sua/AI_v1/wiii-desktop/src/__tests__/local-preview-bootstrap.test.ts)
- [`settings-page.test.ts`](E:/Sach/Sua/AI_v1/wiii-desktop/src/__tests__/settings-page.test.ts)
- [`auth-identity-ssot.test.ts`](E:/Sach/Sua/AI_v1/wiii-desktop/src/__tests__/auth-identity-ssot.test.ts)

## Verification

### Frontend tests

- `npm test -- --run src/__tests__/local-preview-bootstrap.test.ts src/__tests__/settings-page.test.ts src/__tests__/auth-identity-ssot.test.ts`
- Result: `93 passed`

### Frontend build

- `npm run build:web`
- Result: pass

### Backend local health

- `http://127.0.0.1:8000/api/v1/health`
- Result: `{"status":"ok","service":"Wiii","version":"0.1.0","environment":"development"}`

### OAuth redirect verification

Request:

- `http://localhost:8000/api/v1/auth/google/login?redirect_uri=http://localhost:1420`

Observed Google authorize URL contains:

- `redirect_uri=http://localhost:8000/api/v1/auth/google/callback`

This confirms local Google OAuth is back on the correct callback base URL.

## Notes

- Host-level `127.0.0.1:8000` and `localhost:8000` both work for local health checks, but browser testing should use `localhost` to match OAuth and allowed redirect origins cleanly.
- Any stale browser settings from the temporary `8001` migration should normalize back to `localhost:8000` after reload.
