import type { NekoSessionEvent } from "./session-events";
import type { NekoSession } from "./stores/neko-session-store";
import { nativeRunBlocksRespawn } from "./stores/session-native-recovery";

export interface SessionControlNotice {
  kind: "cancel" | "detail" | "unknown";
  tone: "quiet" | "warning" | "danger";
  text: string;
  guidance?: string;
  stage?: "saving" | "staged" | "requested" | "cancelled" | "turn-ended" | "runtime-stopped";
}

const DIAGNOSTICS_GUIDANCE =
  "Cuộc trò chuyện và bản nháp vẫn được giữ lại.";

const EXIT_NOTICE_COPY = new Map([
  ["Runtime đã dừng khi rời Neko Chill.", "Phiên đã dừng."],
  ["Đã kết thúc phiên — nhắn tiếp để khởi động lại agent.", "Đã kết thúc phiên."],
  ["Phiên đã lưu — nhắn tiếp để khởi động lại agent.", "Phiên đã lưu."],
]);

function hasUnknownOutcome(events: NekoSessionEvent[]): boolean {
  type NativeIdentity = { agentSessionId: string; runId: string; providerId: string };
  const unknownRuns = new Map<string, NativeIdentity>();
  const uncertainCleanup = new Map<string, NativeIdentity>();
  const keyOf = (data: NativeIdentity) => JSON.stringify([data.agentSessionId, data.runId, data.providerId]);
  for (const { data } of events) {
    if (data.type === "native-runtime-reconciled") {
      const unknown = data.state === "unknown_outcome"
        || data.operationPhase === "unknown_outcome"
        || data.continuity === "unknown_outcome";
      if (unknown) unknownRuns.set(keyOf(data), data);
      else unknownRuns.delete(keyOf(data));
    } else if (data.type === "native-runtime-cleanup-uncertain") {
      uncertainCleanup.set(keyOf(data), data);
    } else if (data.type === "native-runtime-cleanup-resolved") {
      uncertainCleanup.delete(keyOf(data));
    } else if (data.type === "native-runtime-retired") {
      for (const records of [unknownRuns, uncertainCleanup]) {
        for (const [key, record] of records) {
          if (record.agentSessionId === data.agentSessionId && record.runId === data.runId) records.delete(key);
        }
      }
    }
  }
  return unknownRuns.size > 0 || uncertainCleanup.size > 0;
}

function cancellationNotice(session: NekoSession): SessionControlNotice | null {
  // Durable sequence is authoritative even if hydration arrives out of order.
  const events = [...session.events].sort((a, b) => a.seq - b.seq);
  let commandIndex = -1;
  for (let index = events.length - 1; index >= 0; index -= 1) {
    if (events[index].data.type === "runtime-command") {
      commandIndex = index;
      break;
    }
  }
  const command = events[commandIndex];
  if (!command || command.data.type !== "runtime-command") {
    return session.cancelPending ? {
      kind: "cancel", tone: "warning", stage: "saving",
      text: "Đang chuẩn bị dừng…",
    } : null;
  }
  const instanceId = command.data.providerInstanceId;
  const laterEvents = events.slice(commandIndex + 1);
  const eventsById = new Map(events.filter((event) => event.eventId).map((event) => [event.eventId, event]));
  const replaced = session.runtime && session.runtime.instanceId !== instanceId;
  const newTurn = laterEvents.some(({ data }) => {
    if (data.type !== "dispatch-invoked" || data.action !== "prompt") return false;
    const target = eventsById.get(data.targetEventId)?.data;
    return target?.type === "model-input" && target.providerInstanceId === data.providerInstanceId;
  });
  const newRuntime = laterEvents.some(({ data }) => data.type === "runtime-attached"
    && data.provider.instanceId !== instanceId);
  if (replaced || newTurn || newRuntime) return null;

  const invoked = command.eventId && laterEvents.some(({ data }) => data.type === "dispatch-invoked"
    && data.action === "cancel" && data.targetEventId === command.eventId
    && data.providerInstanceId === instanceId);
  const promptEventId = command.data.promptEventId;
  const prompt = promptEventId ? eventsById.get(promptEventId) : undefined;
  const promptInvoked = prompt?.data.type === "model-input"
    && prompt.data.providerInstanceId === instanceId
    && prompt.seq < command.seq
    && events.some(({ seq, data }) => data.type === "dispatch-invoked" && data.action === "prompt"
      && data.targetEventId === promptEventId && data.providerInstanceId === instanceId
      && seq > prompt.seq && seq < command.seq);
  const terminal = invoked && promptInvoked ? laterEvents.find(({ data }) => data.type === "turn-terminal"
    && data.providerInstanceId === instanceId && data.promptEventId === promptEventId) : undefined;
  if (terminal?.data.type === "turn-terminal") {
    return terminal.data.stopReason === "cancelled"
      ? { kind: "cancel", tone: "quiet", stage: "cancelled", text: "Đã dừng." }
      : { kind: "cancel", tone: "warning", stage: "turn-ended", text: "Lượt đã kết thúc; chưa xác nhận đã hủy." };
  }
  const processExited = laterEvents.some(({ data }) => data.type === "runtime-detached"
    && data.reason === "process-exit" && data.instanceId === instanceId);
  if (processExited) {
    return { kind: "cancel", tone: "quiet", stage: "runtime-stopped", text: "Phiên đã dừng." };
  }

  // A native completion needs the same checkpoint before and after the request.
  // A cancelled historical run alone cannot confirm this cancellation.
  let attachedIndex = -1;
  for (let index = commandIndex - 1; index >= 0; index -= 1) {
    if (events[index].data.type === "runtime-attached") {
      attachedIndex = index;
      break;
    }
  }
  const attached = events[attachedIndex]?.data;
  const providerId = attached?.type === "runtime-attached" && attached.provider.instanceId === instanceId
    && (!session.runtime || attached.provider.providerId === session.runtime.providerId)
    ? attached.provider.providerId : undefined;
  const nativeBefore = attachedIndex >= 0 && providerId
    ? [...events.slice(attachedIndex + 1, commandIndex)].reverse().find(({ data }) =>
    data.type === "native-runtime-reconciled"
    && data.providerId === providerId) : undefined;
  const native = nativeBefore?.data;
  // Provider identity alone cannot bind a historical native run to this process.
  const nativeIdentity = attached?.type === "runtime-attached"
    ? attached.provider.providerCapabilities?.extensions : undefined;
  const nativeCancelled = invoked && native?.type === "native-runtime-reconciled"
    && typeof nativeIdentity?.nativeAgentSessionId === "string"
    && typeof nativeIdentity?.nativeRunId === "string"
    && native.agentSessionId === nativeIdentity.nativeAgentSessionId
    && native.runId === nativeIdentity.nativeRunId
    && !["completed", "cancelled", "failed", "unknown_outcome"].includes(native.state)
    && native.operationPhase !== "unknown_outcome" && native.continuity !== "unknown_outcome"
    && laterEvents.some(({ data }) => data.type === "native-runtime-reconciled"
      && data.runId === native.runId && data.agentSessionId === native.agentSessionId
      && data.providerId === native.providerId && data.state === "cancelled"
      && data.operationPhase !== "unknown_outcome" && data.continuity !== "unknown_outcome");
  if (nativeCancelled) {
    return { kind: "cancel", tone: "quiet", stage: "cancelled", text: "Đã dừng." };
  }
  if (invoked) {
    return { kind: "cancel", tone: "warning", stage: "requested", text: "Đang chờ xác nhận dừng…" };
  }
  return session.cancelPending ? {
    kind: "cancel", tone: "warning", stage: "saving",
    text: "Đang lưu yêu cầu dừng…",
  } : {
    kind: "cancel", tone: "warning", stage: "staged",
    text: "Đã nhận yêu cầu dừng; chưa gửi.",
  };
}

export function getSessionControlNotices(session: NekoSession): SessionControlNotice[] {
  const notices: SessionControlNotice[] = [];
  const unknown = hasUnknownOutcome(session.events);
  if (unknown) {
    notices.push({
      kind: "unknown", tone: "danger",
      text: "Chưa rõ kết quả lượt này.",
      guidance: DIAGNOSTICS_GUIDANCE,
    });
  } else {
    const cancel = cancellationNotice(session);
    if (cancel) notices.push(cancel);
  }
  if (session.statusDetail?.trim() || session.status === "error") {
    // Normalize known success copy at display time, including saved sessions.
    // Never rewrite persisted data or arbitrary warning/error details.
    const detail = session.status === "exited"
      ? EXIT_NOTICE_COPY.get(session.statusDetail ?? "") ?? session.statusDetail : session.statusDetail;
    const duplicateStop = session.status === "exited"
      && notices.some((notice) => notice.tone === "quiet" && notice.text === detail);
    if (!duplicateStop) {
      notices.push({
        kind: "detail",
        tone: session.status === "error" ? "danger" : session.status === "exited" ? "quiet" : "warning",
        text: detail?.trim() ? detail : "Chưa thể tiếp tục cuộc trò chuyện.",
        guidance: session.status === "error" && !unknown ? DIAGNOSTICS_GUIDANCE : undefined,
      });
    }
  }
  return notices;
}

/** Only the last actually dispatched, confirmed cancelled input can be retried. */
export function getStoppedPrompt(session: NekoSession): { eventId: string; text: string } | null {
  if ((session.status !== "idle" && session.status !== "exited") || !session.workspace
    || session.cancelPending || session.closePending || session.deletePending
    || session.pendingControlId || session.pendingPermission || session.resolvingPermissionId
    || session.nativeRecoveryRequired || hasUnknownOutcome(session.events)
    || (!session.runtime && nativeRunBlocksRespawn(session))
    || cancellationNotice(session)?.stage !== "cancelled") return null;

  const events = [...session.events].sort((a, b) => a.seq - b.seq);
  const command = [...events].reverse().find(({ data }) => data.type === "runtime-command")?.data;
  const input = [...events].reverse().find(({ data }) => data.type === "model-input");
  if (command?.type !== "runtime-command" || command.action !== "cancel"
    || !input?.eventId || input.eventId !== command.promptEventId || input.data.type !== "model-input"
    || input.data.source !== "live" || !input.data.text.trim()
    || input.data.providerInstanceId !== command.providerInstanceId) return null;
  const inputIndex = events.indexOf(input);
  const commandIndex = events.findIndex(({ data }) => data === command);
  const dispatched = events.slice(inputIndex + 1, commandIndex).some(({ data }) =>
    data.type === "dispatch-invoked" && data.action === "prompt"
    && data.targetEventId === input.eventId && data.providerInstanceId === command.providerInstanceId);
  return dispatched ? { eventId: input.eventId, text: input.data.text } : null;
}

export function workspaceIsolationLabel(session: NekoSession): string {
  if (session.runtime?.workspaceIsolation === "advisory") {
    return "Runtime báo thư mục làm việc ở mức hướng dẫn, không phải ranh giới cách ly bắt buộc.";
  }
  if (session.runtime?.workspaceIsolation === "enforced") {
    return "Runtime báo có áp dụng cách ly thư mục làm việc.";
  }
  return "Chưa có thông tin cách ly thư mục từ runtime.";
}
