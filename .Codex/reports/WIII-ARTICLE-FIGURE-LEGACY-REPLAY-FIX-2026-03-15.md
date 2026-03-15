# Wiii Article-Figure Legacy Replay Fix

Date: 2026-03-15

## Problem

Export HTML cua Wiii van cho thay explanatory turns roi vao lane `answer markdown + iframe`, du article/figure runtime moi da co san.

Root cause chinh:

- `InterleavedBlockSequence` da biet tach `legacy-widget` segments, nhung `renderEditorialFlow()` lai render `legacy-widget` o mot vong lap rieng sau khi render prose/figure.
- `buildArticleComposition()` strip ` ```widget ` qua som, nen conversation cu co widget fences khong duoc nhan dien de nang cap thanh editorial flow.

## Fix

### Frontend

Files:

- `wiii-desktop/src/components/chat/InterleavedBlockSequence.tsx`
- `wiii-desktop/src/__tests__/interleaved-block-sequence.test.tsx`

Changes:

- Gop `prose`, `figure`, va `legacy-widget` vao mot render pass duy nhat trong `renderEditorialFlow()`.
- Dung `collectRawAnswers()` cho legacy replay branch de khong strip widget fences truoc khi composer kip phan tach.
- Them regression test cho case conversation cu:
  - 1 answer
  - prose + 2 widget fences
  - ky vong render thanh `editorial-visual-flow` voi 2 figures inline

### Test harness

- Mock `InlineHtmlWidget` trong unit test de test on dinh va tap trung vao orchestration.

## Verification

- `npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx`
  - Result: `18 passed`
- `npm run test:e2e:visual`
  - Result: `2 passed`
- `npm run build:web`
  - Result: pass

## Outcome

Lane replay cho conversation cu da duoc nang cap:

- Khong con append widget ve cuoi flow sai thu tu
- Khong con strip widget qua som khien composer bo lo figure
- Explanatory widget cu gio co the duoc render nhu article figures, thay vi nam trong `answer-block`

## Remaining

- Can export HTML moi sau local test de xac nhan DOM cuoi cung da hien `editorial-visual-flow` thay vi `answer-block > iframe`.
- App/simulation lane van con du dia polish ve art direction, nhung bug replay lane da duoc khoa.
