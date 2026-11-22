# Research decisions

- Extend Wiii's explicit native PID-1 migration, not ACP load. Neko task v1 intentionally fails closed with typed `writer_unavailable`. Task stores use `.neko-core/task-sessions/<id>.json` and `<id>.lock`; legacy stores use `sessions/<id>.json.lock`. Their old locks contain only PID/token/acquiredAt.
- Existing native recovery already serializes start admission and independently proves Linux namespace absence. Extend its ownership proof with exact checkpoint/receipt/root and full execution identity; never trust renderer-supplied PIDs, paths or stop assertions.
- A real scoped conversation Quit cleanly with cancelled/completed, active continuity and null PID, yet retained its PID-1 writer lock. The older unknown-outcome case also fails on the parent version and must remain untouched.
- Reject unscoped fallback, unlink-on-load, journal fabrication and a bundled Neko Core change. Maintainer approved the existing-button/native-proof approach and live-owner refusal tests.
- Linux lacks PowerShell; reproduce setup-plan's template/path steps directly on the existing issue branch. No extension hooks are configured. No unresolved design questions.
