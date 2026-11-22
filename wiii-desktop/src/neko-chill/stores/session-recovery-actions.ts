/** User-requested orphan stop. Native termination and a saved checkpoint precede reuse. */
import { persistSessionStrict } from "../persistence";
import { isNekoTaskScopeMapping } from "../task-scope-mapping";
import {
  NATIVE_TERMINAL_STATES, nativeTaskId, nativeSessionsForTask, nativeRuntimeIdentity,
  nativeRunBlocksRespawn, retireAbsentNativeCheckpoints, reconcileNativeRuntime,
} from "./session-native-recovery";
import type { SessionSet, SessionGet, NekoSessionState } from "./session-store-types";
import type { SessionRuntime } from "./session-runtime-lifecycle";

export function createSessionRecoveryActions(set: SessionSet, get: SessionGet, runtime: SessionRuntime): Pick<NekoSessionState, "recoverSession"> {
  const { runtimes, closeOperations, waitForHolds, dispatchBarriers, runtimeOperations } = runtime;
  return {
    recoverSession: (sessionId) => {
      const current = get().sessions[sessionId];
      if (!current || current.deletePending) return Promise.resolve();
      if (current.closePending) return closeOperations.get(sessionId) ?? Promise.resolve();
      if (current.taskScope && (!isNekoTaskScopeMapping(current.taskScope) || current.taskScope.state === "recovery-required")) return Promise.resolve();
      if (current.runtime || runtimes.get(sessionId) || runtimes.hasRetainedCleanup(sessionId)
        || (!current.nativeRecoveryRequired && !nativeRunBlocksRespawn(current))) return Promise.resolve();

      set(state => {
        const session = state.sessions[sessionId];
        session.closePending = true;
        session.nativeRecoveryRequired = true;
        session.status = "stopping";
        session.statusDetail = "Đang dừng phiên cũ…";
      });
      const operation = (async () => {
        let stopped = false;
        try {
          await waitForHolds(dispatchBarriers, sessionId);
          await waitForHolds(runtimeOperations, sessionId);
          const reader = runtime.readNativeControl();
          const session = get().sessions[sessionId];
          const before = nativeSessionsForTask(await reader.listSessions(), session);
          const liveIds = new Set(Object.values(get().sessions).flatMap(other => {
            const provider = runtimes.get(other.id) ?? other.runtime;
            return provider ? [nativeRuntimeIdentity(provider).agentSessionId] : [];
          }));
          // Never stop another visible/live owner when reconciling older runs of a Task.
          if (before.some(native => liveIds.has(native.agentSessionId))) throw new Error("Live owner still attached");
          const active = before.filter(native => !NATIVE_TERMINAL_STATES.has(native.state));
          if (active.length) await reader.cancelUnresolvedStarts(sessionId, {
            taskId: nativeTaskId(session), agentSessionIds: active.map(native => native.agentSessionId),
          });

          const candidate = { ...get().sessions[sessionId], events: [...get().sessions[sessionId].events] };
          const natives = nativeSessionsForTask(await reader.listSessions(), candidate);
          retireAbsentNativeCheckpoints(candidate, natives);
          for (const native of natives) await reconcileNativeRuntime(candidate, native, reader);
          // A cancel receipt, missing record, or UI flag alone is never stop proof.
          if (nativeRunBlocksRespawn(candidate)) throw new Error("Native stop not proven");
          stopped = true;
          set(state => {
            const target = state.sessions[sessionId];
            target.events = candidate.events;
            target.eventHighWaterMark = candidate.eventHighWaterMark;
          });
          // Keep replay cursors in memory if a later write fails, but keep sending locked.
          await persistSessionStrict(get().sessions[sessionId]);
          set(state => {
            const target = state.sessions[sessionId];
            target.status = "exited";
            target.nativeRecoveryRequired = false;
            target.pendingPermission = null;
            target.resolvingPermissionId = null;
            target.pendingControlId = null;
            target.cancelPending = false;
            target.statusDetail = "Bạn có thể tiếp tục trò chuyện.";
          });
        } catch {
          set(state => {
            const target = state.sessions[sessionId];
            if (!target) return;
            target.status = "error";
            target.statusDetail = stopped
              ? "Chưa lưu được cuộc trò chuyện. Bạn có thể thử lại."
              : "Chưa dừng được phiên cũ. Bạn có thể thử lại.";
          });
        }
      })();
      const tracked = operation.finally(() => {
        if (closeOperations.get(sessionId) !== tracked) return;
        set(state => { if (state.sessions[sessionId]) state.sessions[sessionId].closePending = false; });
        closeOperations.delete(sessionId);
      });
      closeOperations.set(sessionId, tracked);
      return tracked;
    },
  };
}
