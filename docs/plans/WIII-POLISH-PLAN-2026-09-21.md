# WIII polish plan — 2026-09-21

Status: Batch 1 merged (#976/#977) · Batch 2 complete (#978/#979 @ `b873afa`) · Batch 3 **CLEAN-STOP** — see WIII-POLISH-BATCH3-2026-09-21.md
Lived soft P2 (2026-09-22): overview/catalog count honesty · Files empty without tool-legend stack · ProjectHome crumb dedupe — note `WIII-SOFT-P2-2026-09-22.md` (wiii-lab)
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

### P1 — Batch 2 (complete — #978 IME/submit · #979 hydrate skeleton)

7. ~~**Session composer parity**~~ → shipped #978 (IME Enter guard + submitting spinner). Residual toolbar density stays optional.
8. ~~**Loading chrome**~~ → shipped #979 (hydrate recovery skeleton + busy label; reduced-motion).
9. **Theme** — parked Batch3+ (light ghost==text-3 XS; no chill theme toggle unless product asks).
10. **Empty-state hierarchy** — parked Batch3+ (transcript `py-[10vh]` + filter chrome when 0 sessions) — P2, not task-blocking.
11. ~~Overview marketing hero~~ → shipped as follow-up PR after Batch1 (#976): calm dense operational header.
12. **Connections / tools / coworker honesty follow-ups** — only if new mute-disabled gaps appear after Batch 1.

## Out of scope this batch

- Brand copy from ZCode / other products
- Backend / Tauri command changes beyond existing `canChooseWorkspaceFolder`
- Dependabot / research PRs
- Broad CSS redesign

## Ship shape

- 1–2 PRs on `codex/…` branches from fresh `main`
- Tests for folder CTA, shortcuts rows, palette gate, title helpers
- Squash-merge when Gate Summary green
