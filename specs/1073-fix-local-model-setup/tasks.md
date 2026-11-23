# Tasks: Local model setup

Input: [plan.md](plan.md), [spec.md](spec.md), research/data-model/contracts/quickstart.

## Phase1: Setup
- [x] T001 Verify canonical Neko1.9.5 profile/home/credential contracts in specs/1073-fix-local-model-setup/research.md.

## Phase2: Foundation
- [x] T002 Define bounded status/save and canonical safe-file operations in wiii-desktop/src-tauri/src/neko/local_models.rs.
- [x] T003 Wire main-only commands/capability in wiii-desktop/src-tauri/src/commands/local_models.rs and wiii-desktop/src-tauri/tests/security_contract.rs.

## Phase3: First model (US1, P1)
Independent test: fresh native profile reaches setup and an authorized real response without terminal/Service.
- [x] T004 [US1] Add typed native bridge in wiii-desktop/src/lib/local-model-setup.ts.
- [x] T005 [US1] Build accessible masked setup form in wiii-desktop/src/neko-chill/components/LocalModelSetupDialog.tsx.
- [x] T006 [US1] Wire Overview/ProjectHome/File actions and returned selection in wiii-desktop/src/neko-chill/NekoChillApp.tsx and existing entry components.
- [x] T007 [US1] Add field/native-only/selection regressions in wiii-desktop/src/__tests__/neko-chill/local-model-setup.test.tsx.

## Phase4: Correction without loss (US2, P1)
Independent test: invalid/save failure/cancel/reopen preserve exact draft and restore focus.
- [x] T008 [US2] Verify malformed/symlink/no-overwrite/legacy-key ownership in wiii-desktop/src-tauri/src/neko/local_models.rs tests.
- [x] T009 [US2] Verify cancel/error/retry/focus/draft in wiii-desktop/src/__tests__/neko-chill/local-model-setup.test.tsx and project-home tests.

## Phase5: Restart (US3, P2)
Independent test: genuine native File Quit/reopen retains saved profile and authorized use.
- [ ] T010 [US3] Verify private canonical persistence across reopen via specs/1073-fix-local-model-setup/quickstart.md; evidence outside git.

## Phase6: Cross-cutting gates
- [x] T011 Run focused TS/Vitest/Rust/security/hook/diff gates and record results in specs/1073-fix-local-model-setup/quickstart.md/PR.
- [ ] T012 Complete native Light800/Dark1200 and original-profile audit per specs/1073-fix-local-model-setup/quickstart.md; deliver evidence, clean CI/Devin Review, delegated merge without release.

## Dependencies And Delivery

T001→T002→T003→US1→US2/US3→gates. Native contract and bridge/dialog could be developed independently after T002; recovery tests and restart evidence could run independently after US1, but execute serially on this shared native VM. MVP is US1; all stories/gates are required for this focused PR. Twelve checklist tasks: foundation3, US1 four, US2 two, US3 one, final gates two. All tasks have ids/paths/story labels where applicable.
