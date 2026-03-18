# Wiii Code Studio + Visual Runtime Phase 5

**Date:** 2026-03-16  
**Owner:** Codex  
**Status:** Completed, verified locally

## Scope

Phase này khóa nốt phần frontend của plan professionalization:

- giữ `LLM-first planning, host-governed runtime`
- restore lại `template/article_figure` lane cho structured visuals
- tránh regression do mọi visual bị ép qua iframe lane
- xác minh metadata/routing backend vẫn khớp với renderer frontend

## What Changed

### 1. Restored native structured renderer path

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\VisualBlock.tsx`

Changes:
- kích hoạt lại structured renderer cho `renderer_kind === "template"`
- đổi các helper chết thành runtime thật:
  - `renderStructured`
  - `ControlBar`
  - `Details`
  - `getFormulaChips`
- template visuals giờ render trong `visual-block-shell` article shell thay vì fail vì thiếu `html`
- `app` lane tiếp tục dùng `EmbeddedAppFrame`
- `inline_html` lane tiếp tục dùng `InlineVisualFrame`
- chỉ `html/app` lanes mới hiện `VisualActionBar`

### 2. Recovered article shell for template figures

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\VisualBlock.tsx`

Changes:
- root figure dùng:
  - `visual-block-shell`
  - `visual-block-shell--article`
  - `visual-block-shell--embedded` khi cần
- header shell giờ có:
  - pedagogical role pill
  - formula chips
  - title
  - embedded lede / claim prose
- structured visuals dùng control bar + stage canvas + details block đúng article-first layout

### 3. Fixed structured visual regression tests

File:
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\__tests__\structured-visuals.test.tsx`

Changes:
- cập nhật các assertion tiếng Việt theo text render thực tế
- dọn expectation cũ bị mojibake/ASCII drift
- suite giờ cover đúng:
  - comparison
  - process
  - architecture
  - concept
  - chart
  - timeline
  - map-lite
  - annotation focus
  - app frame
  - iframe bridge control

## Verification

### Frontend

Ran:

```bash
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm test -- --run src/__tests__/structured-visuals.test.tsx
npm test -- --run src/__tests__/interleaved-block-sequence.test.tsx
npm test -- --run src/__tests__/code-studio-store.test.ts
npm test -- --run src/__tests__/inline-html-widget.test.tsx
npm run build:web
```

Results:

- `structured-visuals.test.tsx` -> `16 passed`
- `interleaved-block-sequence.test.tsx` -> `17 passed`
- `code-studio-store.test.ts` -> `12 passed`
- `inline-html-widget.test.tsx` -> `8 passed`
- `npm run build:web` -> pass

### Backend

Ran:

```bash
python -m pytest maritime-ai-service/tests/unit/test_visual_intent_resolver.py -q
python -m pytest maritime-ai-service/tests/unit/test_visual_tools.py -q
```

Results:

- `test_visual_intent_resolver.py` -> `14 passed`
- `test_visual_tools.py` -> `73 passed`

## Outcome

Current state:

- `article_figure` / template lane works again
- structured visuals no longer fall through to missing-html failure
- `app` and `inline_html` lanes remain intact
- Code Studio metadata work from previous phase still holds
- backend routing/validation remains green

## Remaining Non-Blocking Follow-Ups

- polish article shell typography / art direction further
- expand chart runtime recipe library so more numeric chart cases avoid bespoke codegen
- add critic/fallback loop for Code Studio before preview publish
- unify search/code widget feedback contract under `WidgetResultV1`
