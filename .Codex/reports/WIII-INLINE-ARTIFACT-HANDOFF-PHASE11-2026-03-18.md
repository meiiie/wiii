# Wiii Inline Artifact Handoff — Phase 11 — 2026-03-18

## Goal
- Add a Claude-style artifact promotion affordance to inline visuals without turning the visual itself into a persistent artifact.
- Reuse the normal chat send path instead of inventing a second stream pipeline.

## What changed
- `VisualBlock` now accepts `onSuggestedQuestion`.
- `InterleavedBlockSequence`, `MessageBubble`, and `MessageList` pass that callback all the way down from the normal chat flow.
- Inline visuals can now render a very light action chip:
  - `Mo thanh Artifact`
- Clicking that chip sends `artifact_handoff_prompt` as a new user turn.
- No in-place conversion happens.
- Existing HTML actions remain:
  - `Tai HTML`
  - `Sao chep`
- Code Studio shortcut remains when a Code Studio session already exists.

## UX rules
- The action bar stays subtle and low-chrome.
- Artifact handoff is only shown when:
  - `artifact_handoff_available=true`
  - `artifact_handoff_mode=followup_prompt`
  - `artifact_handoff_prompt` is present
  - the normal send callback exists
- True artifact lane payloads do not show this handoff.
- The handoff button is disabled while a stream is active.

## Why this matches the design
- Inline visual stays inline and ephemeral.
- Artifact creation is modeled as intent escalation on the next turn.
- The user experiences it as “Wiii, make this into a real artifact now”, not as a silent renderer swap.

## Verification
- `npm test -- --run src/__tests__/structured-visuals.test.tsx` -> `18 passed`
- `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx` -> `19 passed`
- `npm run build:web` -> pass

## Next recommended step
- Add one very small e2e smoke test for:
  - click `Mo thanh Artifact`
  - verify a new user turn is sent
  - verify the next response can open the artifact lane
