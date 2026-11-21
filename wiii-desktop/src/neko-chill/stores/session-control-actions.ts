/** Permission, stop, and configuration transactions against the current runtime. */
import { appendOwnedSessionEvent, removeEventById } from "./session-projections";
import { persistSessionBeforeDispatch } from "../persistence";
import type { NekoSessionEvent } from "../session-events";
import type { Driver } from "../drivers/types";
import { appendRuntimeCleanupFact, runtimeDisposalOutcome, cleanupFailureReason } from "./session-runtime-facts";
import type { SessionSet, SessionGet, NekoSessionState } from "./session-store-types";
import type { SessionRuntime } from "./session-runtime-lifecycle";
export function createSessionControlActions(set: SessionSet, get: SessionGet, runtime: SessionRuntime): Pick<NekoSessionState, "cancelTurn" | "resolvePermission" | "setConfigOption"> {
  const { drainPresentationStreams, runtimes, acquireHold, runtimeOperations, dispatchBarriers, persistSessionNowOrReport, observeInvocationAfterMarker, detachInstanceForRecovery, revokeRuntimeAfterDurabilityFailure } = runtime;
  return {
    cancelTurn: async () => {
      const sessionId = get().activeSessionId;
      if (!sessionId)
        return;
      drainPresentationStreams(sessionId);
      const provider = runtimes.get(sessionId);
      const session = get().sessions[sessionId];
      if (!provider ||
        !session ||
        session.cancelPending ||
        session.resolvingPermissionId ||
        session.closePending ||
        session.deletePending)
        return;
      const promptEventId = [...session.events].reverse().find(({ data }) => data.type === "dispatch-invoked"
        && data.action === "prompt" && data.providerInstanceId === provider.instanceId)?.data;
      const boundPromptId = promptEventId?.type === "dispatch-invoked" ? promptEventId.targetEventId : undefined;
      // A notify resolving is not terminal. Keep a once-only Stop latch per prompt.
      if (session.events.some(({ data }) => data.type === "runtime-command" && data.action === "cancel"
        && data.providerInstanceId === provider.instanceId && data.promptEventId === boundPromptId))
        return;
      const releaseOperation = acquireHold(runtimeOperations, sessionId);
      try {
        let commandEventId: string | null = null;
        set((state) => {
          const session = state.sessions[sessionId];
          if (session) {
            session.cancelPending = true;
            commandEventId = appendOwnedSessionEvent(session, "model", {
              type: "runtime-command",
              action: "cancel",
              providerInstanceId: provider.instanceId,
              ...(boundPromptId ? { promptEventId: boundPromptId } : {}),
              delivery: "staged",
            }).eventId!;
          }
        });
        const session = get().sessions[sessionId];
        if (!session)
          return;
        const releaseDispatchBarrier = acquireHold(dispatchBarriers, sessionId);
        try {
          await persistSessionBeforeDispatch(session);
        }
        catch (error) {
          set((state) => {
            const current = state.sessions[sessionId];
            if (current) {
              removeEventById(current.events as NekoSessionEvent[], commandEventId);
              current.cancelPending = false;
              current.statusDetail = error instanceof Error ? error.message : String(error);
            }
          });
          return;
        }
        finally {
          releaseDispatchBarrier();
        }
        let cancelStarted = false;
        try {
          const driver = runtimes.requireInstance(sessionId, provider.instanceId, "cancel");
          const invocation = driver.cancel();
          cancelStarted = true;
          set((state) => {
            const current = state.sessions[sessionId];
            if (current && commandEventId) {
              appendOwnedSessionEvent(current, "model", {
                type: "dispatch-invoked",
                targetEventId: commandEventId,
                action: "cancel",
                providerInstanceId: provider.instanceId,
              });
            }
          });
          const persistInvocation = persistSessionNowOrReport(sessionId, "xác nhận dispatch yêu cầu dừng", {
            strict: true,
          });
          const outcome = await observeInvocationAfterMarker(sessionId, provider, invocation, persistInvocation);
          if (!outcome.markerPersisted)
            return;
          if (outcome.invocationFailed)
            throw outcome.error;
        }
        catch (error) {
          let rolledBackUndispatchedCancel = false;
          set((state) => {
            const current = state.sessions[sessionId];
            if (current) {
              if (!cancelStarted) {
                removeEventById(current.events as NekoSessionEvent[], commandEventId);
                rolledBackUndispatchedCancel = true;
              }
              if (current.status !== "stopping" && current.status !== "exited") {
                current.statusDetail = error instanceof Error ? error.message : String(error);
              }
            }
          });
          if (rolledBackUndispatchedCancel) {
            await persistSessionNowOrReport(sessionId, "rollback yêu cầu dừng chưa gửi", {
              fatal: true,
              strict: true,
            });
          }
        }
      }
      finally {
        set((state) => {
          const current = state.sessions[sessionId];
          if (current)
            current.cancelPending = false;
        });
        releaseOperation();
      }
    },
    resolvePermission: async (optionId) => {
      const sessionId = get().activeSessionId;
      if (!sessionId)
        return;
      const session = get().sessions[sessionId];
      const request = session?.pendingPermission;
      if (!request ||
        session?.resolvingPermissionId ||
        session.cancelPending ||
        session.closePending ||
        session.deletePending)
        return;
      const provider = runtimes.get(sessionId);
      if (!provider)
        return;
      const releaseOperation = acquireHold(runtimeOperations, sessionId);
      let decisionEventId: string | null = null;
      let decisionPersisted = false;
      let resolutionStarted = false;
      set((state) => {
        const s = state.sessions[sessionId];
        if (s?.pendingPermission?.requestId === request.requestId) {
          // Acquire this approval synchronously so a double click cannot
          // append a conflicting decision while persistence is in flight.
          s.resolvingPermissionId = request.requestId;
          decisionEventId = appendOwnedSessionEvent(s, "model", {
            type: "permission-decision",
            requestId: request.requestId,
            optionId,
            providerInstanceId: provider.instanceId,
            delivery: "staged",
          }).eventId!;
        }
      });
      const releaseDispatchBarrier = acquireHold(dispatchBarriers, sessionId);
      try {
        await persistSessionBeforeDispatch(get().sessions[sessionId]);
        decisionPersisted = true;
        releaseDispatchBarrier();
        // Driver fails closed on null/unknown options (FR-006).
        const driver = runtimes.requireInstance(sessionId, provider.instanceId, "permission-resolution");
        const invocation = driver.resolvePermission({ requestId: request.requestId, optionId });
        resolutionStarted = true;
        set((state) => {
          const current = state.sessions[sessionId];
          if (current && decisionEventId) {
            appendOwnedSessionEvent(current, "model", {
              type: "dispatch-invoked",
              targetEventId: decisionEventId,
              action: "permission",
              providerInstanceId: provider.instanceId,
            });
          }
        });
        const persistInvocation = persistSessionNowOrReport(sessionId, "xác nhận dispatch quyết định", {
          strict: true,
        });
        const outcome = await observeInvocationAfterMarker(sessionId, provider, invocation, persistInvocation);
        if (!outcome.markerPersisted) {
          set((state) => {
            const s = state.sessions[sessionId];
            if (s?.pendingPermission?.requestId === request.requestId) {
              s.pendingPermission = null;
            }
            if (s?.resolvingPermissionId === request.requestId) {
              s.resolvingPermissionId = null;
            }
          });
          return;
        }
        if (outcome.invocationFailed)
          throw outcome.error;
        set((state) => {
          const s = state.sessions[sessionId];
          if (s?.pendingPermission?.requestId === request.requestId) {
            s.pendingPermission = null;
          }
          if (s?.resolvingPermissionId === request.requestId) {
            s.resolvingPermissionId = null;
          }
        });
      }
      catch (error) {
        let rolledBackUndispatchedDecision = false;
        set((state) => {
          const s = state.sessions[sessionId];
          if (s) {
            if (!decisionPersisted || !resolutionStarted) {
              removeEventById(s.events as NekoSessionEvent[], decisionEventId);
              rolledBackUndispatchedDecision = decisionPersisted;
            }
            if (s.resolvingPermissionId === request.requestId) {
              s.resolvingPermissionId = null;
            }
            s.statusDetail = error instanceof Error ? error.message : String(error);
          }
        });
        if (rolledBackUndispatchedDecision) {
          await persistSessionNowOrReport(sessionId, "rollback quyết định chưa gửi", {
            fatal: true,
            strict: true,
          });
        }
      }
      finally {
        releaseDispatchBarrier();
        releaseOperation();
      }
    },
    setConfigOption: async (optionId, value) => {
      const sessionId = get().activeSessionId;
      if (!sessionId)
        return;
      const session = get().sessions[sessionId];
      const option = session?.controls.find((candidate) => candidate.id === optionId);
      if (!session ||
        !option ||
        session.status !== "idle" ||
        session.pendingPermission ||
        session.pendingControlId ||
        session.closePending ||
        session.deletePending) {
        return;
      }
      const provider = runtimes.get(sessionId);
      if (!provider)
        return;
      try {
        runtimes.requireInstance(sessionId, provider.instanceId, "session-config");
      }
      catch (error) {
        set((state) => {
          const current = state.sessions[sessionId];
          if (current)
            current.statusDetail = error instanceof Error ? error.message : String(error);
        });
        return;
      }
      const releaseOperation = acquireHold(runtimeOperations, sessionId);
      try {
        const previousValue = option.currentValue;
        set((state) => {
          const current = state.sessions[sessionId];
          if (current) {
            current.pendingControlId = optionId;
            current.statusDetail = undefined;
            appendOwnedSessionEvent(current, "model", {
              type: "control-change",
              phase: "requested",
              optionId,
              previousValue,
              nextValue: value,
            });
          }
        });
        let driver: Driver;
        let configDispatched = false;
        const releaseControlLock = () => {
          set((state) => {
            const current = state.sessions[sessionId];
            if (current?.pendingControlId === optionId)
              current.pendingControlId = null;
          });
        };
        try {
          await persistSessionBeforeDispatch(get().sessions[sessionId]);
          driver = runtimes.requireInstance(sessionId, provider.instanceId, "session-config");
          configDispatched = true;
          await driver.setConfigOption(optionId, value);
          // Do not commit a response from a provider that was replaced while
          // its asynchronous configuration call was running.
          runtimes.requireInstance(sessionId, provider.instanceId, "session-config");
        }
        catch (error) {
          const reason = error instanceof Error ? error.message : String(error);
          let rollbackError: unknown;
          if (configDispatched) {
            try {
              // A rejected request is ambiguous: the provider may have applied
              // the value before its response was lost. Compensate only through
              // the exact provider instance that received the request.
              const rollbackDriver = runtimes.requireInstance(sessionId, provider.instanceId, "session-config");
              await rollbackDriver.setConfigOption(optionId, previousValue);
              runtimes.requireInstance(sessionId, provider.instanceId, "session-config");
            }
            catch (compensationError) {
              rollbackError = compensationError;
            }
          }
          const rollbackReason = rollbackError instanceof Error ? rollbackError.message : String(rollbackError ?? "");
          const revocation = rollbackError
            ? await detachInstanceForRecovery(sessionId, provider)
            : null;
          set((state) => {
            const current = state.sessions[sessionId];
            if (current) {
              const ownsControlLock = current.pendingControlId === optionId;
              const control = current.controls.find((candidate) => candidate.id === optionId);
              if (!rollbackError && ownsControlLock && control) {
                control.currentValue = previousValue;
              }
              if (revocation) {
                if (current.runtime?.instanceId === revocation.provider.instanceId) {
                  current.runtime = null;
                  current.executionProjection = undefined;
                }
                appendRuntimeCleanupFact(current, revocation.provider, "config-uncertain", runtimeDisposalOutcome(revocation));
              }
              if (ownsControlLock) {
                const lifecycleAlreadyClosed = current.status === "stopping" || current.status === "exited";
                if (rollbackError && revocation) {
                  current.status = revocation.cleanupFailed ? "error" : "exited";
                }
                else if (rollbackError && !lifecycleAlreadyClosed) {
                  current.status = "error";
                }
                if (!(rollbackError && !revocation && lifecycleAlreadyClosed)) {
                  current.statusDetail = rollbackError
                    ? revocation
                      ? revocation.cleanupFailed
                        ? `Cấu hình không xác định; runtime đã bị thu hồi nhưng cleanup báo lỗi: ${cleanupFailureReason(revocation.error)}`
                        : `Cấu hình không xác định sau lỗi "${rollbackReason}"; runtime đã được thu hồi. Nhắn tiếp để khởi động một runtime mới.`
                      : `Không thể xác nhận hoặc hoàn tác cấu hình: ${rollbackReason}`
                    : configDispatched
                      ? `Provider báo lỗi; đã hoàn tác cấu hình: ${reason}`
                      : reason;
                }
              }
              appendOwnedSessionEvent(current, "model", {
                type: "control-change",
                phase: rollbackError ? "rollback-failed" : "rolled-back",
                optionId,
                previousValue,
                nextValue: value,
                reason: rollbackError ? `${reason}; compensation: ${rollbackReason}` : reason,
              });
            }
          });
          const terminalPersisted = await persistSessionNowOrReport(sessionId, "trạng thái hoàn tác cấu hình", {
            fatal: true,
            strict: true,
          });
          if (!terminalPersisted) {
            await revokeRuntimeAfterDurabilityFailure(sessionId, provider);
          }
          releaseControlLock();
          return;
        }
        set((state) => {
          const current = state.sessions[sessionId];
          if (!current)
            return;
          const control = current.controls.find((candidate) => candidate.id === optionId);
          if (control)
            control.currentValue = value;
          appendOwnedSessionEvent(current, "model", {
            type: "control-change",
            phase: "committed",
            optionId,
            previousValue,
            nextValue: value,
          });
        });
        try {
          await persistSessionBeforeDispatch(get().sessions[sessionId]);
          releaseControlLock();
        }
        catch (commitError) {
          let rollbackError: unknown;
          try {
            const rollbackDriver = runtimes.requireInstance(sessionId, provider.instanceId, "session-config");
            await rollbackDriver.setConfigOption(optionId, previousValue);
            runtimes.requireInstance(sessionId, provider.instanceId, "session-config");
          }
          catch (error) {
            rollbackError = error;
          }
          const reason = commitError instanceof Error ? commitError.message : String(commitError);
          const rollbackReason = rollbackError instanceof Error ? rollbackError.message : String(rollbackError ?? "");
          const revocation = rollbackError
            ? await detachInstanceForRecovery(sessionId, provider)
            : null;
          set((state) => {
            const current = state.sessions[sessionId];
            if (!current)
              return;
            const ownsControlLock = current.pendingControlId === optionId;
            const control = current.controls.find((candidate) => candidate.id === optionId);
            if (!rollbackError && ownsControlLock && control) {
              control.currentValue = previousValue;
            }
            if (revocation) {
              if (current.runtime?.instanceId === revocation.provider.instanceId) {
                current.runtime = null;
                current.executionProjection = undefined;
              }
              appendRuntimeCleanupFact(current, revocation.provider, "config-uncertain", runtimeDisposalOutcome(revocation));
            }
            if (ownsControlLock) {
              const lifecycleAlreadyClosed = current.status === "stopping" || current.status === "exited";
              if (rollbackError && revocation) {
                current.status = revocation.cleanupFailed ? "error" : "exited";
              }
              else if (rollbackError && !lifecycleAlreadyClosed) {
                current.status = "error";
              }
              if (!(rollbackError && !revocation && lifecycleAlreadyClosed)) {
                current.statusDetail = rollbackError
                  ? revocation
                    ? revocation.cleanupFailed
                      ? `Cấu hình không xác định; runtime đã bị thu hồi nhưng cleanup báo lỗi: ${cleanupFailureReason(revocation.error)}`
                      : `Cấu hình không xác định sau lỗi "${rollbackReason}"; runtime đã được thu hồi. Nhắn tiếp để khởi động một runtime mới.`
                    : `Không thể xác nhận hoặc hoàn tác cấu hình: ${rollbackReason}`
                  : `Không thể lưu cấu hình; đã hoàn tác: ${reason}`;
              }
            }
            appendOwnedSessionEvent(current, "model", {
              type: "control-change",
              phase: rollbackError ? "rollback-failed" : "rolled-back",
              optionId,
              previousValue,
              nextValue: value,
              reason: rollbackError ? `${reason}; compensation: ${rollbackReason}` : reason,
            });
          });
          const terminalPersisted = await persistSessionNowOrReport(sessionId, "trạng thái hoàn tác cấu hình", {
            fatal: true,
            strict: true,
          });
          if (!terminalPersisted) {
            await revokeRuntimeAfterDurabilityFailure(sessionId, provider);
          }
          releaseControlLock();
        }
      }
      finally {
        releaseOperation();
      }
    }
  };
}
