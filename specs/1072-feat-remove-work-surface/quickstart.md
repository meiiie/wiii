# Verification

1. Run native lease and focused task mapping/recovery/client regressions, then TypeScript, full desktop tests/embed build and diff checks.
2. Create a real Work task with harmless unique context in an isolated parent-version native profile. Verify its real fixed-task receipt, answer and native mapping; do not synthesize a persisted fixture for UI acceptance.
3. Tray Quit and prove host exit plus terminal/known native state; retain the Work snapshot checksum.
4. Open the same profile in removal build at 800×600. Open the old transcript, use existing recovery if stale writer blocks, then explicitly send a harmless context-check follow-up.
5. Verify same backend, fresh receipt, retained context and unchanged Work snapshot. Keep the original unknown-outcome thread blocked. Never manually delete a lock to pass acceptance.
