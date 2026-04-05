# Embedded Operator Hardening — 2026-03-22

## Scope
- Harden `preview -> confirm -> apply` for LMS host actions.
- Add org-level capability policy coverage.
- Add student-safe quiz/assignment coaching evals without overriding Wiii's core identity.

## What Changed

### Backend
- `host_context.py`
  - Added `permission` and `required_permissions` to `HostActionDefinition`.
  - `build_operator_session_v1(...)` now accepts `host_action_feedback`.
  - Operator session now recognizes pending previews and changes `next_best_step` toward explicit confirm/apply flows.
- `graph.py`
  - `_inject_operator_context(...)` now passes structured `host_action_feedback` into `build_operator_session_v1(...)`.
- `adapters/lms.py`
  - Strengthened student-safe host instructions:
    - quiz/exam: no direct answers, no choosing the correct option for the learner, no doing the quiz for them
    - assignment: no writing the final submission for the learner; guide approach, outline, rubric, stepwise hints

### Tests
- `test_sprint222b_action_tools.py`
  - added approval-required coverage
  - added preview-required coverage
  - added matching preview token auto-reuse coverage
  - added mismatched preview-kind rejection coverage
- `test_sprint234_capability_policy.py`
  - student blocked from `manage:courses`
  - teacher allowed for `manage:courses`
  - role restriction wins even if permission exists
  - org-admin/owner governance case
  - host capability filtering removes disallowed tools
- `test_sprint222_graph_injection.py`
  - host capability filtering for student prompt injection
  - operator prompt becomes preview-aware when feedback includes a pending preview token
- `test_sprint222_host_context.py`
  - operator session preview-aware next-step coverage
- `test_sprint234_student_safe_coach.py`
  - quiz prompt anti-answer eval
  - assignment prompt anti-ghostwriting eval
  - runtime skill stack eval for student quiz coaching
  - teacher course-editor stack excludes student coach
- `wiii-desktop`
  - feedback persistence tests for host action preview/apply follow-up continuity

## Identity Safety
- LMS remains a host/plugin overlay only.
- No runtime product skill or operator prompt in this slice changes Wiii's soul/card/personality.
- New behavior only affects:
  - what host actions are visible
  - whether a mutating action needs preview/confirmation
  - how student-safe guardrails are expressed on quiz/assignment pages

## Verification
- Backend targeted:
  - `110 passed`
- Desktop targeted:
  - `39 passed`
- LMS Angular:
  - `tsc --noEmit` pass
- Wiii desktop:
  - `tsc --noEmit` pass

## Current State
- `preview -> confirm -> apply` is now materially more real:
  - preview feedback survives to the next turn
  - operator prompt understands pending preview state
  - apply/publish actions refuse to run silently
  - matching preview tokens can be reused automatically after explicit confirmation
- org-level host capability filtering is now covered by explicit tests
- student-safe coaching now has concrete anti-leakage evals

## Next Recommended Slice
1. Add real `preview_panel` UI affordance in Wiii desktop so preview summaries are visually inspectable, not only remembered semantically.
2. Add audit logging for mutating host actions (`preview_created`, `apply_confirmed`, `publish_confirmed`).
3. Add LMS-side action tests for:
   - `preview_lesson_patch`
   - `apply_lesson_patch`
   - `preview_quiz_commit`
   - `apply_quiz_commit`
   - `preview_quiz_publish`
   - `apply_quiz_publish`
4. Add student-safe E2E prompts against real LMS quiz/assignment pages to verify no-answer leakage under more adversarial wording.
