/** Prompt admission, resume, durable staging, and provider invocation. */
import type { DriverFactory } from "./session-store-types";
import { isNekoTaskScopeMapping, beginNekoTaskLoad } from "../task-scope-mapping";
import { nativeRunBlocksRespawn } from "./session-native-recovery";
import { persistSessionStrict, persistSessionBeforeDispatch } from "../persistence";
import { useNekoAgentStore } from "./neko-agent-store";
import type { DriverEvent } from "../drivers/types";
import { appendRuntimeCleanupFact } from "./session-runtime-facts";
import { appendOwnedSessionEvent, removeEventById } from "./session-projections";
import type { KnowledgeContext } from "@/workbench/knowledge";
import { useKnowledgeConnectionStore, buildKnowledgeAugmentedPrompt } from "@/workbench/knowledge";
import { v4 as uuidv4 } from "uuid";
import type { NekoSessionEvent } from "../session-events";
import type { SessionSet, SessionGet, NekoSessionState } from "./session-store-types";
import type { SessionRuntime } from "./session-runtime-lifecycle";
import { AcpRpcError } from "../drivers/acp/errors";
import { getStoppedPrompt } from "../session-control-status";
export function createSessionPromptActions(set: SessionSet, get: SessionGet, runtime: SessionRuntime): Pick<NekoSessionState, "sendPrompt" | "sendPromptToSession"> {
  const { runtimes, acquireHold, runtimeOperations, retainTaskAdmissionFailure, defaultDriverFactory, taskAdmissionLaunch, assertScopedRuntimeAdmitted, persistSessionNowOrReport, dispatchBarriers, observeInvocationAfterMarker } = runtime;
  return {
    sendPrompt: async (text, onAccepted) => {
      const sessionId = get().activeSessionId;
      if (sessionId)
        await get().sendPromptToSession(sessionId, text, onAccepted);
    },
    sendPromptToSession: async (sessionId, text, onAccepted, stillAuthorized, retryOfPromptEventId) => {
      // Capture the intended session before any asynchronous launch/binding work.
      // Navigation must never redirect an already explicit user submission.
      const activeModeExit = runtime.modeExitOperation;
      if (activeModeExit)
        await activeModeExit;
      const session = get().sessions[sessionId];
      // "exited" accepts a new prompt: a restored (or crashed) session
      // respawns a FRESH agent process (spec US3-2 / edge case restart).
      if (!session ||
        (session.status !== "idle" && session.status !== "exited") ||
        session.pendingControlId ||
        session.pendingPermission ||
        session.resolvingPermissionId ||
        session.closePending ||
        session.deletePending) {
        return;
      }
      let retryOfMessageId: string | undefined;
      if (retryOfPromptEventId !== undefined) {
        const stopped = getStoppedPrompt(session);
        const input = session.events.find(({ eventId }) => eventId === retryOfPromptEventId)?.data;
        if (stopped?.eventId !== retryOfPromptEventId || stopped.text !== text
          || input?.type !== "model-input"
          || !session.messages.some(message => message.id === input.messageId && message.role === "user" && message.text === text)) return;
        retryOfMessageId = input.messageId;
      }
      if (session.taskScope && (!isNekoTaskScopeMapping(session.taskScope)
        || session.taskScope.state === "recovery-required" || session.taskScope.state === "pending-new"
        || (runtimes.get(sessionId) && session.taskScope.state !== "bound"))) {
        set((state) => {
          const current = state.sessions[sessionId];
          if (current) {
            current.status = "error";
            current.statusDetail = "Tác vụ Neko chưa có admission an toàn. Không gửi lại prompt; cần đối soát liên kết đã lưu.";
          }
        });
        return;
      }
      if (+!runtimes.get(sessionId) &&
        !runtimes.hasRetainedCleanup(sessionId) &&
        nativeRunBlocksRespawn(session)) {
        set((state) => {
          const current = state.sessions[sessionId];
          if (!current)
            return;
          current.status = "error";
          current.statusDetail =
            "Lần chạy native trước chưa có kết quả an toàn để chạy lại. Hãy khởi động lại Wiii để đối soát journal hoặc kiểm tra thủ công.";
        });
        return;
      }
      if (!session.workspace) {
        set((state) => {
          const current = state.sessions[sessionId];
          if (current) {
            current.statusDetail = "Hãy gắn một thư mục dự án trước khi nhắn tiếp.";
          }
        });
        return;
      }
      const releaseOperation = acquireHold(runtimeOperations, sessionId);
      try {
        let provider = runtimes.get(sessionId);
        if (!provider) {
          const savedScope = get().sessions[sessionId]?.taskScope;
          if (savedScope && isNekoTaskScopeMapping(savedScope)) {
            set((state) => {
              const current = state.sessions[sessionId];
              current.taskScope = beginNekoTaskLoad(savedScope);
              // Acquire the one-request lock before the durable load intent.
              current.status = "connecting";
            });
            try {
              await persistSessionStrict(get().sessions[sessionId]);
            }
            catch (error) {
              await retainTaskAdmissionFailure(sessionId, error);
              set((state) => {
                const s = state.sessions[sessionId]; if (s) {
                  s.status = "error";
                  s.statusDetail = "Không thể lưu ý định tiếp tục tác vụ Neko. Chưa khởi động agent.";
                }
              });
              return;
            }
          }
          const beforeStart = get().sessions[sessionId];
          if (!beforeStart || beforeStart.closePending || beforeStart.deletePending
            || (savedScope && beforeStart.status !== "connecting"))
            return;
          set((state) => {
            const current = state.sessions[sessionId];
            if (current)
              current.status = "connecting";
          });
          const agentStore = useNekoAgentStore.getState();
          if (!agentStore.agents.some((agent) => agent.id === session.agentId))
            await agentStore.detect(session.agentId);
          const checked = useNekoAgentStore.getState();
          const agent = checked.agents.find((a) => a.id === session.agentId);
          if (checked.error || (checked.isLoading && checked.probeStates[session.agentId] !== "ready")
            || !agent?.found || agent.availability !== "available") {
            set((state) => {
              const s = state.sessions[sessionId];
              if (s?.status === "connecting") {
                s.status = "error";
                s.statusDetail = `Chưa xác nhận được ${session.agentName} sẵn sàng. Hãy kiểm tra tại Tổng quan → Quản lý harness rồi thử lại.`;
              }
            });
            return;
          }
          try {
            const factory: DriverFactory = (get() as unknown as {
              _driverFactory?: DriverFactory;
            })._driverFactory ?? defaultDriverFactory;
            if (get().sessions[sessionId]?.status !== "connecting")
              return;
            const pendingEvents: DriverEvent[] = [];
            let preparingRuntime = true;
            const replacement = await runtimes.replace(sessionId, agent.id, (instanceId, ownDriver) => factory(agent, sessionId, {
              workspace: session.workspace!,
              projectId: session.projectId ?? null,
              ...(session.execution ? { execution: session.execution } : {}),
              executionId: instanceId,
              ...(session.launchProfile?.id ? { profileId: session.launchProfile.id } : {}),
              backendSessionId: session.backendSessionId,
              ...taskAdmissionLaunch(sessionId, instanceId),
            }, (event) => {
              if (event.sessionId !== sessionId)
                return;
              if (preparingRuntime)
                pendingEvents.push(event);
              else if (runtimes.isCurrent(sessionId, instanceId))
                get().handleEvent(event);
            }, ownDriver));
            await assertScopedRuntimeAdmitted(sessionId, replacement.current);
            provider = replacement.current;
            set((state) => {
              const s = state.sessions[sessionId];
              if (s) {
                if (replacement.previous && !replacement.cleanupFailed) {
                  appendRuntimeCleanupFact(s, replacement.previous, "replacement", { failed: false });
                }
                s.runtime = replacement.current;
                s.executionProjection = undefined;
                s.backendSessionId = replacement.current.backendSessionId;
                appendOwnedSessionEvent(s, "runtime", {
                  type: "runtime-attached",
                  provider: replacement.current,
                });
                s.status = "idle";
                s.statusDetail = undefined;
              }
            });
            preparingRuntime = false;
            for (const event of pendingEvents) {
              if (event.sessionId === sessionId && runtimes.isCurrent(sessionId, replacement.current.instanceId)) {
                get().handleEvent(event);
              }
            }
          }
          catch (err) {
            await retainTaskAdmissionFailure(sessionId, err);
            const reason = err instanceof Error ? err.message : String(err);
            set((state) => {
              const s = state.sessions[sessionId];
              const writerRecovery = Boolean(s && s.agentId === "neko" && !s.runtime && !s.closePending && !s.deletePending
                && err instanceof AcpRpcError && err.sessionRecovery === "writer-locked");
              if (s && (s.status === "connecting" || writerRecovery)) {
                s.status = "error";
                s.statusDetail = reason;
                if (writerRecovery) s.nativeRecoveryRequired = true;
                appendOwnedSessionEvent(s, "runtime", {
                  type: "runtime-attach-failed",
                  providerId: s.agentId,
                  reason,
                });
              }
            });
            await persistSessionNowOrReport(sessionId, "lỗi khởi động runtime");
            return;
          }
        }
        if (!provider)
          return;
        const providerInstanceId = provider.instanceId;
        // Acquire the turn before optional remote retrieval. Otherwise a slow
        // knowledge request could let a second composer submission pass.
        set((state) => {
          const current = state.sessions[sessionId];
          if (current)
            current.status = "dispatching";
        });
        let knowledgeContext: KnowledgeContext | null = null;
        let modelPrompt = text;
        // Fixed task context is owned by Neko. Shared Wiii Knowledge is not
        // silently admitted across this boundary; other/legacy lanes keep it.
        if (!get().sessions[sessionId]?.taskScope && useKnowledgeConnectionStore.getState().status === "ready") {
          try {
            knowledgeContext = await useKnowledgeConnectionStore.getState().retrieve(text);
            modelPrompt = buildKnowledgeAugmentedPrompt(text, knowledgeContext);
          }
          catch (error) {
            // Retrieval is an independent capability. A degraded knowledge
            // connection must remain visible but must not disable local work.
            set((state) => {
              const current = state.sessions[sessionId];
              if (current) {
                current.statusDetail = `Wiii Knowledge tạm không dùng được; agent tiếp tục không có RAG: ${error instanceof Error ? error.message : String(error)}`;
              }
            });
          }
        }
        // Runtime admission and Knowledge retrieval can await. Recheck queued
        // intent against the now-live model/root before making it dispatchable.
        if (stillAuthorized && !stillAuthorized()) {
          set(state => {
            const current = state.sessions[sessionId]; if (current)
              current.statusDetail = "Ngữ cảnh hoặc model đã thay đổi. Tin chờ chưa được gửi.";
          });
          return;
        }
        const messageId = uuidv4();
        const previousTitle = get().sessions[sessionId]?.title;
        let inputEventId: string | null = null;
        let knowledgeEventId: string | null = null;
        set((state) => {
          const s = state.sessions[sessionId];
          if (!s)
            return;
          s.messages.push({ id: messageId, role: "user", text, ...(retryOfMessageId ? { retryOfMessageId } : {}) });
          inputEventId = appendOwnedSessionEvent(s, "model", {
            type: "model-input",
            source: "live",
            messageId,
            text,
            providerInstanceId,
            delivery: "staged",
          }).eventId!;
          if (knowledgeContext) {
            knowledgeEventId = appendOwnedSessionEvent(s, "model", {
              type: "knowledge-context",
              source: "wiii-knowledge",
              contextId: knowledgeContext.contextId,
              query: knowledgeContext.query,
              renderedContext: knowledgeContext.renderedContext,
              sources: knowledgeContext.sources.map((source) => ({
                sourceId: source.sourceId,
                title: source.title,
                documentId: source.documentId,
                pageNumber: source.pageNumber,
                score: source.score,
              })),
              providerInstanceId,
              delivery: "staged",
            }).eventId!;
          }
          // Acquire the turn synchronously. No second composer submission may
          // pass while the first prompt waits for its durability barrier.
          s.status = "dispatching";
          s.lastActivityAt = Date.now();
          s.updatedAt = s.lastActivityAt;
          // Work owns its title; a full prompt may also contain criteria.
          if (!s.execution && s.messages.length === 1) {
            s.title = text.length > 48 ? `${text.slice(0, 48)}…` : text;
          }
        });
        const updated = get().sessions[sessionId];
        if (!updated)
          return;
        const releaseDispatchBarrier = acquireHold(dispatchBarriers, sessionId);
        try {
          // Hard barrier: the provider cannot observe this prompt before the
          // exact model input is durable in the append-only log.
          await persistSessionBeforeDispatch(updated);
        }
        catch (error) {
          set((state) => {
            const current = state.sessions[sessionId];
            if (current) {
              current.messages = current.messages.filter((message) => message.id !== messageId);
              removeEventById(current.events as NekoSessionEvent[], inputEventId);
              removeEventById(current.events as NekoSessionEvent[], knowledgeEventId);
              if (current.messages.length === 0 && previousTitle) {
                current.title = previousTitle;
              }
              if (current.status === "dispatching")
                current.status = "idle";
              current.statusDetail = `Không thể lưu prompt nên chưa gửi cho agent: ${error instanceof Error ? error.message : String(error)}`;
            }
          });
          return;
        }
        finally {
          releaseDispatchBarrier();
        }
        // turn-started from the driver flips status + opens the assistant
        // message; prompt() resolves only when the whole turn ends.
        let promptStarted = false;
        try {
          const driver = runtimes.requireInstance(sessionId, providerInstanceId, "prompt");
          const invocation = driver.prompt(modelPrompt, { promptEventId: inputEventId! });
          promptStarted = true;
          onAccepted?.();
          set((state) => {
            const current = state.sessions[sessionId];
            if (current && inputEventId) {
              appendOwnedSessionEvent(current, "model", {
                type: "dispatch-invoked",
                targetEventId: inputEventId,
                action: "prompt",
                providerInstanceId,
              });
              if (knowledgeEventId) {
                appendOwnedSessionEvent(current, "model", {
                  type: "dispatch-invoked",
                  targetEventId: knowledgeEventId,
                  action: "knowledge",
                  providerInstanceId,
                });
              }
            }
          });
          const persistInvocation = persistSessionNowOrReport(sessionId, "xác nhận dispatch prompt", {
            strict: true,
          });
          const outcome = await observeInvocationAfterMarker(sessionId, provider, invocation, persistInvocation);
          if (!outcome.markerPersisted)
            return;
          if (outcome.invocationFailed)
            throw outcome.error;
          set((state) => {
            const current = state.sessions[sessionId];
            // Some drivers only resolve prompt() and do not emit lifecycle
            // events. Release the local dispatch lock in that valid case.
            if (current?.status === "dispatching")
              current.status = "idle";
          });
        }
        catch (error) {
          let rolledBackUndispatchedInput = false;
          set((state) => {
            const current = state.sessions[sessionId];
            if (!current)
              return;
            if (!promptStarted) {
              current.messages = current.messages.filter((message) => message.id !== messageId);
              removeEventById(current.events as NekoSessionEvent[], inputEventId);
              removeEventById(current.events as NekoSessionEvent[], knowledgeEventId);
              if (current.messages.length === 0 && previousTitle) {
                current.title = previousTitle;
              }
              rolledBackUndispatchedInput = true;
            }
            if (current?.status === "dispatching") {
              current.status = promptStarted ? "error" : "idle";
              current.statusDetail = error instanceof Error ? error.message : String(error);
            }
          });
          if (rolledBackUndispatchedInput) {
            await persistSessionNowOrReport(sessionId, "rollback prompt chưa gửi", {
              fatal: true,
              strict: true,
            });
          }
        }
      }
      finally {
        releaseOperation();
      }
    }
  };
}
