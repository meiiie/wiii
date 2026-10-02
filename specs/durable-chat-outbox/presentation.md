# Compact queue presentation

The queue lives directly above the composer as a shallow tray. Each row shows its order, one-line text preview, edit and remove actions. Full content is available by expanding the text. The list has a viewport-bounded scroll area; collapse never hides paused/uncertain guidance or the resume control. No hover-only actions, permanent decorative animation, new dependencies or hidden send-now semantics.

ZCode reference: zai-org/ZCode, HEAD 29628c9acdb81b703bbd4080c207a0e7ce5e276e, verified 2026-10-02. Studied ConversationQueuePanel.tsx, SessionPane queue command handlers, composer routing and draft-revision guards. Adopted compact rows and shared composer dock, not source code. Wiii retains inline editing because its composer may already hold a draft; it never withdraws a queued item into a conflicting draft. Drag-reorder and stop-and-send-now remain outside this presentation change.

Invariants: durable pause acknowledged before editing; failed writes retain edited text; only one pending mutation; save/cancel leaves queue paused; uncertain delivery cannot resume; delivering rows cannot mutate; queue controls use named keyboard-accessible buttons. Collapsing during edit is disabled. Session-keyed mounting prevents draft bleed across sessions. Presentation does not change FIFO or context binding.

Validation: focused panel tests, composer deferred-admission tests, all desktop tests, typecheck, desktop/embed builds and native Linux fixture screenshots. Real-provider and cross-platform acceptance remain separate. Rollback is limited to presentation files; queue persistence format remains version 1.
