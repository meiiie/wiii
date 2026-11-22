import type { NekoSessionEvent } from "@/neko-chill/session-events";
import type { NekoSession } from "@/neko-chill/stores/session-store-types";
import type { AdeNativeOutcome } from "./native-lifecycle";

/** A turn result is not a process-exit fact or proof of Task acceptance. */
export function deriveAdeTurnResult(session: NekoSession): {
  event: NekoSessionEvent;
  outcome: AdeNativeOutcome;
} | null {
  if (!session.execution || !["idle", "exited"].includes(session.status)
    || session.pendingPermission || session.cancelPending || session.closePending || session.deletePending)
    return null;

  const events = [...session.events].sort((a, b) => a.seq - b.seq);
  const input = [...events].reverse().find(({ data }) => data.type === "model-input" && data.source === "live");
  if (!input?.eventId || input.data.type !== "model-input" || !input.data.providerInstanceId)
    return null;
  const instanceId = input.data.providerInstanceId;
  if (session.runtime && session.runtime.instanceId !== instanceId) return null;

  const dispatched = events.find(({ seq, data }) => seq > input.seq
    && data.type === "dispatch-invoked" && data.action === "prompt"
    && data.targetEventId === input.eventId && data.providerInstanceId === instanceId);
  if (!dispatched) return null;
  const terminal = events.find(({ seq, data }) => seq > dispatched.seq
    && data.type === "turn-terminal" && data.promptEventId === input.eventId
    && data.providerInstanceId === instanceId);
  if (!terminal?.eventId || terminal.data.type !== "turn-terminal") return null;

  return {
    event: terminal,
    outcome: terminal.data.stopReason === "end_turn" ? "review"
      : terminal.data.stopReason === "cancelled" ? "cancelled" : "failed",
  };
}
