# UX quality review contract

Apply incrementally to real observed flows, not as a claim of perfect/SOTA compliance.

For each control: user goal, visible label, enabled/disabled reason, keyboard access, focus, hit area, feedback, failure recovery, cancellation, persistence, duplicate action, and next step. Use a consistent distinction between requested, accepted, executing, confirmed terminal, and unknown outcome. Do not describe receipt correlation as OS isolation.

Priority order: lost input or wrong authority; dead ends and misleading state; recovery/accessibility; wording/navigation; visual polish. Keep Wiii/Neko approved identity. Use synthetic projects, exact hashes and before/after screenshots.

References checked 2026-10-02:
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
- Target size minimum, including documented exceptions: https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum
- Keyboard focus visibility: https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum
- Nielsen Norman Group usability heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/

These guide review; screenshots alone cannot establish accessibility compliance or user-tested usability.

## Control wording follow-up
Observed in native QA: End session led to a cancelled Run label; profile loading briefly used a failure-like disabled-send title. Clarify labels only: “Dừng lượt đang chạy”, “Kết thúc phiên” with retained-history explanation, “Đã dừng” for cancelled Run, and a distinct loading message. Runtime state transitions and cancellation authority remain unchanged. Validate existing button contracts and safe deletion guidance.
