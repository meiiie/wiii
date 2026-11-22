/** Single owner for live runtimes, operation holds, durability failures, and mode-exit cleanup. */
import { RuntimeRegistry } from "../runtime-manager";
import { original } from "immer";
import type { NativeControlReader, NekoSession } from "./session-store-types";
import { getNekoControlClient } from "@/neko/control-client";
import type { NekoSessionOwnershipFact } from "@/neko/session-ownership";
import { topLevelKind } from "./session-native-recovery";
import type { DriverLaunchConfig } from "../drivers/factory";
import { isNekoTaskScopeMapping, bindNekoTaskMapping, markNekoTaskRecovery } from "../task-scope-mapping";
import type { NekoTaskReceipt } from "../drivers/acp/task-protocol";
import type { NekoTaskScopeMapping } from "../task-scope-mapping";
import { persistSessionStrict, persistSessionNow } from "../persistence";
import type { RuntimeProviderSnapshot, RuntimeDisposalResult } from "../runtime-manager";
import { AcpRpcError } from "../drivers/acp/errors";
import type { DetectedAgent } from "./neko-agent-store";
import type { DriverEvent, Driver } from "../drivers/types";
import { appendRuntimeCleanupFact, runtimeDisposalOutcome, cleanupFailureReason, observeRuntimeCleanup } from "./session-runtime-facts";
import type { RuntimeCleanupOutcome } from "./session-runtime-facts";
import type { SessionStoreApi } from "./session-store-types";
import type { SessionPresentation } from "./session-presentation";
export function createSessionRuntime(getStore: () => SessionStoreApi, presentation: SessionPresentation) {
  const { discardPresentationStreams } = presentation;
  /** Live runtimes stay outside Zustand but are owned by RuntimeRegistry. */
  const runtimes = new RuntimeRegistry();
  const closeOperations = new Map<string, Promise<void>>();
  const dispatchBarriers = new Map<string, Set<Promise<void>>>();
  const runtimeOperations = new Map<string, Set<Promise<void>>>();
  let modeExitOperation: Promise<void> | null = null;
  let nativeControlReaderFactory: () => NativeControlReader = getNekoControlClient;
  // Read the current injected authority at call time, preserving its free-call contract.
  function readNativeControl(): NativeControlReader {
    return nativeControlReaderFactory();
  }
  function acquireHold(registry: Map<string, Set<Promise<void>>>, sessionId: string): () => void {
    let resolve!: () => void;
    const hold = new Promise<void>((done) => {
      resolve = done;
    });
    const holds = registry.get(sessionId) ?? new Set<Promise<void>>();
    holds.add(hold);
    registry.set(sessionId, holds);
    let released = false;
    return () => {
      if (released)
        return;
      released = true;
      holds.delete(hold);
      if (holds.size === 0)
        registry.delete(sessionId);
      resolve();
    };
  }
  async function waitForHolds(registry: Map<string, Set<Promise<void>>>, sessionId: string): Promise<void> {
    while (registry.get(sessionId)?.size) {
      await Promise.allSettled([...(registry.get(sessionId) ?? [])]);
    }
  }
  function ownershipFact(session: Pick<NekoSession, "id" | "agentId" | "kind" | "projectId" | "execution" | "status"> & Partial<Pick<NekoSession, "runtime" | "closePending" | "deletePending">>): NekoSessionOwnershipFact {
    const kind = topLevelKind(session);
    return {
      sessionId: session.id,
      providerId: session.agentId,
      kind,
      projectId: session.projectId ?? null,
      taskId: kind === "worker" ? session.execution?.taskId ?? null : null,
      runId: kind === "worker" ? session.execution?.runId ?? null : null,
      active: Boolean(session.runtime || session.closePending || session.deletePending)
        || runtimes.get(session.id) !== null
        || runtimes.hasRetainedCleanup(session.id)
        || (session.status !== "exited" && session.status !== "error"),
    };
  }
  function taskAdmissionLaunch(sessionId: string, instanceId: string): Partial<DriverLaunchConfig> {
    const initial = getStore().getState().sessions[sessionId];
    if (!initial?.taskScope)
      return {};
    if (initial.closePending || initial.deletePending
      || !runtimes.isCurrentOrPreparing(sessionId, instanceId))
      throw new Error("Phiên tác vụ đang đóng; chưa khởi động lại agent.");
    const scope = initial.taskScope;
    if (!isNekoTaskScopeMapping(scope) || (scope.state !== "pending-new" && scope.state !== "pending-load")) {
      throw new Error("Liên kết tác vụ Neko chưa sẵn sàng để admission.");
    }
    let admitted: NekoTaskReceipt | null = null;
    let admittedBackendId: string | null = null;
    const stillPreparing = () => {
      const current = getStore().getState().sessions[sessionId];
      if (!current || current.closePending || current.deletePending
        || !runtimes.isCurrentOrPreparing(sessionId, instanceId)
        || !current.taskScope || !isNekoTaskScopeMapping(current.taskScope)
        || current.taskScope.threadId !== scope.threadId
        || current.taskScope.execution.taskId !== scope.execution.taskId
        || current.taskScope.execution.runId !== scope.execution.runId
        || current.taskScope.execution.environmentId !== scope.execution.environmentId
        || current.taskScope.projectId !== scope.projectId
        || current.taskScope.workspacePath !== scope.workspacePath
        || current.workspace?.path !== scope.workspacePath
        || (current.projectId ?? null) !== scope.projectId
        || current.execution?.taskId !== scope.execution.taskId
        || current.execution.runId !== scope.execution.runId
        || current.execution.environmentId !== scope.execution.environmentId) {
        throw new Error("Admission tác vụ Neko đã hết hiệu lực theo phiên/process hiện tại.");
      }
      return current;
    };
    return {
      taskScope: { label: scope.label, ...(scope.receipt ? { receipt: scope.receipt } : {}) },
      onTaskAdmitted: async (backendSessionId, receipt, authorizedCanonicalRoot) => {
        const current = stillPreparing();
        const bound = bindNekoTaskMapping(current.taskScope as NekoTaskScopeMapping, receipt, backendSessionId, authorizedCanonicalRoot);
        admitted = receipt;
        admittedBackendId = backendSessionId;
        getStore().setState((state) => {
          const s = state.sessions[sessionId];
          s.taskScope = bound;
          s.backendSessionId = backendSessionId;
        });
        try {
          await persistSessionStrict(getStore().getState().sessions[sessionId]);
          const after = stillPreparing();
          if (!isNekoTaskScopeMapping(after.taskScope) || after.taskScope.state !== "bound"
            || after.taskScope.receipt.activationId !== receipt.activationId)
            throw new Error("Receipt tác vụ Neko đã thay đổi trong khi lưu.");
        }
        catch (error) {
          getStore().setState((state) => {
            const s = state.sessions[sessionId];
            if (s?.taskScope && isNekoTaskScopeMapping(s.taskScope)
              && s.taskScope.receipt?.activationId === receipt.activationId) {
              s.taskScope = markNekoTaskRecovery(s.taskScope, "receipt-persistence-failed");
            }
          });
          throw error;
        }
      },
      onTaskCloseOutcome: async (outcome) => {
        if (outcome !== "uncertain" || !admitted || !admittedBackendId)
          return;
        const s = getStore().getState().sessions[sessionId];
        if (!s?.taskScope || !isNekoTaskScopeMapping(s.taskScope)
          || s.taskScope.backendSessionId !== admittedBackendId
          || s.taskScope.receipt?.activationId !== admitted.activationId)
          return;
        getStore().setState((state) => {
          const current = state.sessions[sessionId];
          current.taskScope = markNekoTaskRecovery(s.taskScope as NekoTaskScopeMapping, "close-unconfirmed");
          current.statusDetail = "Chưa xác nhận Neko đã đóng tác vụ. Giữ receipt; không tự chạy lại hoặc xóa writer lock.";
        });
        await persistSessionStrict(getStore().getState().sessions[sessionId]);
      },
    };
  }
  async function assertScopedRuntimeAdmitted(sessionId: string, provider: RuntimeProviderSnapshot): Promise<void> {
    const session = getStore().getState().sessions[sessionId];
    if (!session?.taskScope)
      return;
    if (isNekoTaskScopeMapping(session.taskScope) && session.taskScope.state === "bound"
      && session.backendSessionId === provider.backendSessionId
      && session.taskScope.backendSessionId === provider.backendSessionId)
      return;
    await runtimes.detachInstance(sessionId, provider.instanceId);
    throw new Error("Agent chưa trả receipt đã lưu bền. Tác vụ chưa được admission.");
  }
  function taskRecoveryKind(error: unknown): "writer-unavailable" | "recovery-required" | undefined {
    if (error instanceof AcpRpcError && error.taskRecovery)
      return error.taskRecovery.kind === "writer_unavailable" ? "writer-unavailable" : "recovery-required";
    if (error instanceof AggregateError) {
      for (const child of error.errors) {
        const kind = taskRecoveryKind(child);
        if (kind)
          return kind;
      }
    }
    return undefined;
  }
  async function retainTaskAdmissionFailure(sessionId: string, error: unknown): Promise<void> {
    const s = getStore().getState().sessions[sessionId];
    if (!s?.taskScope || !isNekoTaskScopeMapping(s.taskScope))
      return;
    const reason = taskRecoveryKind(error) ?? (s.taskScope.state === "pending-load" ? "load-response-uncertain" : "new-response-uncertain");
    getStore().setState((state) => {
      const current = state.sessions[sessionId];
      if (current?.taskScope && isNekoTaskScopeMapping(current.taskScope) && current.taskScope.state !== "recovery-required") {
        current.taskScope = markNekoTaskRecovery(current.taskScope, reason);
      }
    });
  }
  async function defaultDriverFactory(agent: DetectedAgent, sessionId: string, launch: DriverLaunchConfig, onEvent: (event: DriverEvent) => void, ownDriver: (driver: Driver) => void): Promise<Driver> {
    const { createDriverForAgent } = await import("../drivers/factory");
    return createDriverForAgent(agent, sessionId, launch, onEvent, ownDriver);
  }
  async function revokeRuntimeAfterDurabilityFailure(sessionId: string, provider: RuntimeProviderSnapshot): Promise<void> {
    const revocation = await detachInstanceForRecovery(sessionId, provider);
    let terminalDetail: string | null = null;
    if (revocation) {
      getStore().setState((state) => {
        const current = state.sessions[sessionId];
        if (!current)
          return;
        if (current.runtime?.instanceId === revocation.provider.instanceId) {
          current.runtime = null;
          current.executionProjection = undefined;
        }
        appendRuntimeCleanupFact(current, revocation.provider, "durability-failure", runtimeDisposalOutcome(revocation));
        if (current.status !== "stopping") {
          current.status = revocation.cleanupFailed ? "error" : "exited";
          terminalDetail = revocation.cleanupFailed
            ? `Không thể lưu kết quả giao dịch; runtime đã bị thu hồi nhưng cleanup báo lỗi: ${cleanupFailureReason(revocation.error)}`
            : "Không thể lưu kết quả giao dịch; runtime đã được thu hồi. Nhắn tiếp để thử lại khi bộ nhớ bền đã sẵn sàng.";
          current.statusDetail = terminalDetail;
        }
      });
    }
    // The original boundary write may have failed transiently. Retry once with
    // the terminal revocation included; if storage is still unavailable, the
    // earlier durable staged record remains non-authoritative on hydration.
    const terminalPersisted = await persistSessionNowOrReport(sessionId, "trạng thái thu hồi sau lỗi độ bền", {
      fatal: true,
      strict: true,
    });
    if (!terminalPersisted && terminalDetail) {
      getStore().setState((state) => {
        const current = state.sessions[sessionId];
        if (current) {
          current.statusDetail = `${terminalDetail} Bản ghi kết thúc vẫn chưa thể lưu bền.`;
        }
      });
    }
  }
  async function observeInvocationAfterMarker(sessionId: string, provider: RuntimeProviderSnapshot, invocation: Promise<void>, markerPersistence: Promise<boolean>): Promise<{
    markerPersisted: false;
    invocationFailed: false;
  } | {
    markerPersisted: true;
    invocationFailed: false;
  } | {
    markerPersisted: true;
    invocationFailed: true;
    error: unknown;
  }> {
    // Attach both handlers before waiting on storage so a provider rejection can
    // never become unobserved while the marker write is in flight.
    const invocationOutcome = invocation.then(() => ({ failed: false as const }), (error) => ({ failed: true as const, error }));
    const markerPersisted = await markerPersistence;
    if (!markerPersisted) {
      // detachInstance revokes the registry binding synchronously before cleanup
      // waits, so a long-running prompt cannot keep dispatching tools after the
      // audit boundary has failed.
      await revokeRuntimeAfterDurabilityFailure(sessionId, provider);
      return { markerPersisted: false, invocationFailed: false };
    }
    const outcome = await invocationOutcome;
    return outcome.failed
      ? { markerPersisted: true, invocationFailed: true, error: outcome.error }
      : { markerPersisted: true, invocationFailed: false };
  }
  async function detachInstanceForRecovery(sessionId: string, provider: RuntimeProviderSnapshot): Promise<RuntimeDisposalResult | null> {
    try {
      return await runtimes.detachInstance(sessionId, provider.instanceId);
    }
    catch (error) {
      // The provider may already be synchronously revoked while its joined
      // cleanup is still failing. Preserve the captured identity so config
      // recovery can finish its state transition and strict terminal persist.
      return { provider, cleanupFailed: true, error };
    }
  }
  async function persistSessionNowOrReport(sessionId: string, context: string, options: {
    fatal?: boolean;
    strict?: boolean;
  } = {}): Promise<boolean> {
    const prior = getStore().getState().sessions[sessionId];
    if (prior?.taskScope && (!isNekoTaskScopeMapping(prior.taskScope) || prior.taskScope.state === "recovery-required")) {
      getStore().setState((state) => {
        const current = state.sessions[sessionId];
        if (!current)
          return;
        const prefix = "Liên kết tác vụ Neko cần đối soát; giữ receipt, không tự khởi động lại hoặc gửi lại prompt.";
        const diagnostic = current.status === "error" && current.statusDetail && !current.statusDetail.startsWith(prefix)
          ? ` ${current.statusDetail}` : "";
        current.status = "error";
        current.statusDetail = prefix + diagnostic;
      });
    }
    const session = getStore().getState().sessions[sessionId];
    if (!session)
      return false;
    try {
      await (options.strict ? persistSessionStrict(session) : persistSessionNow(session));
      const failure = session.persistenceFailure;
      if (failure?.context === context) {
        getStore().setState((state) => {
          const current = state.sessions[sessionId];
          if (!current?.persistenceFailure || original(current.persistenceFailure) !== failure) return;
          if (current.statusDetail === failure.detail) current.statusDetail = undefined;
          current.persistenceFailure = undefined;
        });
      }
      return true;
    }
    catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      getStore().setState((state) => {
        const current = state.sessions[sessionId];
        if (!current)
          return;
        if (options.fatal && current.status !== "stopping" && current.status !== "exited") {
          current.status = "error";
        }
        const detail = `Không thể lưu ${context}: ${reason}`;
        current.persistenceFailure = { context, detail };
        current.statusDetail = detail;
      });
      return false;
    }
  }
  // ---------------------------------------------------------------------------
  // Idle reap (T601, FR-009 — waku's lesson, reimplemented)
  // ---------------------------------------------------------------------------
  const IDLE_REAP_MS = 30 * 60 * 1000;
  const SWEEP_INTERVAL_MS = 5 * 60 * 1000;
  let reaperTimer: ReturnType<typeof setInterval> | null = null;
  /**
   * Dispose runtimes of sessions idle past the threshold. Never touches a
   * streaming turn or an unanswered permission request (the sweep may run
   * while the user reads an approval — reaping there would fail their turn).
   */
  async function sweepIdleSessions(now: number = Date.now()): Promise<void> {
    const { sessions } = getStore().getState();
    for (const session of Object.values(sessions)) {
      if (session.status !== "idle")
        continue;
      if (session.pendingPermission)
        continue;
      if (session.pendingControlId)
        continue;
      if (now - session.lastActivityAt < IDLE_REAP_MS)
        continue;
      const provider = runtimes.get(session.id);
      if (!provider)
        continue;
      getStore().setState((state) => {
        const current = state.sessions[session.id];
        if (current?.status === "idle")
          current.status = "connecting";
      });
      const cleanup = await observeRuntimeCleanup(runtimes.detach(session.id));
      getStore().setState((state) => {
        const s = state.sessions[session.id];
        if (s && s.status === "connecting") {
          s.runtime = null;
          s.executionProjection = undefined;
          appendRuntimeCleanupFact(s, provider, "idle", cleanup, now);
          s.status = cleanup.failed ? "error" : "exited";
          s.statusDetail = "Agent tạm nghỉ sau 30 phút yên lặng — nhắn tiếp để khởi động lại.";
          if (cleanup.failed) {
            s.statusDetail = "Runtime hết hạn nhưng báo lỗi khi thu hồi tài nguyên.";
          }
          s.updatedAt = now;
          s.lastActivityAt = now;
        }
      });
      await persistSessionNowOrReport(session.id, "trạng thái runtime hết hạn", {
        fatal: cleanup.failed,
        strict: cleanup.failed,
      });
    }
  }
  /** Start the periodic sweep and return its explicit owner/disposer. */
  function startIdleReaper(): () => void {
    stopIdleReaper();
    reaperTimer = setInterval(() => void sweepIdleSessions(), SWEEP_INTERVAL_MS);
    return stopIdleReaper;
  }
  function stopIdleReaper(): void {
    if (!reaperTimer)
      return;
    clearInterval(reaperTimer);
    reaperTimer = null;
  }
  /** Mode-exit owner: stop every live runtime and persist detach facts. */
  async function disposeAllNekoRuntimes(): Promise<void> {
    if (modeExitOperation)
      return modeExitOperation;
    const state = getStore().getState();
    const nativeControl = nativeControlReaderFactory();
    const unresolvedStartSessionIds = new Set(nativeControl.unresolvedStartSessionIds());
    const sessionIds = new Set([
      ...runtimes.ownedSessionIds(),
      ...dispatchBarriers.keys(),
      ...runtimeOperations.keys(),
      ...closeOperations.keys(),
      ...unresolvedStartSessionIds,
      ...Object.values(state.sessions)
        .filter((session) => session.runtime !== null || session.status === "connecting")
        .map((session) => session.id),
    ]);
    const priorLifecycleOperations = [...sessionIds]
      .map((sessionId) => closeOperations.get(sessionId))
      .filter((operation): operation is Promise<void> => Boolean(operation));
    getStore().setState((draft) => {
      for (const sessionId of sessionIds) {
        const session = draft.sessions[sessionId];
        if (!session || session.deletePending)
          continue;
        session.closePending = true;
        session.status = "stopping";
      }
    });
    const operation = (async () => {
      await Promise.allSettled(priorLifecycleOperations);
      await Promise.all([...sessionIds].map((sessionId) => waitForHolds(dispatchBarriers, sessionId)));
      const results = await runtimes.disposeAll();
      await Promise.all([...sessionIds].map((sessionId) => waitForHolds(runtimeOperations, sessionId)));
      // A provider preparation can become unresolved while RuntimeRegistry is
      // joining it. Refresh after every preparation has settled so teardown
      // cannot miss a native start retained after the initial snapshot.
      let durableDiscoveryFailure: unknown;
      try {
        for (const sessionId of await nativeControl.reconcilableStartSessionIds()) {
          unresolvedStartSessionIds.add(sessionId);
          sessionIds.add(sessionId);
        }
      }
      catch (error) {
        // A catalog read is advisory to the identities already retained by this
        // renderer. Continue revoking those known starts, then surface the read
        // failure so mode exit cannot claim complete cleanup.
        durableDiscoveryFailure = error;
      }
      const unresolvedStartFailures = new Map<string, unknown>();
      await Promise.all([...unresolvedStartSessionIds].map(async (sessionId) => {
        try {
          await nativeControl.cancelUnresolvedStarts(sessionId);
        }
        catch (error) {
          unresolvedStartFailures.set(sessionId, error);
        }
      }));
      const resultsBySession = new Map(results.map((result) => [result.sessionId, result] as const));
      const sessionIdsToPersist: string[] = [];
      getStore().setState((draft) => {
        for (const sessionId of sessionIds) {
          const session = draft.sessions[sessionId];
          if (!session || session.deletePending)
            continue;
          const result = resultsBySession.get(sessionId);
          const provider = result?.provider ?? session.runtime;
          const unresolvedStartFailure = unresolvedStartFailures.get(sessionId);
          const runtimeCleanup: RuntimeCleanupOutcome = result
            ? runtimeDisposalOutcome(result)
            : unresolvedStartSessionIds.has(sessionId)
              ? { failed: false }
              : {
                failed: true,
                error: new Error("Runtime không thuộc registry khi rời Neko Chill; cleanup không được quan sát."),
              };
          const cleanup: RuntimeCleanupOutcome = unresolvedStartFailure === undefined
            ? runtimeCleanup
            : { failed: true, error: unresolvedStartFailure };
          session.runtime = null;
          session.executionProjection = undefined;
          session.status = cleanup.failed ? "error" : "exited";
          session.pendingPermission = null;
          session.resolvingPermissionId = null;
          session.cancelPending = false;
          session.updatedAt = Date.now();
          session.statusDetail = cleanup.failed
            ? "Chưa thể đóng phiên an toàn."
            : "Phiên đã dừng.";
          if (provider) {
            appendRuntimeCleanupFact(session, provider, "mode-exit", cleanup);
          }
          sessionIdsToPersist.push(sessionId);
        }
      });
      await Promise.all(sessionIdsToPersist.map(async (sessionId) => {
        const result = resultsBySession.get(sessionId);
        const failed = unresolvedStartFailures.has(sessionId)
          || (result ? result.cleanupFailed : !unresolvedStartSessionIds.has(sessionId));
        await persistSessionNowOrReport(sessionId, "trạng thái rời Neko Chill", {
          fatal: failed,
          strict: failed,
        });
      }));
      const unreportedFailures = [
        ...(durableDiscoveryFailure === undefined ? [] : [durableDiscoveryFailure]),
        ...[...unresolvedStartFailures]
          .filter(([sessionId]) => (durableDiscoveryFailure !== undefined
            || !sessionIdsToPersist.includes(sessionId)))
          .map(([, error]) => error),
      ];
      if (unreportedFailures.length === 1)
        throw unreportedFailures[0];
      if (unreportedFailures.length > 1) {
        throw new AggregateError(unreportedFailures, "Không thể chứng minh toàn bộ runtime đã được thu hồi khi rời Neko Chill.");
      }
    })();
    let tracked!: Promise<void>;
    tracked = operation.finally(() => {
      getStore().setState((draft) => {
        for (const sessionId of sessionIds) {
          const session = draft.sessions[sessionId];
          if (session && closeOperations.get(sessionId) === tracked) {
            session.closePending = false;
          }
        }
      });
      for (const sessionId of sessionIds) {
        if (closeOperations.get(sessionId) === tracked)
          closeOperations.delete(sessionId);
      }
      if (modeExitOperation === tracked)
        modeExitOperation = null;
    });
    for (const sessionId of sessionIds)
      closeOperations.set(sessionId, tracked);
    modeExitOperation = tracked;
    return tracked;
  }
  /** Test hook: replace native journal reads without constructing a Tauri host. */
  function _setNativeControlReaderForTests(factory: (() => NativeControlReader) | undefined): void {
    nativeControlReaderFactory = factory ?? getNekoControlClient;
  }
  /** Test hook: drop live runtimes, simulating an app restart. */
  function _clearLiveDriversForTests(): void {
    discardPresentationStreams();
    runtimes.clearForTests();
    closeOperations.clear();
    dispatchBarriers.clear();
    runtimeOperations.clear();
    modeExitOperation = null;
    stopIdleReaper();
  }
  return {
    acquireHold,
    waitForHolds,
    ownershipFact,
    taskAdmissionLaunch,
    assertScopedRuntimeAdmitted,
    taskRecoveryKind,
    retainTaskAdmissionFailure,
    defaultDriverFactory,
    revokeRuntimeAfterDurabilityFailure,
    observeInvocationAfterMarker,
    detachInstanceForRecovery,
    persistSessionNowOrReport,
    sweepIdleSessions,
    startIdleReaper,
    stopIdleReaper,
    disposeAllNekoRuntimes,
    _setNativeControlReaderForTests,
    _clearLiveDriversForTests,
    runtimes,
    closeOperations,
    dispatchBarriers,
    runtimeOperations,
    ...presentation,
    get modeExitOperation() { return modeExitOperation; },
    readNativeControl,
  };
}
export type SessionRuntime = ReturnType<typeof createSessionRuntime>;
