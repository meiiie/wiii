# Quiz Visual Render Hotfix — 2026-03-19

## Issue

Local quiz/code-studio runs could finish backend generation but still show:

- `Khong the hien thi noi dung (visual)`

The fallback came from the frontend `BlockErrorBoundary`, not from backend payload generation.

## Root Cause

`VisualBlock.tsx` had an `early return` for the "delegated to Code Studio panel" state **before** several `useEffect` hooks.

When an app visual rendered once and then the store switched into:

- `codeStudioPanelOpen=true`
- `activeSessionId === visual_session_id`

React could hit a hook-order mismatch during the next render and the boundary downgraded it to the generic visual error.

## Fix

Updated:

- `wiii-desktop/src/components/chat/VisualBlock.tsx`

Changes:

- replaced the pre-hook `early return` with a boolean `delegateToCodeStudioPanel`
- kept hook execution stable across renders
- moved the delegated Code Studio placeholder render to the final return phase

## Regression Coverage

Added test:

- `wiii-desktop/src/__tests__/structured-visuals.test.tsx`

New case:

- render an `app` visual first
- then toggle Code Studio session + panel open
- assert the visual swaps into the "Đang mở trong Code Studio" state without crashing

## Verification

- `npm test -- --run src/__tests__/structured-visuals.test.tsx src/__tests__/code-studio-panel.test.tsx src/__tests__/tool-execution-strip.test.tsx`
  - `27 passed`
- `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/reasoning-interval.test.tsx`
  - `20 passed`
- `npm run build:web`
  - pass

## Related Backend Sanity

Current code-level sanity check for the plain quiz prompt:

- query: `tạo cho mình quizz gồm 30 câu hỏi về tiếng Trung để mình luyện tập được không ?`
- `_conservative_fast_route(...)`
  - `('direct', 'learning', 0.9, 'obvious learning turn without app or domain signals')`

So if local still routes plain quiz into Code Studio, the running backend process is likely stale and should be restarted.
