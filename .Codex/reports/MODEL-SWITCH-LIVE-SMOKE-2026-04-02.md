# Model Switch Live Smoke - 2026-04-02

## Setup
- Transport: ASGI in-process probe
- Current reality:
  - Gemini not healthy / quota-auth unstable
  - Zhipu GLM available

## Results
### 1. Explicit `provider=google` on `/api/v1/chat/stream/v3`
- Status: `200`
- Stream sequence:
  - `status`
  - `error`
  - `done`
- Error payload includes:
  - `provider=google`
  - `reason_code=busy`
  - `model_switch_prompt`
- Prompt content correctly suggests:
  - retry this turn with `Zhipu GLM`
  - keep `Zhipu GLM` for future turns

### 2. Explicit `provider=google` on `/api/v1/chat`
- Status: `200`
- Result did **not** surface `model_switch_prompt`
- It fell into a generic direct fallback answer
- Metadata still reported `provider=google`

### 3. `provider=auto` on `/api/v1/chat`
- Status: `200`
- Runtime landed on `provider=zhipu`, `model=glm-5`
- Response quality was acceptable
- Metadata contained failover route information
- `model_switch_prompt` was still `null` in that sync probe

## Current Truth
- The new UX path is working correctly for the **primary stream path**, which is what users actually use in chat.
- There is still a **sync-lane residual issue**:
  - explicit provider failure does not yet consistently become a clean model-switch prompt
  - instead it can collapse into a generic fallback answer

## Recommendation
- Keep the current stream UX as the main user-facing solution.
- If we want parity later, the next follow-up would be:
  - trace the sync explicit-provider path after stale selectability is ignored
  - ensure hard provider failure becomes either:
    - structured `ProviderUnavailableError`, or
    - successful failover metadata with a sync-side `model_switch_prompt`
