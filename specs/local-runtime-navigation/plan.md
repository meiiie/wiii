# Plan
1. Capture current native failure: returning to Work ends the idle process.
2. Add one inherited React ownership boundary for the local workbench. Standalone ADE/Neko previews retain explicit cleanup ownership.
3. Keep runtime event handling in the existing store. No hidden screens, changed dispatch logic, or broadened authorization.
4. Regression: nested screen navigation does not dispose/restart reaper; outer exit disposes once; web cannot initialize local boundary; busy/permission guards remain. Run existing teardown suites, full frontend, TypeScript, desktop/embed/native builds.
5. Native fixture: launch, finish, explicit close/resume, navigate Work and back repeatedly. Check exact Run identity, session runtime identity, input counts, and visible explanations. No external provider calls.
