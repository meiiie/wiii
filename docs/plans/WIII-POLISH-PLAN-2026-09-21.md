# WIII polish plan — 2026-09-21

Status: Active · Batch 1 shipping now · Batch 2 deferred  
Owner: soft+BIG polish (this agent) · Teammate may parallel-live elsewhere — **do not edit claimed paths**  
Base: `main` @ `#975` · Preview: `localhost:1420/?preview=neko-chill`  
Voice: VI-first · ZCode-selective (calm density / disabled=explained / keyboard honesty — **no ZCode brand copy**)

## Claimed surfaces (Batch 1) — other agents keep off

| Surface | Paths |
|---|---|
| Help / shortcuts Enter rows | `wiii-desktop/src/neko-chill/components/NekoMenuBar.tsx` (+ menu-bar tests) |
| Folder CTA honesty (preview) | `NekoComposer.tsx`, `ProjectDialog.tsx`, `workspace.ts` helpers if needed |
| Palette gated aria-disabled | `command-items.ts`, `NekoCommandCenter.tsx` |
| Cheap VI leftovers | `SessionInspector.tsx`, `ProjectHome.tsx` sr-only, `ProjectDialog` heading |
| Create / overview density | `NekoOverview.tsx` (light tighten only) |
| Bigger: keyboard footer + focus | `NekoComposer.tsx`, `NekoCommandCenter.tsx`, `ProjectHome.tsx`, `theme.css` if needed |
| Plan + tests | this note · matching `__tests__/neko-chill/*` |

## Ranked backlog

### P0 — Batch 1 soft pack (ship now)

1. **Help / shortcuts — Enter + Shift+Enter rows**  
   Phím tắt dialog lists chrome shortcuts but omits composer Enter (gửi) / Shift+Enter (xuống dòng). Mirror ChatInput honesty.

2. **Folder CTA — disable + title when `!canChooseWorkspaceFolder`**  
   Browser preview: composer “Chọn thư mục” and ProjectDialog add/empty folder CTAs still look actionable then no-op or alert. Prefer mute-disabled + local VI `title` (same cue as #972/#974).

3. **Palette `aria-disabled` where gated**  
   Command-center “Gắn dự án” action that would open the folder picker must expose `aria-disabled` + title in preview; skip execute.

4. **VI-ize leftover EN labels (cheap)**  
   `Workspace` sr-only / “Workspace / thư mục nguồn” / inspector “Agent” & “Model / profile” → VI where product voice is already VI.

5. **Create / overview density tighten (safe)**  
   Light vertical tighten on overview hero + stats — no layout rewrite.

### P0 — Batch 1 bigger polish (ship with or right after soft pack)

6. **Keyboard footer + focus consistency (composer ↔ palette)**  
   Session composer + ProjectHome get Enter/Shift+Enter hint; palette footer uses the same calm kbd chip language; keep `nk-input-field` / `nk-project-composer` focus-within rings aligned (no new brand chrome).

### P1 — Batch 2 (next round — leave for teammate / next pass)

7. **Session composer parity** — deeper alignment with ProjectHome / ZCode composer cues (toolbar density, locked-model affordance, insert/slash chrome).  
8. **Loading chrome** — discovery / hydrate / harness probe skeletons and busy labels consistency.  
9. **Theme** — dark/light token polish, focus contrast, reduced-motion pass beyond chill tokens.  
10. **Empty-state hierarchy** — transcript / sidebar / overview empty copy closer to ZCode calm density (if not absorbed in #6).  
11. **Connections / tools / coworker honesty follow-ups** — only if new mute-disabled gaps appear after Batch 1.

## Out of scope this batch

- Brand copy from ZCode / other products  
- Backend / Tauri command changes beyond existing `canChooseWorkspaceFolder`  
- Dependabot / research PRs  
- Broad CSS redesign

## Ship shape

- 1–2 PRs on `codex/…` branches from fresh `main`  
- Tests for folder CTA, shortcuts rows, palette gate, title helpers  
- Squash-merge when Gate Summary green  
