import { describe, expect, it } from "vitest";
import { deriveAdeTurnResult } from "@/ade/turn-lifecycle";
import { appendSessionEvent } from "@/neko-chill/session-events";
import type { NekoSession } from "@/neko-chill/stores/session-store-types";
import type { TurnStopReason } from "@/neko-chill/drivers/types";

function finishedSession(stopReason: TurnStopReason = "end_turn"): NekoSession {
  const events: NekoSession["events"] = [];
  const input = appendSessionEvent(events, "model", {
    type: "model-input", source: "live", messageId: "message-1", text: "Do the work",
    providerInstanceId: "instance-1", delivery: "staged",
  });
  appendSessionEvent(events, "runtime", {
    type: "dispatch-invoked", action: "prompt", targetEventId: input.eventId!, providerInstanceId: "instance-1",
  });
  appendSessionEvent(events, "runtime", {
    type: "turn-terminal", promptEventId: input.eventId!, providerInstanceId: "instance-1", stopReason,
  });
  return {
    execution: { runId: "run-1", taskId: "task-1", environmentId: "env-1" },
    status: "idle", events, runtime: { instanceId: "instance-1" },
  } as NekoSession;
}

describe("Work turn-result correlation", () => {
  it("accepts an explicit end_turn without claiming that the ACP process exited", () => {
    const session = finishedSession();
    expect(deriveAdeTurnResult(session)).toMatchObject({ outcome: "review", event: session.events[2] });
    session.runtime = null;
    session.status = "exited";
    session.events.reverse();
    expect(deriveAdeTurnResult(session)?.outcome).toBe("review");
  });

  it.each(["idle", "exited"] as const)("does not treat %s or model text alone as a result", (status) => {
    const session = finishedSession();
    session.status = status;
    session.events.pop();
    expect(deriveAdeTurnResult(session)).toBeNull();
  });

  it("rejects undispatched, mismatched and legacy turns", () => {
    const undispatched = finishedSession();
    undispatched.events.splice(1, 1);
    expect(deriveAdeTurnResult(undispatched)).toBeNull();
    const wrongPrompt = finishedSession();
    const terminal = wrongPrompt.events[2].data;
    if (terminal.type === "turn-terminal") terminal.promptEventId = "another-prompt";
    expect(deriveAdeTurnResult(wrongPrompt)).toBeNull();
    const wrongInstance = finishedSession();
    wrongInstance.runtime!.instanceId = "replacement";
    expect(deriveAdeTurnResult(wrongInstance)).toBeNull();
    const legacy = finishedSession();
    const input = legacy.events[0].data;
    if (input.type === "model-input") input.source = "legacy-migration";
    expect(deriveAdeTurnResult(legacy)).toBeNull();
  });

  it("does not finish a newer input using an older completed turn", () => {
    const session = finishedSession();
    appendSessionEvent(session.events, "model", {
      type: "model-input", source: "live", messageId: "message-2", text: "Follow up",
      providerInstanceId: "instance-1", delivery: "staged",
    });
    expect(deriveAdeTurnResult(session)).toBeNull();
  });

  it.each(["streaming", "dispatching", "stopping", "connecting", "error"] as const)("waits while the session is %s", (status) => {
    const session = finishedSession();
    session.status = status;
    expect(deriveAdeTurnResult(session)).toBeNull();
  });

  it.each(["cancelPending", "closePending", "deletePending"] as const)("waits for %s to settle", (flag) => {
    const session = finishedSession();
    session[flag] = true;
    expect(deriveAdeTurnResult(session)).toBeNull();
  });

  it("leaves manual chats and unresolved permissions outside Work completion", () => {
    const manual = finishedSession();
    manual.execution = null;
    expect(deriveAdeTurnResult(manual)).toBeNull();
    const permission = finishedSession();
    permission.pendingPermission = { requestId: "permission-1", title: "Write?", options: [] };
    expect(deriveAdeTurnResult(permission)).toBeNull();
  });

  it.each([
    ["cancelled", "cancelled"], ["error", "failed"], ["refusal", "failed"],
    ["max_tokens", "failed"], ["max_turn_requests", "failed"],
  ] as const)("projects %s as %s, never successful review", (reason, outcome) => {
    expect(deriveAdeTurnResult(finishedSession(reason))?.outcome).toBe(outcome);
  });
});
