# Integration plan

Base: Wiii 31ba311a73cec24560b455cf4134b579636b760d. Preserve handoff in its own local commit, then apply reviewed combined PR993/995 delta from 00b1f0a2ad216b65245b8be98b22740aed65a7d3 with a three-way merge.

Shared paths: runtime.rs, driver-factory.test.ts, control-client.ts. Runtime must keep canonical cwd/task binding and use ResolvedProvider.command() for updater ownership. Keep PathBuf; remove obsolete Command import.

## Runtime compatibility
The existing published Neko 1.7.0 pin lacks task-v1. Do not present it as compatible with the new task-scoped flow. Development candidate: Neko 8b3354fcb5b76c55061b9e439c241faf7ecbbcae, compiled with CI-pinned Bun 1.4.0, separate filename and SHA256. Its source version string remains 1.7.0 and is insufficient identity. Never replace the official release lock digest with development bytes. Release integration remains blocked until a compatible governed artifact or separately reviewed candidate channel exists.

## Verification
Run 231-file frontend suite, tsc, frontend/embed builds, Python release suite, native Rust suite and build. Use fresh synthetic HOME/project and loopback provider for task capability/root/identity and response validation. Native UI acceptance and live OpenCode acceptance remain separate; existing outbound policy denial is not bypassed.

## Risk and rollback
High-risk native lifecycle/task boundary: preserve fail-closed capability checks and no replay of unknown effects. No data migration. Original input and separate snapshot commit allow review/reconstruction without reset or overwriting the team checkout. Roll back only integration changes on this local branch.
