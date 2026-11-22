/** Provider-event intake and projection into visible session state. */
import { isNekoTaskScopeMapping } from "../task-scope-mapping";
import { normalizeSessionTitle } from "../session-title";
import { canonicalRootsEqual } from "../drivers/acp/task-protocol";
import { v4 as uuidv4 } from "uuid";
import { openAssistant, toToolBlock, appendOwnedSessionEvent, lastBlock } from "./session-projections";
import type {
  ToolExecutionBlockData,
  ThinkingBlockData,
  AnswerBlockData,
} from "@/api/types/content-blocks";
import { providerProcessExitDetail, sessionHasVisibleModelOutput } from "../session-status";
import { useNekoWorkspaceStore } from "./neko-workspace-store";
import { useCompletionNoticeStore } from "./completion-notice-store";
import { persistSessionDebounced } from "../persistence";
import type { SessionSet, SessionGet, NekoSessionState } from "./session-store-types";
import type { SessionRuntime } from "./session-runtime-lifecycle";
export function createSessionEventActions(set: SessionSet, get: SessionGet, runtime: SessionRuntime): Pick<NekoSessionState, "handleEvent" | "persistTurnResult"> {
  const { enqueuePresentationDelta, drainPresentationStreams, runtimes, persistSessionNowOrReport } = runtime;
  return {
    persistTurnResult: async (sessionId) => {
      if (!await persistSessionNowOrReport(sessionId, "lượt trả lời đã kết thúc", { strict: true }))
        throw new Error("Chưa lưu được kết quả lần chạy.");
    },
    handleEvent: (event) => {
      // A terminal from an older prompt must never finish a newer turn, even
      // when both share the same long-lived ACP process. Runtime callbacks
      // additionally retain their existing isCurrent(instance) guard.
      if ((event.type === "turn-started" || event.type === "turn-finished") && event.promptEventId) {
        const session = get().sessions[event.sessionId];
        const input = session && [...session.events].reverse().find(({ data }) => data.type === "model-input"
          && data.source === "live" && data.providerInstanceId === session.runtime?.instanceId);
        if (!input || input.eventId !== event.promptEventId)
          return;
        if (event.type === "turn-finished" && session.events.some(({ data }) => data.type === "turn-terminal"
          && data.promptEventId === event.promptEventId && data.providerInstanceId === session.runtime?.instanceId))
          return;
      }
      if (event.type === "reasoning-delta" || event.type === "answer-delta") {
        enqueuePresentationDelta(event.sessionId, event.type === "answer-delta" ? "answer" : "reasoning", event.text);
        return;
      }
      if (event.type === "turn-started" ||
        event.type === "activity" ||
        event.type === "permission-request" ||
        event.type === "turn-finished" ||
        event.type === "error" ||
        event.type === "process-exited") {
        drainPresentationStreams(event.sessionId);
      }
      const previous = get().sessions[event.sessionId];
      const finishedMessage = previous?.messages[previous.messages.length - 1];
      const completedTurn = event.type === "turn-finished" && event.stopReason === "end_turn"
        && previous?.status === "streaming" && !previous.cancelPending && !previous.closePending
        && !previous.deletePending && finishedMessage?.role === "assistant"
        ? finishedMessage.id : null;
      const exitingProvider = event.type === "process-exited" ? runtimes.get(event.sessionId) : null;
      set((state) => {
        const session = state.sessions[event.sessionId];
        if (!session)
          return;
        session.lastActivityAt = Date.now();
        session.updatedAt = session.lastActivityAt;
        switch (event.type) {
          case "neko-execution-info": {
            const mapping = session.taskScope;
            if (!session.runtime || session.runtime.providerId !== "neko"
              || session.closePending || session.deletePending || !mapping
              || !isNekoTaskScopeMapping(mapping) || mapping.state !== "bound"
              || event.backendSessionId !== session.runtime.backendSessionId
              || event.backendSessionId !== mapping.backendSessionId)
              return;
            const value = event.projection;
            const matches = value.status !== "reported" || (value.taskId === mapping.receipt.id
              && canonicalRootsEqual(value.root, mapping.receipt.root)
              && value.activationEpoch === mapping.receipt.activationEpoch
              && value.activationId === mapping.receipt.activationId);
            session.executionProjection = {
              providerInstanceId: session.runtime.instanceId,
              value: matches ? value : { status: "unverified" }
            };
            return;
          }
          case "session-controls": {
            session.controls = event.controls.map((option) => ({
              ...option,
              choices: option.choices?.map((choice) => ({ ...choice })),
            }));
            return;
          }
          case "available-commands": {
            session.commands = event.commands.map((command) => ({
              ...command,
            }));
            return;
          }
          case "session-info": {
            if (!session.execution && typeof event.title === "string" && event.title.trim()) {
              session.title = normalizeSessionTitle(event.title.trim()).slice(0, 120);
            }
            if (typeof event.updatedAt === "string") {
              const parsed = Date.parse(event.updatedAt);
              if (Number.isFinite(parsed)) {
                session.updatedAt = Math.max(session.updatedAt, parsed);
                session.lastActivityAt = Math.max(session.lastActivityAt, parsed);
              }
            }
            if (event.continuityLevel === "recovered") {
              session.statusDetail =
                "Neko Core đã phục hồi checkpoint sau lần dừng bất thường; các mutation chưa có kết quả được giữ ở trạng thái chưa xác định và sẽ không tự chạy lại.";
            }
            return;
          }
          case "turn-started": {
            session.status = "streaming";
            session.messages.push({
              id: uuidv4(),
              role: "assistant",
              blocks: [],
            });
            return;
          }
          case "activity": {
            const message = openAssistant(session);
            if (!message)
              return;
            const existing = message.blocks!.find((block): block is ToolExecutionBlockData => block.type === "tool_execution" && block.id === event.activity.id);
            const next = toToolBlock(event.activity);
            if (existing) {
              existing.tool = next.tool;
              existing.status = next.status;
              existing.outcome = next.outcome;
            }
            else {
              message.blocks!.push(next);
            }
            if (event.activity.locations?.length) {
              appendOwnedSessionEvent(session, "runtime", {
                type: "workspace-activity",
                activityId: event.activity.id,
                title: event.activity.title,
                status: event.activity.status,
                operation: event.activity.operation ?? null,
                locations: event.activity.locations.map((location) => ({ ...location })),
                ...(event.activity.toolName ? { toolName: event.activity.toolName } : {}),
                ...(event.activity.detail ? { detail: event.activity.detail } : {}),
              });
            }
            return;
          }
          case "permission-request": {
            session.pendingPermission = event.request;
            session.resolvingPermissionId = null;
            return;
          }
          case "turn-finished": {
            if (event.promptEventId && session.runtime) {
              appendOwnedSessionEvent(session, "runtime", {
                type: "turn-terminal",
                providerInstanceId: session.runtime.instanceId, promptEventId: event.promptEventId, stopReason: event.stopReason
              });
            }
            session.status = "idle";
            session.pendingPermission = null;
            session.resolvingPermissionId = null;
            session.cancelPending = false;
            const message = openAssistant(session);
            const last = message ? lastBlock(message) : undefined;
            if (last?.type === "thinking") {
              (last as ThinkingBlockData).endTime = Date.now();
            }
            return;
          }
          case "error": {
            const message = openAssistant(session);
            if (message) {
              message.blocks!.push({
                type: "answer",
                id: uuidv4(),
                content: `⚠️ ${event.message}`,
              } satisfies AnswerBlockData);
            }
            else {
              session.statusDetail = event.message;
            }
            if (event.fatal) {
              session.executionProjection = undefined;
              session.status = "error";
              session.statusDetail = event.message;
              if (session.taskScope) {
                // The adapter revoked the failed scoped admission. A stale
                // card/queued click must not retain a permission projection.
                session.pendingPermission = null;
                session.resolvingPermissionId = null;
              }
            }
            return;
          }
          case "process-exited": {
            session.runtime = null;
            session.executionProjection = undefined;
            if (exitingProvider) {
              appendOwnedSessionEvent(session, "runtime", {
                type: "runtime-detached",
                providerId: exitingProvider.providerId,
                instanceId: exitingProvider.instanceId,
                kind: exitingProvider.kind,
                reason: "process-exit",
              });
            }
            session.status = "exited";
            session.pendingPermission = null;
            session.resolvingPermissionId = null;
            session.cancelPending = false;
            session.statusDetail = providerProcessExitDetail(event.code, {
              emptyModelReply: !sessionHasVisibleModelOutput(session.messages, session.events),
              stderrTail: event.stderrTail,
            });
            return;
          }
        }
      });
      // Provider exit is a boundary fact, not ordinary streaming output. Make
      // its detach record immediate so a crash cannot restore a phantom runtime.
      const session = get().sessions[event.sessionId];
      if (session) {
        if (event.type === "activity" && session.workspace) {
          useNekoWorkspaceStore
            .getState()
            .observeActivity(event.sessionId, session.workspace, event.activity);
        }
        if (event.type === "turn-finished") {
          void persistSessionNowOrReport(event.sessionId, "lượt trả lời đã kết thúc", { strict: true }).then((saved) => {
            const current = get().sessions[event.sessionId];
            if (!saved || !completedTurn || !current || current.status !== "idle"
              || current.closePending || current.deletePending
              || current.messages[current.messages.length - 1]?.id !== completedTurn)
              return;
            useCompletionNoticeStore.getState().publish({
              id: `${event.sessionId}:${completedTurn}`, sessionId: event.sessionId, title: current.title,
            });
          });
        }
        else if (event.type === "process-exited") {
          void persistSessionNowOrReport(event.sessionId, "trạng thái provider đã thoát", {
            strict: true,
          });
        }
        else {
          persistSessionDebounced(session);
        }
      }
      if (event.type === "process-exited") {
        void runtimes.detach(event.sessionId).catch(() => { });
      }
    }
  };
}
