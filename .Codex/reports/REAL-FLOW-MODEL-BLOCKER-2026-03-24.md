# Real Flow Test — Model/Runtime Blocker

Date: 2026-03-24
Workspace: `E:\Sach\Sua\AI_v1`
Tester: Codex

## Scope
- Test real local flow for Wiii backend/UI after LMS-side stabilization.
- Stop and report before patching if the blocker appears to be model/provider/runtime related.

## Environment
- Frontend: `http://127.0.0.1:1420`
- Backend: `http://127.0.0.1:8000`
- Container: `wiii-app`

## What passed
- Frontend loaded successfully and showed the Wiii login screen.
- `GET /api/v1/health` returned healthy.
- Simple sync chat succeeded when calling `POST /api/v1/chat` with:
  - valid API key
  - headers
  - request body including `user_id` and `role`

## What failed
### 1. Complex chart flow did not complete
Prompt:
- `Vẽ biểu đồ so sánh tốc độ các loại tàu container`

Observed behavior:
- First attempt ended with connection drop / backend unavailable briefly.
- Subsequent controlled attempt with body `user_id` + `role` timed out after `240s`.
- Backend remained healthy after timeout, so this was not a full process crash on the second run.

### 2. Model/provider path is unstable under structured-output load
Observed in container logs:
- Gemini hit `429 RESOURCE_EXHAUSTED`.
- Runtime then fell back into Zhipu/`glm-5`.
- Structured-output calls failed repeatedly:
  - `RoutingDecision` parse failure because model returned plain text instead of JSON
  - `_NarratedReasoningSchema` parse failure because model returned fenced JSON / markdown instead of strict JSON

Impact:
- Request spends too long in retry/fallback/parsing recovery loops.
- Visual/chart path becomes practically unusable in local real-flow testing.

### 3. Local backend reload noise complicates diagnosis
Observed in logs:
- `uvicorn --reload` performed a shutdown/start cycle during the failing period.
- This makes local symptoms noisier and can interrupt long-running requests.

## Secondary finding
- Raw `POST /api/v1/chat` without body fields `user_id` and `role` returned:
  - `400 validation_error`
  - missing `body.user_id`
  - missing `body.role`
- Headers alone were not sufficient on this path during testing.
- This is a separate API contract issue, not the main blocker for the chart failure.

## Current conclusion
- LMS integration is not the blocker in this real-flow test.
- The main blocker is the multi-model/runtime path:
  - quota pressure on Gemini
  - weak structured-output compliance on fallback model path
  - long retry/fallback loops
  - local reload noise

## Recommended next step
1. Hand off these findings to the Wiii model/runtime team first.
2. After they stabilize provider failover + structured-output handling, rerun:
   - simple direct chat
   - chart prompt
   - LMS sidebar/iframe flow
3. Separately clean the `/api/v1/chat` body-vs-header compatibility issue if desired.
