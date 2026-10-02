# Explicit Work launch intent

Owner request 2026-10-02: improve Wiii UX at button, wording, state and flow level; avoid dead ends. First native-reproduced defect: Work goal admitted as a scoped session but not dispatched, leaving `(no messages)` while Work says running.

One click on Send and open session must preserve the displayed goal and acceptance criteria, bind the exact created session durably, then dispatch that intent once through existing guarded transport. Navigation cannot redirect it. Admission/binding failure cannot trigger fallback or automatic retry. Manual drafts are preserved until accepted and are independent from Work intent.

Original branding, typography, host security, provider choice and model authority are not redesigned. Issue #996 was opened after approval. The owner then deferred further GitHub/PR work; continue locally.

Work title remains the owner-provided goal, independent from provider transcript title and the longer first prompt containing acceptance criteria. Manual chat retains existing title behavior.
