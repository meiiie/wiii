# Local Preview Backend URL Fix

Date: 2026-03-17
Owner: Codex
Status: Completed locally

## Problem

Local browser preview at `http://localhost:1420/` was showing:

- `Mất kết nối với máy chủ. Vui lòng kiểm tra kết nối mạng.`

even though:

- frontend was alive
- backend health at `http://localhost:8001/api/v1/health` was green

Root cause:

- local preview bootstrap still defaulted to `http://localhost:8000`
- frontend fallback client also still used `http://localhost:8000`
- persisted local preview settings with `http://localhost:8000` were not auto-migrated

So the app UI loaded, but chat/network calls still pointed at the wrong local port.

## Files changed

- `E:\Sach\Sua\AI_v1\wiii-desktop\src\lib\constants.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\stores\settings-store.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\auth\LoginScreen.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\settings\SettingsPage.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\settings\SettingsView.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\api\client.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\local-preview-bootstrap.test.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\settings-page.test.ts`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\auth-identity-ssot.test.ts`

## Fix

### 1. Local preview default now uses port 8001

- `DEFAULT_SERVER_URL` for local browser preview changed from `http://localhost:8000` to `http://localhost:8001`

### 2. Existing local preview settings are migrated automatically

- if a saved local browser config still has `http://localhost:8000`, it is rewritten to `http://localhost:8001`

### 3. Login and settings surfaces now point to the same local backend

- developer mode bootstrap
- local settings placeholder/preset
- client fallback path

## Verification

Commands run:

```bash
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm test -- --run src/__tests__/local-preview-bootstrap.test.ts src/__tests__/settings-page.test.ts src/__tests__/auth-identity-ssot.test.ts
npm run build:web
```

Results:

- `92 passed`
- `build:web` passed

## User note

To pick up the migration in the browser, the local preview page should be reloaded.

Recommended:

- hard refresh `http://localhost:1420/`
- if a tab is still stale, reopen it once

