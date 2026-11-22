# Explicit scoped compatibility recovery

Keep `neko_control_legacy_lease_recover` request unchanged: `clientSessionId`, `backendSessionId` only. Renderer paths, PIDs, receipts or stop assertions remain forbidden; native reads its catalog/files under start-admission serialization.

Scoped success needs exact saved mapping/checkpoint proof and physical quiescence. A missing previously removed lock is retryable only with that same proof, so strict persistence failure cannot strand one-time removal. Unsupported platform/format or unproven result never authorizes clearing scoped recovery.

The existing button dispatches no new/load/prompt RPC. A later explicit send retains fixed scope/backend and must obtain the next validated activation before prompt dispatch. Ordinary legacy recovery keeps its existing behavior.
