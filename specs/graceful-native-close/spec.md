# Close owned runtimes before cancelling orphan starts

Observed on Linux: `cancelUnresolvedStarts` scans all nonterminal legacy sessions for a client identity, including the current bound runtime. Calling it before `RuntimeRegistry.detach` kills that runtime before its ACP session/close request. The subsequent close write fails invalid_state. Neko cannot release its writer lease; its PID-only stale detection sees PID 1 in a later namespace and refuses the old session.

Fix Wiii's normal lifecycle ordering: await dispatch barriers, let the owned driver perform graceful ACP close and native cleanup, then run orphan cancellation as a final safety sweep. Aggregate either failure into an uncertain cleanup result. Deletion must use the same order for bound runtimes and preserve data when any cleanup remains unconfirmed. No namespace containment is weakened and no writer lock is removed by Wiii.

This does not repair already stranded leases or prove recovery after an abrupt process death. Neko's PID-only stale-lease identity needs a separate namespace-aware protocol or OS-backed writer lock. Keep old ambiguous sessions blocked rather than claiming they were safely recovered.

Validation: two regression tests first fail with orphan cleanup before driver disposal (close and delete), then pass. Task-scoped and retained-start tests remain required. Native acceptance must create a fresh session, close it, confirm lease release, restart and resume it; old synthetic broken sessions are not healed by deleting locks.
