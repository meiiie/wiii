# Wiii Article Figure Phase 3

Date: 2026-03-15

## Goal

Close the remaining gap where explanatory responses still degraded into `markdown + boxed iframe` or single-figure output instead of a Claude-like article flow with multiple inline figures.

## What Changed

### Frontend

- Hardened the article composer in [InterleavedBlockSequence.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx):
  - supports `0 answer`, `1 answer`, or `multiple answer` blocks
  - synthesizes minimal bridge prose when the model returns visuals without prose
  - falls back to grouping contiguous editorial visuals even when backend group ids are missing
- Added coverage in [interleaved-block-sequence.test.tsx](E:/Sach/Sua/AI_v1/wiii-desktop/src/__tests__/interleaved-block-sequence.test.tsx) for:
  - grouped visuals without prose
  - multiple answer blocks merged into one article flow
  - fallback grouping when visuals arrive as separate singleton groups

### Backend

- Expanded structured auto-grouping in [visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/app/engine/tools/visual_tools.py):
  - `infographic` now auto-groups under explanatory/template runtime
  - this prevents the model from collapsing a full explanation into one large infographic card
- Added regression in [test_visual_tools.py](E:/Sach/Sua/AI_v1/maritime-ai-service/tests/unit/test_visual_tools.py) to verify explanatory infographics now return grouped figures.

### Acceptance

- Updated [visual-runtime.spec.ts](E:/Sach/Sua/AI_v1/wiii-desktop/playwright/visual-runtime.spec.ts) so explanatory visual tests expect:
  - editorial flow present
  - multi-figure behavior by default
  - lead/tail prose still visible in article mode

## Verification

- Backend: `46 passed`
- Frontend article composer unit: `17 passed`
- Web build: `npm run build:web` passed
- Playwright web acceptance: `2 passed`

## Outcome

- Explanatory requests are now much less likely to collapse into a single legacy-style visual.
- Even when the model returns imperfect grouping metadata, the frontend can still recover an article-style multi-figure flow.
- The remaining gap is now mostly art direction and figure quality, not orchestration failure.
