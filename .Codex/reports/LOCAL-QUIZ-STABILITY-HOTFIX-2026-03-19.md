# Local Quiz Stability Hotfix — 2026-03-19

## Scope

Addressed two local issues reported from real usage:

1. quiz/code-studio visual could end as `Khong the hien thi noi dung (visual)`
2. visible reasoning / action text could repeat the same sentence back-to-back, making Wiii look stuck

## Frontend Fixes

### 1. VisualBlock hook-order crash

Updated:

- `wiii-desktop/src/components/chat/VisualBlock.tsx`

Root cause:

- `VisualBlock` returned early when a visual was delegated into Code Studio
- that early return happened before later hooks
- once store state changed across renders, React could hit hook-order mismatch and the UI fell into `BlockErrorBoundary`

Fix:

- convert pre-hook return into `delegateToCodeStudioPanel` boolean
- keep hook order stable across renders
- only render the Code Studio placeholder after hooks have already run

### 2. Duplicate narrator/action lines

Updated:

- `wiii-desktop/src/stores/chat-store.ts`

Fixes:

- dedupe identical consecutive `setStreamingThinking(...)` lines
- dedupe identical consecutive `appendActionText(...)` blocks

This means if narrator fallback emits the same sentence twice in a row, the chat UI now keeps a single copy instead of making Wiii look stalled or confused.

## Tests Added / Updated

- `wiii-desktop/src/__tests__/structured-visuals.test.tsx`
  - add regression for app visual delegating into Code Studio without crashing
- `wiii-desktop/src/__tests__/chat-store.test.ts`
  - add narrator duplicate-thinking dedupe test
- `wiii-desktop/src/__tests__/action-text-timeline.test.ts`
  - add duplicate action-text dedupe test

## Verification

- `npm test -- --run src/__tests__/structured-visuals.test.tsx src/__tests__/code-studio-panel.test.tsx src/__tests__/tool-execution-strip.test.tsx`
  - `27 passed`
- `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/reasoning-interval.test.tsx`
  - `20 passed`
- `npm test -- --run src/__tests__/chat-store.test.ts src/__tests__/action-text-timeline.test.ts src/__tests__/streaming-blocks.test.ts`
  - `46 passed`
- `npm run build:web`
  - pass

## Backend Sanity

Current code-level routing sanity still confirms the plain quiz prompt should **not** fast-route into Code Studio anymore:

- query: `tạo cho mình quizz gồm 30 câu hỏi về tiếng Trung để mình luyện tập được không ?`
- `_conservative_fast_route(...)`
  - `('direct', 'learning', 0.9, 'obvious learning turn without app or domain signals')`

If local still shows the old Code Studio routing after these fixes, the running backend process is stale and should be restarted before retesting.
