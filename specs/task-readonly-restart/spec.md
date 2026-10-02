# Read-only restart must not create a load attempt

Native QA: delta was explicitly ended (native journal cancelled/completed, PID null). First cold open persisted a pending-load task scope while saving journal reconciliation. A second cold open, without a user prompt, interpreted this as unfinished-load and blocked the session. Reading history must not record intent to execute.

Preserve a validated durable bound receipt on restore. The restored session has no runtime and is exited; the existing explicit-send path calls beginNekoTaskLoad and strictly persists intent before any provider startup, then validates epoch/root/membership and writes the new receipt. Interrupted pending-new/pending-load and recovery-required states remain blocked. Do not migrate existing ambiguous pending-load records: they cannot be safely distinguished from real interrupted loads.

Risks: accidentally reusing stale live admission, weakening replay protection. Verify explicit load writes/receipt tests and native restart twice without sending; the final explicit new prompt must advance epoch exactly once. No bypass of existing ambiguous history. Rollback this isolated mapping change if validation fails.
