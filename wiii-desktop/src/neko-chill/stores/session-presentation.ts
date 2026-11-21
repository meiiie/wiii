/** Per-session semantic answer/reasoning buffers with ordered boundary draining. */
import { SemanticStreamBuffer } from "@/lib/semantic-stream-buffer";
import { markWiiiPerformance } from "@/lib/performance-telemetry";
import { openAssistant, lastBlock } from "./session-projections";
import type { ThinkingBlockData, AnswerBlockData } from "@/api/types/content-blocks";
import { v4 as uuidv4 } from "uuid";
import { persistSessionDebounced } from "../persistence";
import type { SessionStoreApi } from "./session-store-types";
export function createSessionPresentation(getStore: () => SessionStoreApi) {
  type PresentationDeltaKind = "answer" | "reasoning";
  interface PresentationStreamEntry {
    sessionId: string;
    kind: PresentationDeltaKind;
    order: number;
    buffer: SemanticStreamBuffer;
  }
  const presentationStreams = new Map<string, PresentationStreamEntry>();
  let presentationStreamOrder = 0;
  function presentationStreamKey(sessionId: string, kind: PresentationDeltaKind): string {
    return `${sessionId}:${kind}`;
  }
  function commitPresentationDelta(sessionId: string, kind: PresentationDeltaKind, text: string): void {
    if (!text)
      return;
    markWiiiPerformance(`wiii:stream:${sessionId}:start`);
    const now = Date.now();
    getStore().setState((state) => {
      const session = state.sessions[sessionId];
      if (!session)
        return;
      session.lastActivityAt = now;
      session.updatedAt = now;
      const message = openAssistant(session);
      if (!message)
        return;
      const last = lastBlock(message);
      if (kind === "reasoning") {
        if (last?.type === "thinking" && last.stepState !== "completed") {
          (last as ThinkingBlockData).content += text;
        }
        else {
          message.blocks!.push({
            type: "thinking",
            id: uuidv4(),
            content: text,
            toolCalls: [],
            startTime: now,
          } satisfies ThinkingBlockData);
        }
        return;
      }
      if (last?.type === "answer") {
        (last as AnswerBlockData).content += text;
      }
      else {
        message.blocks!.push({
          type: "answer",
          id: uuidv4(),
          content: text,
        } satisfies AnswerBlockData);
      }
    });
    const session = getStore().getState().sessions[sessionId];
    if (session)
      persistSessionDebounced(session);
  }
  function enqueuePresentationDelta(sessionId: string, kind: PresentationDeltaKind, text: string): void {
    // A change from reasoning to answer (or back) is a semantic boundary. Drain
    // the earlier channel first so separate timers can never reorder the blocks.
    for (const entry of presentationStreams.values()) {
      if (entry.sessionId === sessionId && entry.kind !== kind && entry.buffer.pending > 0) {
        entry.buffer.drain();
      }
    }
    const key = presentationStreamKey(sessionId, kind);
    let entry = presentationStreams.get(key);
    if (!entry) {
      entry = {
        sessionId,
        kind,
        order: ++presentationStreamOrder,
        buffer: new SemanticStreamBuffer({
          onFlush: (chunk) => commitPresentationDelta(sessionId, kind, chunk),
        }),
      };
      presentationStreams.set(key, entry);
    }
    else if (entry.buffer.pending === 0) {
      entry.order = ++presentationStreamOrder;
    }
    entry.buffer.push(text);
  }
  function drainPresentationStreams(sessionId: string): void {
    [...presentationStreams.values()]
      .filter((entry) => entry.sessionId === sessionId && entry.buffer.pending > 0)
      .sort((left, right) => left.order - right.order)
      .forEach((entry) => entry.buffer.drain());
  }
  function discardPresentationStreams(sessionId?: string): void {
    for (const [key, entry] of presentationStreams.entries()) {
      if (sessionId !== undefined && entry.sessionId !== sessionId)
        continue;
      entry.buffer.discard();
      presentationStreams.delete(key);
    }
  }
  return { enqueuePresentationDelta, drainPresentationStreams, discardPresentationStreams };
}
export type SessionPresentation = ReturnType<typeof createSessionPresentation>;
