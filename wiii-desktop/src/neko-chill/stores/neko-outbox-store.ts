import { create } from "zustand";
import { v4 as uuid } from "uuid";
import { loadStoreStrict, saveStoreStrict } from "@/lib/storage";
import { DurableOutbox, emptyOutbox, sameOutboxBinding, type OutboxBinding, type OutboxSnapshot } from "../durable-outbox";
import { useNekoSessionStore } from "./neko-session-store";

interface OutboxState { snapshot: OutboxSnapshot; ready: boolean; error: string | null }
export const useNekoOutboxStore = create<OutboxState>(() => ({ snapshot: emptyOutbox(), ready: false, error: null }));
let owners = 0;
let pendingPump = false;
let hydration: Promise<void> | null = null;
const pausing = new Set<string>();
export function sessionOutboxBinding(sessionId: string): OutboxBinding | null {
  const s = useNekoSessionStore.getState().sessions[sessionId];
  if (!s?.workspace || s.taskScope?.state === "invalid" || s.taskScope?.state === "recovery-required") return null;
  return { sessionId, workspace: s.workspace.path,
    task: s.taskScope ? `${s.taskScope.execution.runId}:${s.taskScope.authorizedRoot}` : "legacy",
    model: JSON.stringify([s.launchProfile?.id ?? null, s.controls.filter(c => c.category === "model").map(c => [c.id, c.currentValue])]) };
}
function canSend(sessionId: string): boolean {
  const s = useNekoSessionStore.getState().sessions[sessionId];
  return Boolean(owners && s && (s.status === "idle" || s.status === "exited") && !s.pendingControlId
    && !s.pendingPermission && !s.resolvingPermissionId && !s.cancelPending && !s.closePending && !s.deletePending);
}
function schedulePump(): void {
  if (!owners || pendingPump) return;
  pendingPump = true;
  queueMicrotask(() => {
    pendingPump = false;
    if (!owners) return;
    for (const q of outbox.snapshot.queues) {
      void outbox.dispatch(q.sessionId, () => sessionOutboxBinding(q.sessionId), () => canSend(q.sessionId), async (text, accepted, binding) => {
        await useNekoSessionStore.getState().sendPromptToSession(q.sessionId, text, accepted, () => {
          const current = sessionOutboxBinding(q.sessionId);
          return current !== null && sameOutboxBinding(current, binding);
        });
        return useNekoSessionStore.getState().sessions[q.sessionId]?.status === "idle";
      }).catch(() => {});
    }
  });
}
export const outbox = new DurableOutbox({
  read: () => loadStoreStrict("neko-outbox-v1.json", "outbox", emptyOutbox()),
  write: state => saveStoreStrict("neko-outbox-v1.json", "outbox", state),
}, () => {
  useNekoOutboxStore.setState({ snapshot: outbox.snapshot, ready: outbox.ready, error: outbox.error });
  schedulePump();
});
export function hydrateOutbox(): Promise<void> {
  if (!hydration) hydration = outbox.hydrate().finally(() => { hydration = null; });
  return hydration;
}
export async function enqueueSessionMessage(sessionId: string, text: string): Promise<void> {
  const s = useNekoSessionStore.getState().sessions[sessionId];
  const binding = sessionOutboxBinding(sessionId);
  if (!s || !binding || !["streaming", "dispatching", "idle"].includes(s.status)
    || s.pendingPermission || s.pendingControlId || s.closePending || s.deletePending || s.cancelPending) {
    throw new Error("Phiên chưa thể nhận tin chờ. Bản nháp được giữ lại.");
  }
  await outbox.enqueue(binding, text, uuid());
}
export function startNekoOutbox(): () => void {
  owners += 1;
  void hydrateOutbox().catch(() => {});
  const unsubscribe = useNekoSessionStore.subscribe(state => {
    for (const q of outbox.snapshot.queues) {
      const s = state.sessions[q.sessionId];
      if (q.items.length && !q.paused && !pausing.has(q.sessionId)
        && (!s || s.status === "error" || s.status === "exited" || s.cancelPending || s.closePending || s.deletePending)) {
        pausing.add(q.sessionId);
        void outbox.pause(q.sessionId, "Phiên đã dừng, đóng hoặc gặp lỗi. Kiểm tra trước khi tiếp tục hàng đợi.")
          .catch(() => {}).finally(() => pausing.delete(q.sessionId));
      }
    }
    schedulePump();
  });
  return () => {
    unsubscribe();
    owners -= 1;
    if (!owners) for (const q of outbox.snapshot.queues) if (q.items.length) {
      void outbox.pause(q.sessionId, "Đã rời không gian làm việc. Hàng đợi được giữ lại.").catch(() => {});
    }
  };
}
