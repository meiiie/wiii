# Wiii Pointy — LMS integration guide

> **Status:** V1 (read-only tutor mode)
> **Last updated:** 2026-04-29
> **Owner:** Wiii Lab
> **Audience:** LMS frontend team (`holilihu.online` Angular app)
> **Companion docs:** `docs/integration/LMS_TEAM_GUIDE.md` (Section 9, Page-Aware AI Context)

Wiii Pointy is the cooperative-iframe overlay that lets Wiii — the AI living
inside the LMS iframe — *point at* UI elements, scroll to them, navigate the
LMS router, and run multi-step guided tours. It is the web-native answer to
the "macOS clicky" UX, built on top of the Sprint 222 `HostActionBridge`
(PostMessage 2-way protocol) Wiii already speaks.

V1 is intentionally **read-only**: no auto-click, no auto-fill, no DOM
mutation. The student stays in control. Auto-click + auto-fill are gated for
V2 behind explicit per-tool `mutates_state=true` + `requires_confirmation=true`.

---

## 1. What you ship as the LMS team

Two small things in the LMS Angular app:

1. **Include the Pointy bundle** on every page where the Wiii iframe is
   embedded:

   ```html
   <script src="https://wiii.holilihu.online/pointy/wiii-pointy.umd.js"></script>
   ```

   (Or import the ESM build from `dist-pointy/wiii-pointy.es.js` if you
   prefer a bundled path.)

2. **Initialise the bridge once**, then forward capabilities to the iframe:

   ```ts
   import { Router } from '@angular/router';

   declare global {
     interface Window { WiiiPointy: any; }
   }

   const wiiiOrigin = 'https://wiii.holilihu.online';

   const handle = window.WiiiPointy.init({
     iframeOrigin: wiiiOrigin,
     onNavigate: (route: string) => router.navigateByUrl(route),
   });

   const iframeEl = document.getElementById('wiii-iframe') as HTMLIFrameElement;
   iframeEl.addEventListener('load', () => {
     iframeEl.contentWindow?.postMessage(handle.capabilities(), wiiiOrigin);
   });
   ```

That is the entire integration. The bridge listens for `wiii:action-request`
messages from the iframe and replies with `wiii:action-response`. Wiii's
backend (`HostActionBridge`, Sprint 222) and the iframe frontend (Sprint
222b) already speak this protocol.

---

## 2. Action contract (V1)

| Action | Mutates? | Confirm? | Purpose |
|---|---|---|---|
| `ui.highlight` | no | no | Spotlight + tooltip on a target element |
| `ui.scroll_to` | no | no | `scrollIntoView({block:'center'})` on a target |
| `ui.navigate` | no | no | Internal route or safe absolute URL |
| `ui.show_tour` | no | no | 2–5 step guided walk-through |

### `ui.highlight`
```jsonc
{
  "selector": "[data-wiii-id=\"continue-lesson\"]",
  "message": "Đây là nút để tiếp tục bài học.",
  "duration_ms": 2200
}
```
Reply: `{ success: true, data: { summary: "Đã trỏ vào element: #continue-lesson" } }`

### `ui.scroll_to`
```jsonc
{ "selector": "[data-wiii-id=\"profile-card\"]", "block": "center" }
```

### `ui.navigate`
```jsonc
{ "route": "/courses/123/lessons/4" }
```
or
```jsonc
{ "url": "https://holilihu.online/help" }
```
Internal `route` is preferred — `onNavigate` lets you keep Angular Router
state. Absolute `url` is rejected when it points at `localhost`,
`127.0.0.1`, `*.local`, or any non-`http(s)` scheme.

### `ui.show_tour`
```jsonc
{
  "steps": [
    { "selector": "[data-wiii-id=\"course-card\"]",
      "message": "Bước 1 — khóa học hôm nay.", "duration_ms": 1600 },
    { "selector": "[data-wiii-id=\"quiz-card\"]",
      "message": "Bước 2 — bài kiểm tra sắp tới.", "duration_ms": 1600 }
  ],
  "start_at": 0
}
```
A new tour cancels any tour already running.

---

## 3. Selectors — make Pointy reliable

Wiii relies on selectors you provide. Make them stable:

- **Strongly prefer** `data-wiii-id` attributes on every interactive element
  the student is likely to be guided toward. Example:
  `<button data-wiii-id="submit-quiz">Nộp bài</button>`. These survive
  refactors and CSS class churn.
- Fall back to `id` only when uniqueness is guaranteed.
- Avoid relying on raw class names or nth-child paths.

The Wiii backend reads `HostContext.content.structured` (Sprint 222b) — when
you populate it with the visible interactive elements (`{role, name,
data-wiii-id}`), the AI can ground its highlight calls without guessing.

### Quiz pages — pedagogical guardrail

The Pointy skill (`maritime-ai-service/app/engine/context/skills/lms/pointy.skill.yaml`)
explicitly forbids the AI from using `ui.highlight` on quiz answer options.
The AI is allowed to point at navigation / submit / hint controls. If your
quiz template marks answer options with a different `data-wiii-id` namespace
(e.g. `quiz-option-A`), keep them recognisable so future safety checks can
filter them server-side too.

---

## 4. Security model

- **Origin pinning.** The bridge ignores any message whose `event.origin`
  is not the configured `iframeOrigin`. Replies are sent with the same
  fixed `targetOrigin` — never `*`.
- **Selector hardening.** Bad selectors fail closed (`selector_not_found`)
  rather than throwing.
- **URL hardening.** `ui.navigate` rejects loopback / `.local` / `.internal`
  / non-`http(s)` URLs — covers the same SSRF list as the standalone
  Playwright agent (Sprint 222b Phase 7).
- **Content Security Policy.** The bundle is plain JS + DOM. No `eval`, no
  inline workers, no fetch. CSP `script-src 'self' https://wiii.holilihu.online`
  is sufficient; `style-src 'self' 'unsafe-inline'` is required only for the
  inline overlay styles — switch to `'nonce-...'` if your CSP is strict.

---

## 5. Operational notes

- **Bundle size.** ~11 KB minified UMD, ~4.5 KB gzipped. Safe to ship on
  every page.
- **Idempotency.** Calling `WiiiPointy.init(...)` twice replaces the
  previous bridge — useful during HMR.
- **Cleanup.** Call the returned `handle.destroy()` on route teardown if
  your single-page Angular app unmounts the Wiii iframe.
- **Observability.** Pass a `log: (level, msg, ctx) => ...` callback into
  `init` to forward bridge events to your existing telemetry.
- **Coexistence with Page-Aware Context (Sprint 221).** Wiii Pointy and
  Page-Aware Context are independent and additive. Pointy reads selectors
  from the page; Page-Aware Context tells the AI *what page is open*.
  Together they form the full host loop: AI sees page → AI calls action →
  Pointy executes.

---

## 6. Build & ship

```bash
cd wiii-desktop
npm run build:pointy     # → dist-pointy/wiii-pointy.umd.js + .es.js
```

Copy the `dist-pointy/wiii-pointy.umd.js` artifact behind a CDN path
(`https://wiii.holilihu.online/pointy/wiii-pointy.umd.js`). The artifact is
hash-stable per build.

Demo for visual QA: open
`wiii-desktop/dev-demo/pointy/index.html` in a browser after the build.

---

## 7. Roadmap

- **V1 (this PR):** read-only tutor primitives.
- **V2:** `ui.click`, `ui.fill_field` — gated `mutates_state=true,
  requires_confirmation=true`. Quiz pages remain read-only.
- **V3:** push-to-talk voice + Agent Mode dashboard panel (re-uses
  existing `OperatorSessionV1` from `host_context.py`).
- **Long-term:** migrate the capability declaration to WebMCP once the
  W3C draft stabilises. The current `HostCapabilities.tools[]` shape
  maps 1:1 onto MCP tools, so this is a rename, not a rewrite.
