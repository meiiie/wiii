# Retained identity and transition

Wiii thread binds original backend, workspace, task/run/environment and runtime-attached native correlation. Only `recovery-required / writer-unavailable` with a full fixed-task v1 receipt is retryable here.

The read-only Core checkpoint must match session ID, schema 2/3, canonical root, active task/label and protocol activation. The native bound execution must be terminal with known continuity; physical namespace absence is separate proof. A renderer flag or lock PID alone never suffices.

Transition: typed writer-unavailable -> explicit native proof -> strictly persisted bound mapping -> later explicit pending-load -> independently validated fresh receipt. Save failure restores recovery-required; no prompt is dispatched. Missing-lock retries still require the same full proof.
