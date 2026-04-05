# LMS Local Wiii Sidebar Audit — 2026-03-25

## Verdict

Local LMS ↔ Wiii sidebar is now working again on `localhost`.

What was broken was **not** the Wiii embed build itself. The main failures were in the LMS local integration layer:

1. LMS backend token exchange was calling Wiii through the wrong hostname for the current Docker topology.
2. Student layout had the assistant entrypoint hard-disabled.
3. LMS frontend production bundle inside Docker was still pointing to the production Wiii embed URL.
4. LMS frontend CSP did not allow `http://localhost:8000` as an iframe source.

## Fixes Applied

### Local runtime config

- Updated local-only LMS `.env` to call Wiii through `host.docker.internal:8000` for:
  - `AI_SERVICE_URL`
  - `WIII_WEBHOOK_URL`
  - `WIII_TOKEN_EXCHANGE_URL`

This matches the current localhost setup where LMS and Wiii are on separate Docker networks.

### Student sidebar

- Enabled the assistant surface for students in:
  - `E:/Sach/Sua/LMS_hohulili/fe/src/app/features/student/shared/student-layout-simple.component.ts`

### Local-safe frontend Wiii URL resolution

- Updated:
  - `E:/Sach/Sua/LMS_hohulili/fe/src/environments/environment.prod.ts`

So Docker production builds still use production URLs on real production hosts, but automatically switch to:

- `http://localhost:8000/embed`
- `http://localhost:1420`

when the app is being served on `localhost` or `127.0.0.1`.

### CSP

- Updated:
  - `E:/Sach/Sua/LMS_hohulili/fe/nginx.conf`

to allow `http://localhost:8000` and `http://127.0.0.1:8000` as local iframe/connect targets.

## What I Rebuilt

Used the **dev override** compose topology, because the base compose file does not publish host ports:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build backend frontend
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build frontend
```

## Verification

### Host surfaces

- `http://localhost:4200` → `200`
- `http://localhost:8088/actuator/health` → `200`
- `http://localhost:8000/embed` → `200`

### Teacher flow

- login: `teacher@maritime.edu / teacher123`
- sidebar toggle present
- `POST /api/v3/ai/token` returns success
- iframe loads with `http://localhost:8000/embed#...`
- no LMS CSP error remains

Screenshot:
- `E:/Sach/Sua/AI_v1/.Codex/reports/lms-teacher-sidebar-after-fix-2026-03-25.png`

### Student flow

- login: `student@maritime.edu / student123`
- sidebar toggle present
- `POST /api/v3/ai/token` returns success
- iframe loads with `http://localhost:8000/embed#...`
- no LMS CSP error remains

Screenshot:
- `E:/Sach/Sua/AI_v1/.Codex/reports/lms-student-sidebar-after-fix-2026-03-25.png`

### Minimal embed-runtime sanity check

Inside the teacher iframe, `Chào Wiii` could be submitted and Wiii started responding.

That means:

- embed auth works
- iframe loads
- sidebar host integration works
- Wiii local runtime is reachable from LMS

## Important Notes

- The initial “Không thể kết nối với Wiii” problem on localhost was an LMS-side integration problem, not proof that Wiii embed needed a special rebuild.
- Rebuilding LMS frontend **was** necessary after the fixes because:
  - student sidebar entrypoint changed
  - production bundle URL resolution changed
  - nginx CSP changed
- Wiii backend/embed itself did **not** need code rebuild for this specific LMS-local connectivity fix.

## Remaining Risk

- The separate Wiii model/runtime team is still changing provider behavior. Basic embed/runtime is alive, but deeper answer quality/latency issues may still come from the model layer, not from LMS embedding.
