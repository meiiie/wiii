/** Native checkpoint discovery, replay limits, and recovery projection. */
import type { NekoSession, NativeControlReader } from "./session-store-types";
import type { NekoTopLevelSessionKind } from "@/neko/session-ownership";
import type { NekoNativeSessionRecord } from "@/neko/control-client";
import type { RuntimeProviderSnapshot } from "../runtime-manager";
import { appendOwnedSessionEvent } from "./session-projections";
import { canRecoverNekoTaskWriter, isNekoTaskScopeMapping } from "../task-scope-mapping";
export const NATIVE_REPLAY_PAGE_SIZE = 500;
export const MAX_NATIVE_REPLAY_EVENTS = 10000;
export const NATIVE_TERMINAL_STATES = new Set(["completed", "failed", "cancelled"]);
export function topLevelKind(session: Pick<NekoSession, "kind" | "execution">): NekoTopLevelSessionKind {
  return session.kind ?? (session.execution ? "worker" : "scratch");
}
export function nativeTaskId(session: Pick<NekoSession, "id" | "execution">): string {
  return session.execution?.taskId ?? `legacy-local/task/${session.id}`;
}
export function nativeSessionsForTask(sessions: NekoNativeSessionRecord[], session: Pick<NekoSession, "id" | "execution">): NekoNativeSessionRecord[] {
  const candidates = sessions.filter((candidate) => candidate.taskId === nativeTaskId(session));
  candidates.sort((left, right) => {
    const timestamp = Date.parse(right.updatedAt) - Date.parse(left.updatedAt);
    return timestamp || right.agentSessionId.localeCompare(left.agentSessionId);
  });
  return candidates;
}
export function nativeRuntimeIdentity(provider: RuntimeProviderSnapshot): {
  agentSessionId: string;
  runId: string;
} {
  const extensions = provider.providerCapabilities?.extensions;
  const agentSessionId = extensions?.nativeAgentSessionId;
  const runId = extensions?.nativeRunId;
  if (typeof agentSessionId === "string" &&
    agentSessionId.length > 0 &&
    typeof runId === "string" &&
    runId.length > 0) {
    return { agentSessionId, runId };
  }
  // Legacy/test drivers can lack the native identifiers. Preserve a durable,
  // deliberately unresolvable tombstone instead of allowing an uncertain
  // cleanup to become permission for a replacement side effect.
  return {
    agentSessionId: `unresolved/${provider.instanceId}`,
    runId: `unresolved/${provider.instanceId}`,
  };
}
export function lastNativeCursor(session: NekoSession, runId: string): number {
  for (let index = session.events.length - 1; index >= 0; index -= 1) {
    const data = session.events[index].data;
    if (data.type === "native-runtime-reconciled" && data.runId === runId) {
      return data.replayedThroughSeq;
    }
  }
  return 0;
}
export function nativeRunBlocksRespawn(session: NekoSession): boolean {
  const safelyResolved = new Set<string>();
  for (let index = session.events.length - 1; index >= 0; index -= 1) {
    const data = session.events[index].data;
    if (data.type === "runtime-attached")
      break;
    if (data.type === "native-runtime-retired") {
      safelyResolved.add(data.agentSessionId);
      continue;
    }
    if (data.type === "native-runtime-cleanup-resolved") {
      safelyResolved.add(data.agentSessionId);
      continue;
    }
    if (data.type === "native-runtime-reconciled") {
      if (safelyResolved.has(data.agentSessionId))
        continue;
      if (data.state === "unknown_outcome" ||
        data.operationPhase === "unknown_outcome" ||
        data.continuity === "unknown_outcome" ||
        !NATIVE_TERMINAL_STATES.has(data.state)) {
        return true;
      }
      safelyResolved.add(data.agentSessionId);
      continue;
    }
    if (data.type === "native-runtime-cleanup-uncertain" &&
      !safelyResolved.has(data.agentSessionId)) {
      return true;
    }
  }
  return false;
}
/** UI affordance only: the recovery action still verifies native truth and persistence. */
export function nativeSessionNeedsRecovery(session: NekoSession): boolean {
  const taskWriter = canRecoverNekoTaskWriter(session.taskScope);
  return !session.runtime &&
    (!session.taskScope || taskWriter || (isNekoTaskScopeMapping(session.taskScope) && session.taskScope.state !== "recovery-required")) &&
    (session.status === "error" || (session.status === "stopping" && session.closePending)) &&
    (taskWriter || Boolean(session.nativeRecoveryRequired) || nativeRunBlocksRespawn(session));
}
export function retireAbsentNativeCheckpoints(session: NekoSession, natives: NekoNativeSessionRecord[]): boolean {
  const present = new Set(natives.map((native) => native.agentSessionId));
  const resolved = new Set<string>();
  const retire: Array<{
    agentSessionId: string;
    runId: string;
  }> = [];
  for (let index = session.events.length - 1; index >= 0; index -= 1) {
    const data = session.events[index].data;
    if (data.type === "runtime-attached")
      break;
    if (data.type === "native-runtime-retired") {
      resolved.add(data.agentSessionId);
      continue;
    }
    if (data.type !== "native-runtime-reconciled" || resolved.has(data.agentSessionId))
      continue;
    resolved.add(data.agentSessionId);
    if (!present.has(data.agentSessionId) &&
      NATIVE_TERMINAL_STATES.has(data.state) &&
      data.operationPhase !== "unknown_outcome" &&
      data.continuity !== "unknown_outcome") {
      retire.push({ agentSessionId: data.agentSessionId, runId: data.runId });
    }
  }
  for (const checkpoint of retire) {
    appendOwnedSessionEvent(session, "runtime", {
      type: "native-runtime-retired",
      ...checkpoint,
      reason: "projection-pruned",
    });
  }
  return retire.length > 0;
}
export function reconcileNativeStatus(session: NekoSession, natives: NekoNativeSessionRecord[]): void {
  const uncertain = natives.find((native) => native.state === "unknown_outcome" || native.operationPhase === "unknown_outcome");
  if (uncertain) {
    session.status = "error";
    session.statusDetail =
      "Chưa rõ kết quả lượt trước. Wiii không tự gửi lại.";
    return;
  }
  const nonterminal = natives.find((native) => !NATIVE_TERMINAL_STATES.has(native.state));
  if (nonterminal) {
    // Phase 2A cannot reattach a renderer transport to an already-running
    // native process. One unresolved execution is enough to lock the visible
    // Task even when a newer execution has already reached a terminal state.
    session.status = "error";
    session.statusDetail =
      "Chưa nối lại được cuộc trò chuyện. Tạm khóa gửi để tránh chạy trùng.";
    return;
  }
  const native = natives[0];
  if (!native)
    return;
  if (NATIVE_TERMINAL_STATES.has(native.state)) {
    session.status = "exited";
    session.statusDetail = native.state === "completed"
      ? "Phiên trước đã kết thúc. Nhắn tiếp để mở lại."
      : native.state === "cancelled"
        ? "Phiên trước đã dừng. Nhắn tiếp để mở lại."
        : "Phiên trước gặp lỗi. Nhắn tiếp để thử lại.";
    return;
  }
}
export async function reconcileNativeRuntime(session: NekoSession, native: NekoNativeSessionRecord, reader: NativeControlReader): Promise<{
  changed: boolean;
  native: NekoNativeSessionRecord;
}> {
  const fromSeq = lastNativeCursor(session, native.runId);
  let afterSeq = fromSeq;
  let replayedEventCount = 0;
  let hasMore = true;
  while (hasMore) {
    const page = await reader.readEvents(native.runId, afterSeq, NATIVE_REPLAY_PAGE_SIZE);
    replayedEventCount += page.events.length;
    if (replayedEventCount > MAX_NATIVE_REPLAY_EVENTS) {
      throw new Error("Native replay vượt quá giới hạn an toàn 10.000 sự kiện.");
    }
    afterSeq = page.nextAfterSeq;
    hasMore = page.hasMore;
  }
  // listSessions() preceded replay, so the process may have transitioned
  // while pages were being consumed. Re-read the authoritative projection
  // after the replay barrier; otherwise a terminal event can be checkpointed
  // while the visible session remains incorrectly locked as "running".
  const refreshedNative = (await reader.listSessions(native.runId)).find((candidate) => candidate.agentSessionId === native.agentSessionId);
  if (!refreshedNative) {
    throw new Error(`Native session ${native.agentSessionId} biến mất trong lúc đối soát journal.`);
  }
  const previous = [...session.events].reverse().find((event) => (event.data.type === "native-runtime-reconciled" &&
    event.data.agentSessionId === refreshedNative.agentSessionId));
  const previousData = previous?.data.type === "native-runtime-reconciled"
    ? previous.data
    : null;
  const changed = replayedEventCount > 0 ||
    previousData === null ||
    previousData.state !== refreshedNative.state ||
    previousData.operationPhase !== refreshedNative.operationPhase ||
    previousData.continuity !== refreshedNative.continuity ||
    previousData.replayedThroughSeq !== afterSeq;
  if (changed) {
    appendOwnedSessionEvent(session, "runtime", {
      type: "native-runtime-reconciled",
      agentSessionId: refreshedNative.agentSessionId,
      runId: refreshedNative.runId,
      providerId: refreshedNative.providerId,
      state: refreshedNative.state,
      operationPhase: refreshedNative.operationPhase,
      continuity: refreshedNative.continuity,
      replayedFromSeq: fromSeq,
      replayedThroughSeq: afterSeq,
      replayedEventCount,
    });
  }
  return { changed, native: refreshedNative };
}
