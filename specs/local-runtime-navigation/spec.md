# Local runtime ownership across navigation

Owner requests local-only continuous UX work. Native test 2026-10-02 shows opening Work from an idle live Neko conversation unmounts NekoChillApp and calls disposeAllNekoRuntimes. This silently closes the process during ordinary navigation.

Keep one explicit runtime owner at the local workbench boundary. Work/Neko screen changes must not dispose runtimes or stop the idle reaper. Leaving the entire local boundary and standalone preview unmount still clean up. Nested surfaces inherit ownership; no hidden mounted UI or duplicate shortcuts. Preserve busy/permission navigation guards, explicit Stop/End, receipts, unknown-outcome handling and model/provider rules. No new automatic dispatch or resume.

Risks: premature cleanup, leaked background runtimes, duplicate reapers, eager local initialization on web. Verify nested/unmount tests, native navigation, existing mode-exit tests, full frontend/type/build. Rollback the ownership boundary change without deleting history; original per-screen cleanup returns.
