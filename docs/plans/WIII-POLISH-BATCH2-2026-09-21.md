# WIII polish Batch 2 — 2026-09-21

Status: **Complete** · #978 + #979 merged on `main` @ `b873afa` · CLEAN-STOP → see WIII-POLISH-BATCH3-2026-09-21.md
Owner: soft+BIG polish (this agent) · Claims **released** with CLEAN-STOP
Base: `main` @ `#978` · Preview: `localhost:1420/?preview=neko-chill`
Voice: VI-first · ZCode-selective (calm density / disabled=explained / keyboard honesty — **no ZCode brand copy**)

## Claimed surfaces (Batch 2) — released

| Surface | Paths |
|---|---|
| Session composer IME + submitting parity | `NekoComposer.tsx` (+ calm-workbench / composer tests) — merged #978 |
| Hydrate / loading chrome | `NekoChillApp.tsx` `SessionRecoveryState` (+ shell UI test) — this PR #979 |
| Plan | this note · update `WIII-POLISH-PLAN-2026-09-21.md` status |

## Ranked this round (1–2 surgical PRs)

1. **Session composer parity vs ProjectHome** — IME Enter guard (`isComposing` / keyCode 229); submitting shows honest busy spinner (not mute Send without feedback). Keyboard footer / picker / Stop / keep-draft already landed in Batch1. → PR #978 merged
2. **Loading chrome** — hydrate recovery: skeleton chrome + busy label instead of blank center hang. → this PR #979
3. Theme/contrast — only if cheap leftover after 1–2 (skip full theme system).
4. Empty transcript/sidebar — only if still marketing/sparse after #977 (transcript empty already operational; defer unless lived).

## Out of scope

- Brand copy · backend/Tauri beyond existing helpers · Dependabot · broad CSS redesign

## Handoff

Lived retest after merge: IME/submitting + hydrate skeleton **PASS**. Remaining P2 items (empty transcript pad, filter-empty chrome, light ghost==text-3) parked under **WIII-POLISH-BATCH3 CLEAN-STOP** — not task-blocking vs ZCode.
