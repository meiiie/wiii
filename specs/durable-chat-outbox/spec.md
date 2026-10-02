# Durable per-session chat outbox

The outbox is user intent, not an agent runtime or capability grant. Enqueue succeeds only after strict snapshot persistence. Each item captures immutable session, workspace, task and model identity. The existing session store owns admission, native journal fencing, permission checks and dispatch.

FIFO delivery first persists `delivering`, then rechecks readiness and binding. Only a dispatched invocation with a completed idle turn removes the item. Failure, uncertain invocation, shutdown and restart hold the queue. Restored delivering items become uncertain and cannot be resumed automatically or by the generic Resume action; the user must inspect history and remove the ambiguous item. No exactly-once guarantee is claimed across a crash at the provider boundary.

Draft editing is distinct from admission. Accepted-callback releases the submission lock before the long-lived turn promise ends. Operation revisions prevent old completion from unlocking a newer pending enqueue. Editing a queued item pauses its queue first. Stop remains independently accessible. New input behind an existing queue cannot jump ahead of its items.

Storage failures retain the caller's draft and old durable snapshot. An in-memory safety hold blocks delivery after an error even if writing the hold fails. Per-session capacity is 100 items, each at most 64,000 characters. No silent truncation.

Rollback: stop queue delivery and retain `neko-outbox-v1.json`; older application versions ignore the additive store. Do not delete it. Existing session logs remain authoritative for reconciliation.

Validation: pure domain fault-injection tests; composer deferred-admission tests; runtime-owner lifecycle tests; native loopback model with explicitly delayed completion. Real provider auth and remote delivery are outside synthetic acceptance.
