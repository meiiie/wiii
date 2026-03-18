# Local Inline Figure Polish

Date: 2026-03-17
Owner: Codex
Status: Completed locally, verified

## Goal

Reduce the remaining "widget card" feeling in Wiii's article figures and reasoning rhythm without touching routing, stream behavior, or renderer logic.

Reference used:

- Claude inline figure screenshot: `C:\Users\Admin\Downloads\HDhmlbFaoAA_Z60.jpg`
- Wiii article/figure plans:
  - `E:\Sach\Sua\AI_v1\.Codex\reports\WIII-ARTICLE-FIGURE-MASTERPLAN-V5-2026-03-15.md`
  - `E:\Sach\Sua\AI_v1\.Codex\reports\CLAUDE-KIMI-HTML-UX-ANALYSIS-2026-03-15.md`

## What changed

### 1. Article figure shell was thinned

File:

- `E:\Sach\Sua\AI_v1\wiii-desktop\src\styles\globals.css`

Changes:

- softened outer border on `.visual-block-shell--article`
- reduced radial wash and shadow depth
- added lighter translucent backdrop feel instead of a boxed card feel
- tightened figure stage spacing so prose and figure read as one editorial unit

### 2. Embedded summary text became more editorial

Files:

- `E:\Sach\Sua\AI_v1\wiii-desktop\src\components\chat\VisualBlock.tsx`
- `E:\Sach\Sua\AI_v1\wiii-desktop\src\styles\globals.css`

Changes:

- removed the heavy inline utility styling from the embedded summary paragraph
- dropped the `Y chinh` chrome label from `visual-block-shell__lede`
- restyled summary/claim text as serif prose with lighter contrast

### 3. Balanced thinking header was thinned slightly

File:

- `E:\Sach\Sua\AI_v1\wiii-desktop\src\styles\globals.css`

Changes:

- reduced padding
- softened header text contrast
- kept the same collapsible behavior and streaming logic

### 4. Code Studio card was brought closer to the Wiii surface language

File:

- `E:\Sach\Sua\AI_v1\wiii-desktop\src\styles\globals.css`

Changes:

- lighter border
- more transparent background mix
- reduced hover shadow
- closer to an inline surface than a standalone utility widget

## Verification

Frontend tests:

```bash
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm test -- --run src/__tests__/structured-visuals.test.tsx src/__tests__/interleaved-block-sequence.test.tsx src/__tests__/reasoning-interval.test.tsx
```

Result:

- `34 passed`

Build:

```bash
cd E:\Sach\Sua\AI_v1\wiii-desktop
npm run build:web
```

Result:

- pass

## Outcome

This phase does not change routing or lane selection.

It only improves the feel of:

- article figures
- embedded lede/claim text
- balanced thinking header rhythm
- Code Studio inline card chrome

The result is closer to:

- inline
- translucent
- editorial
- absorbed into the page background

and less like:

- nested widget cards
- thick framed mini apps
- over-signposted UI blocks

