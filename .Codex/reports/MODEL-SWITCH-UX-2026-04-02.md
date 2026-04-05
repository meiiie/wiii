# Model Switch UX - 2026-04-02

## Summary
- Added a user-facing model-switch suggestion path from backend failover/provider errors to desktop chat bubbles.
- Preserved Wiii's existing auto-failover, but now the user can:
  - retry the last turn with another provider for that turn only
  - keep a recommended provider for the rest of the session

## Backend
- Added prompt helpers:
  - `maritime-ai-service/app/services/model_switch_prompt_service.py`
- Sync error payload now includes `model_switch_prompt`:
  - `maritime-ai-service/app/api/v1/chat_endpoint_presenter.py`
- Stream error SSE payload now includes `model_switch_prompt`:
  - `maritime-ai-service/app/services/chat_stream_coordinator.py`
- Fallback metadata path now also includes `model_switch_prompt` for successful hard failover.

## Frontend
- Added structured `ApiHttpError` body preservation:
  - `wiii-desktop/src/api/client.ts`
- Added one-shot provider override in store:
  - `wiii-desktop/src/stores/model-store.ts`
- Added metadata-aware stream error persistence:
  - `wiii-desktop/src/stores/chat-store.ts`
- Added model-switch prompt resolver:
  - `wiii-desktop/src/lib/model-switch-prompt.ts`
- Added inline chat card:
  - `wiii-desktop/src/components/chat/ModelSwitchPromptCard.tsx`
- Wired card into assistant messages:
  - `wiii-desktop/src/components/chat/MessageBubble.tsx`
- Stream hook now:
  - consumes one-shot provider override
  - preserves structured error bodies from HTTP/SSE failures
  - stores them on assistant error messages
  - file: `wiii-desktop/src/hooks/useSSEStream.ts`

## Tests
### Backend
- `9 passed`
- Command:
  - `python -m pytest tests/unit/test_model_switch_prompt_service.py tests/unit/test_chat_endpoint_presenter.py tests/unit/test_chat_stream_coordinator.py -q -p no:capture`

### Frontend
- `38 passed`
- Command:
  - `npx vitest run src/__tests__/model-store.test.ts src/__tests__/model-switch-prompt-card.test.tsx src/__tests__/chat-store.test.ts src/__tests__/message-bubble-fast-path.test.tsx`
- Additional nearby suites:
  - `31 passed`
  - `npx vitest run src/__tests__/model-selector.test.tsx src/__tests__/sprint153b-desktop-hardening.test.ts src/__tests__/use-sse-stream-concurrency.test.ts`

## Current Truth
- The UX is now in place for both:
  - pre-SSE HTTP provider failures
  - SSE error events
  - successful failover cases with `failover` metadata
- Missing-thinking issues remain lane-specific and separate from this change.
- If Gemini is unavailable and GLM/OpenRouter/Ollama are selectable, Wiii can now both auto-failover and invite the user to lock in a different provider cleanly.
