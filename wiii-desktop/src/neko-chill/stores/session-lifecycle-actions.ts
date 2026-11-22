/** Close/delete barriers and durable transcript retention or removal. */
import { nativeRunBlocksRespawn, nativeRuntimeIdentity } from "./session-native-recovery";
import { observeRuntimeDetach, appendRuntimeCleanupFact, cleanupFailureReason } from "./session-runtime-facts";
import { deletePersistedSession } from "../persistence";
import { useNekoWorkspaceStore } from "./neko-workspace-store";
import type { SessionSet, SessionGet, NekoSessionState } from "./session-store-types";
import type { SessionRuntime } from "./session-runtime-lifecycle";
export function createSessionLifecycleActions(set: SessionSet, get: SessionGet, runtime: SessionRuntime): Pick<NekoSessionState, "closeSession" | "deleteSession" | "setActiveSession"> {
  const { drainPresentationStreams, runtimes, closeOperations, waitForHolds, dispatchBarriers, runtimeOperations, persistSessionNowOrReport, discardPresentationStreams } = runtime;
  return {
    closeSession: (sessionId) => {
      drainPresentationStreams(sessionId);
      const current = get().sessions[sessionId];
      if (!current || current.deletePending)
        return Promise.resolve();
      if (!current.runtime &&
        !runtimes.get(sessionId) &&
        !runtimes.hasRetainedCleanup(sessionId) &&
        nativeRunBlocksRespawn(current)) {
        return get().recoverSession(sessionId);
      }
      if (current.closePending) {
        return closeOperations.get(sessionId) ?? Promise.resolve();
      }
      set((state) => {
        const session = state.sessions[sessionId];
        if (session) {
          session.closePending = true;
          session.status = "stopping";
        }
      });
      const operation = (async () => {
        await waitForHolds(dispatchBarriers, sessionId);
        const expectedProvider = runtimes.get(sessionId) ?? get().sessions[sessionId]?.runtime ?? null;
        const cleanup = await observeRuntimeDetach(runtimes.detach(sessionId));
        // The durable legacy scan also finds live bound sessions. Give their
        // ACP session/close handshake a chance to release writer leases BEFORE
        // invoking the native orphan-kill fallback.
        let orphanFailure: unknown;
        try {
          await runtime.readNativeControl().cancelUnresolvedStarts(sessionId);
        }
        catch (error) {
          orphanFailure = error;
        }
        const closeFailed = cleanup.failed || orphanFailure !== undefined;
        const provider = cleanup.failed ? expectedProvider : cleanup.provider ?? expectedProvider;
        await waitForHolds(runtimeOperations, sessionId);
        set((state) => {
          const session = state.sessions[sessionId];
          if (session) {
            session.runtime = null;
            session.executionProjection = undefined;
            if (provider) {
              appendRuntimeCleanupFact(session, provider, "close", cleanup);
            }
            session.status = closeFailed ? "error" : "exited";
            session.pendingPermission = null;
            session.resolvingPermissionId = null;
            session.cancelPending = false;
            session.statusDetail = closeFailed
              ? `Neko chưa thể xác nhận runtime đã dừng; không thể khởi động lại an toàn: ${cleanupFailureReason(orphanFailure ?? (cleanup.failed ? cleanup.error : undefined))}`
              : "Đã kết thúc phiên — nhắn tiếp để khởi động lại agent.";
            session.updatedAt = Date.now();
          }
        });
        await persistSessionNowOrReport(sessionId, "trạng thái đóng phiên", {
          fatal: closeFailed,
          strict: closeFailed,
        });
      })();
      let tracked!: Promise<void>;
      tracked = operation.finally(() => {
        if (closeOperations.get(sessionId) === tracked) {
          set((state) => {
            const session = state.sessions[sessionId];
            if (session)
              session.closePending = false;
          });
          closeOperations.delete(sessionId);
        }
      });
      closeOperations.set(sessionId, tracked);
      return tracked;
    },
    deleteSession: async (sessionId) => {
      drainPresentationStreams(sessionId);
      const current = get().sessions[sessionId];
      // Acquire the lifecycle lock before awaiting a close or runtime teardown.
      if (!current || current.deletePending)
        return;
      set((state) => {
        const session = state.sessions[sessionId];
        if (session) {
          session.deletePending = true;
          session.status = "stopping";
        }
      });
      try {
        if (!runtimes.get(sessionId) && !runtimes.hasRetainedCleanup(sessionId)) {
          await runtime.readNativeControl().cancelUnresolvedStarts(sessionId);
        }
      }
      catch (error) {
        set((state) => {
          const session = state.sessions[sessionId];
          if (!session)
            return;
          session.deletePending = false;
          session.status = "error";
          session.statusDetail =
            `Không thể xóa phiên vì một runtime native chưa được đối soát: ${error instanceof Error ? error.message : String(error)}`;
        });
        return;
      }
      const refreshed = get().sessions[sessionId];
      if (refreshed &&
        !refreshed.runtime &&
        !runtimes.get(sessionId) &&
        !runtimes.hasRetainedCleanup(sessionId) &&
        nativeRunBlocksRespawn(refreshed)) {
        set((state) => {
          const session = state.sessions[sessionId];
          if (!session)
            return;
          session.deletePending = false;
          session.status = "error";
          session.statusDetail =
            "Neko chưa thể xác nhận runtime native đã dừng; không xóa phiên khi kết quả execution còn chưa chắc chắn.";
        });
        return;
      }
      const expectedProvider = runtimes.get(sessionId) ?? current.runtime;
      await closeOperations.get(sessionId)?.catch(() => { });
      await waitForHolds(dispatchBarriers, sessionId);
      const cleanup = await observeRuntimeDetach(runtimes.detach(sessionId));
      let orphanFailure: unknown;
      try {
        await runtime.readNativeControl().cancelUnresolvedStarts(sessionId);
      }
      catch (error) {
        orphanFailure = error;
      }
      const provider = cleanup.failed ? expectedProvider : cleanup.provider ?? expectedProvider;
      await waitForHolds(runtimeOperations, sessionId);
      if (orphanFailure !== undefined && !cleanup.failed) {
        set(state => {
          const session = state.sessions[sessionId];
          if (!session)
            return;
          session.runtime = null;
          session.deletePending = false;
          session.status = "error";
          session.statusDetail = `Không thể xóa phiên vì một runtime native chưa được đối soát: ${cleanupFailureReason(orphanFailure)}`;
          if (provider)
            appendRuntimeCleanupFact(session, provider, "delete", cleanup);
        });
        await persistSessionNowOrReport(sessionId, "lỗi đối soát trước khi xóa", { strict: true });
        return;
      }
      if (cleanup.failed) {
        set((state) => {
          const session = state.sessions[sessionId];
          if (!session)
            return;
          session.runtime = null;
          session.executionProjection = undefined;
          session.deletePending = false;
          session.status = "error";
          session.statusDetail = `Không thể xóa phiên vì runtime chưa đóng sạch: ${cleanupFailureReason(cleanup.error)}`;
          if (provider) {
            const identity = nativeRuntimeIdentity(provider);
            const alreadyRecorded = session.events.some((event) => (event.data.type === "native-runtime-cleanup-uncertain" &&
              event.data.agentSessionId === identity.agentSessionId));
            if (!alreadyRecorded) {
              appendRuntimeCleanupFact(session, provider, "delete", cleanup);
            }
          }
        });
        await persistSessionNowOrReport(sessionId, "lỗi cleanup trước khi xóa", {
          strict: true,
        });
        return;
      }
      try {
        await deletePersistedSession(sessionId);
      }
      catch (error) {
        set((state) => {
          const session = state.sessions[sessionId];
          if (!session)
            return;
          session.runtime = null;
          session.executionProjection = undefined;
          session.deletePending = false;
          session.status = "error";
          session.statusDetail = `Không thể xóa phiên khỏi bộ nhớ bền: ${error instanceof Error ? error.message : String(error)}`;
        });
        return;
      }
      set((state) => {
        delete state.sessions[sessionId];
        if (state.activeSessionId === sessionId) {
          state.activeSessionId = null;
        }
      });
      discardPresentationStreams(sessionId);
      useNekoWorkspaceStore.getState().clearSession(sessionId);
    },
    setActiveSession: (sessionId) => {
      set((state) => {
        state.activeSessionId = sessionId;
      });
    }
  };
}
