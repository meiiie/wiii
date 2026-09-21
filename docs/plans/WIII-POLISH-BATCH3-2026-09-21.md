# WIII polish Batch 3 — CLEAN-STOP — 2026-09-21

Status: **CLEAN-STOP** · no Batch 3 PR this round
Owner: soft+BIG polish (this agent) · Teammate (WIII verify) free for other surfaces
Base: `main` @ `b873afa` (#978 + #979 merged)
Preview: `localhost:1420/?preview=neko-chill`
Voice: VI-first · ZCode-selective (calm density / disabled=explained / keyboard honesty — **no ZCode brand copy**)

## Lived retest after #978+#979 (main `b873afa`)

| Surface | Result | Evidence |
|---|---|---|
| Session composer IME Enter guard (`isComposing` / keyCode 229) | **PASS** | `/tmp/wiii-retest-b873afa-ime/` · overall PASS |
| Submitting busy spinner (`Đang gửi…` / `aria-busy`) | **PASS** | same · `submittingSpinnerParity` PASS |
| Hydrate recovery skeleton chrome + busy label | **PASS** | `/tmp/wiii-retest-b873afa-hydrate/` · skeleton + `Đang khôi phục lịch sử phiên…` |
| Hydrate error path shows + retry copy | **PASS** (probe regex soft-miss) | Error card + button **Thử tải lại** present; probe looked for contiguous `thử lại` |

Blockers: none.

## Why no Batch 3 PR

Batch 2 shipped the only items that were operator-facing vs ZCode (IME/submit honesty + hydrate hang chrome). Remaining candidates from Batch2 ranking are **P2 polish**, not clearly task-blocking:

| Candidate | Severity | Why defer |
|---|---|---|
| Empty transcript hierarchy (`py-[10vh]` centered empty in `NekoTranscript`) | P2 · S | Operational copy already present (starters + `/` · Ctrl+K). Large pad is aesthetic vs ZCode calm density — not a task trap. |
| Filter empty chrome (Dự án / Gần đây / Harness + state when 0 sessions) | P2 · S | Loud but usable; empty copy honest. Collapse is nice-to-have. |
| Theme light `--nk-text-3` === `--nk-ghost` (`#69655f`) | P2 · XS | Dark already differentiates. Light flatten is tertiary hierarchy only — not blocking. |
| Theme toggle absence in chill preview | P2 · M | Product choice; out of Batch2 claim. |

Decision rule from parent: **ONE more BIG polish PR only if clearly task-blocking vs ZCode**. None of the above clear that bar → **CLEAN-STOP**.

## Parking lot (Batch 3+ — unclaimed)

1. Tighten empty transcript pad / hierarchy (keep starters + slash hint).
2. Soft-collapse session-list filter chrome when catalog empty.
3. Cheap light-token ghost vs text-3 split (optional).
4. Optional appearance control if product wants dark in chill.

## Out of scope (unchanged)

- Brand copy from ZCode / other products
- Backend / Tauri beyond existing helpers
- Dependabot / research PRs
- Broad CSS redesign

## Claimed surfaces

**None.** Batch 2 claims released with this CLEAN-STOP.
