import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NekoTranscript, SessionControlStatus } from "@/neko-chill/components/NekoTranscript";
import { getSessionControlNotices, workspaceIsolationLabel } from "@/neko-chill/session-control-status";
import type { NekoSessionEvent, NekoSessionEventData } from "@/neko-chill/session-events";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import { createProviderCapabilitySnapshot } from "@/neko/provider-registry";

vi.mock("@/components/common/MarkdownRenderer", () => ({
  MarkdownRenderer: ({ content, streaming }: { content: string; streaming?: boolean }) => (
    <div data-testid="markdown-content" data-streaming={streaming}>{content}</div>
  ),
}));
vi.mock("@/neko-chill/components/NekoPromptRail", () => ({ NekoPromptRail: () => null }));
vi.mock("@/neko-chill/components/PermissionCard", () => ({
  PermissionCard: ({ session }: { session?: NekoSession }) => (
    <div data-testid="permission-session" data-session-id={session?.id}><p role="status">Approval pending</p></div>
  ),
}));

function event(seq: number, data: NekoSessionEventData): NekoSessionEvent {
  return { v: 1, eventId: `event-${seq}`, seq, at: seq, visibility: "runtime", data };
}

function makeSession(overrides: Partial<NekoSession> = {}): NekoSession {
  return {
    id: "session", agentId: "neko", agentName: "Neko Core", title: "Session",
    createdAt: 1, updatedAt: 1, lastActivityAt: 1,
    workspace: { path: "C:/work/project", name: "Project" }, launchProfile: null,
    backendSessionId: null, controls: [], commands: [], pendingControlId: null,
    status: "streaming", messages: [], events: [], eventHighWaterMark: 0,
    runtime: {
      sessionId: "session", providerId: "neko", instanceId: "instance", kind: "acp",
      backendSessionId: null, capabilities: ["prompt", "cancel"],
      contextContinuity: "process", workspaceIsolation: "advisory",
      providerCapabilities: createProviderCapabilitySnapshot({ providerId: "neko", providerVersion: null,
        extensions: { nativeAgentSessionId: "native-session", nativeRunId: "run" } }),
    },
    pendingPermission: null, resolvingPermissionId: null,
    cancelPending: false, closePending: false, deletePending: false,
    ...overrides,
  };
}

const cancel = event(1, { type: "runtime-command", action: "cancel", providerInstanceId: "instance", delivery: "staged" });
const invoked = event(2, { type: "dispatch-invoked", targetEventId: cancel.eventId!, action: "cancel", providerInstanceId: "instance" });
const exit = event(3, { type: "runtime-detached", providerId: "neko", instanceId: "instance", kind: "acp", reason: "process-exit" });
const native = (seq: number, state: string, runId = "run") => event(seq, {
  type: "native-runtime-reconciled", agentSessionId: "native-session", runId, providerId: "neko",
  state, operationPhase: state === "unknown_outcome" ? "unknown_outcome" : "settled",
  continuity: "durable", replayedFromSeq: 0, replayedThroughSeq: seq, replayedEventCount: seq,
});

function nativeCancellationEvents(before: string, afterRun = "run"): NekoSessionEvent[] {
  const command = event(3, cancel.data);
  const dispatch = event(4, { type: "dispatch-invoked", targetEventId: command.eventId!, action: "cancel", providerInstanceId: "instance" });
  return [event(1, { type: "runtime-attached", provider: makeSession().runtime! }), native(2, before), command, dispatch, native(5, "cancelled", afterRun)];
}

describe("session control presentation facts", () => {
  it.each([
    { name: "normal idle", session: makeSession({ status: "idle" }), stage: undefined, detail: undefined, unknown: false },
    { name: "intent without marker", session: makeSession({ cancelPending: true }), stage: "saving", detail: undefined, unknown: false },
    { name: "pending staged cancel", session: makeSession({ events: [cancel], cancelPending: true }), stage: "saving", detail: undefined, unknown: false },
    { name: "staged without invocation", session: makeSession({ events: [cancel] }), stage: "staged", detail: undefined, unknown: false },
    { name: "pre-dispatch failure while streaming", session: makeSession({ statusDetail: "Cancel journal write failed" }), stage: undefined, detail: "Cancel journal write failed", unknown: false },
    { name: "dispatching persistence failure", session: makeSession({ status: "dispatching", statusDetail: "Prompt write failed" }), stage: undefined, detail: "Prompt write failed", unknown: false },
    { name: "requested with pending false", session: makeSession({ events: [cancel, invoked] }), stage: "requested", detail: undefined, unknown: false },
    { name: "idle is not cancellation confirmation", session: makeSession({ status: "idle", events: [cancel, invoked] }), stage: "requested", detail: undefined, unknown: false },
    { name: "unlinked dispatch", session: makeSession({ events: [cancel, event(2, { ...invoked.data, targetEventId: "other" } as NekoSessionEventData)] }), stage: "staged", detail: undefined, unknown: false },
    { name: "wrong provider instance", session: makeSession({ events: [cancel, event(2, { ...invoked.data, providerInstanceId: "other" } as NekoSessionEventData)] }), stage: "staged", detail: undefined, unknown: false },
    { name: "observed process exit", session: makeSession({ status: "exited", runtime: null, events: [cancel, invoked, exit], statusDetail: "Exit code 0" }), stage: "runtime-stopped", detail: "Exit code 0", unknown: false },
    { name: "fatal unknown journal", session: makeSession({ status: "error", events: [cancel, invoked, native(3, "unknown_outcome")], statusDetail: "Native outcome unknown" }), stage: undefined, detail: "Native outcome unknown", unknown: true },
  ])("renders honest facts for $name", ({ session, stage, detail, unknown }) => {
    const notices = getSessionControlNotices(session);
    expect(notices.find((notice) => notice.kind === "cancel")?.stage).toBe(stage);
    expect(notices.find((notice) => notice.kind === "detail")?.text).toBe(detail);
    expect(notices.some((notice) => notice.kind === "unknown")).toBe(unknown);
    render(<SessionControlStatus session={session} />);
    if (stage) expect(screen.getByTestId("session-control-cancel").getAttribute("data-stage")).toBe(stage);
    if (detail) expect(screen.getByTestId("session-control-detail").textContent).toContain(detail);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("confirms only a linked active native checkpoint becoming cancelled", () => {
    const session = makeSession({ events: nativeCancellationEvents("running") });
    expect(getSessionControlNotices(session)[0]?.stage).toBe("cancelled");
  });

  it.each(["missing", "other-session", "other-run"])("does not confirm native cancellation when attached identity is %s", (scenario) => {
    const session = makeSession();
    session.runtime!.providerCapabilities = scenario === "missing" ? undefined : createProviderCapabilitySnapshot({
      providerId: "neko", providerVersion: null, extensions: {
        nativeAgentSessionId: scenario === "other-session" ? "another-session" : "native-session",
        nativeRunId: scenario === "other-run" ? "another-run" : "run",
      },
    });
    session.events = [event(0, {type:"runtime-attached",provider:session.runtime!}),native(1,"running"),{...cancel,seq:2},{...invoked,seq:3},native(4,"cancelled")];
    expect(getSessionControlNotices(session)[0]?.stage).toBe("requested");
  });

  it.each(["already cancelled", "different run", "unbound native checkpoint", "wrong process instance"])("does not confirm cancellation from %s", (scenario) => {
    const events = scenario === "already cancelled"
      ? nativeCancellationEvents("cancelled")
      : scenario === "different run"
        ? nativeCancellationEvents("running", "other-run")
        : scenario === "unbound native checkpoint"
          ? [cancel, invoked, native(3, "cancelled")]
          : [cancel, invoked, event(3, { ...exit.data, instanceId: "other" } as NekoSessionEventData)];
    expect(getSessionControlNotices(makeSession({ events })).find((notice) => notice.kind === "cancel")?.stage).toBe("requested");
  });

  it("does not confirm a current cancellation using a previous same-provider runtime epoch", () => {
    const session = makeSession();
    const command = event(4, cancel.data);
    const dispatch = event(5, { type: "dispatch-invoked", targetEventId: command.eventId!, action: "cancel", providerInstanceId: "instance" });
    session.events = [
      event(1, { type: "runtime-attached", provider: { ...session.runtime!, instanceId: "previous-instance" } }),
      native(2, "running"),
      event(3, { type: "runtime-attached", provider: session.runtime! }),
      command, dispatch, native(6, "cancelled"),
    ];
    expect(getSessionControlNotices(session)[0]?.stage).toBe("requested");
  });

  it("removes the previous cancel notice after a linked new prompt", () => {
    const input = event(3, { type: "model-input", source: "live", messageId: "new-message", text: "Continue", providerInstanceId: "instance", delivery: "staged" });
    const prompt = event(4, { type: "dispatch-invoked", action: "prompt", providerInstanceId: "instance", targetEventId: input.eventId! });
    expect(getSessionControlNotices(makeSession({ events: [cancel, invoked, input, prompt] }))).toEqual([]);
    expect(getSessionControlNotices(makeSession({ events: [cancel, invoked, input] }))[0]?.stage).toBe("requested");
  });

  it("does not carry a prior provider cancellation into a replacement runtime", () => {
    const session = makeSession();
    session.runtime = { ...session.runtime!, instanceId: "replacement", providerId: "codex", kind: "codex-app-server" };
    session.events = [cancel, invoked, event(3, { type: "runtime-attached", provider: session.runtime })];
    expect(getSessionControlNotices(session)).toEqual([]);
  });

  it("keeps uncertain native cleanup visible until explicit resolution", () => {
    const uncertain = event(3, { type: "native-runtime-cleanup-uncertain", agentSessionId: "native-session", runId: "run", providerId: "neko", reason: "Transport ended" });
    const resolved = event(5, { type: "native-runtime-cleanup-resolved", agentSessionId: "native-session", runId: "run", providerId: "neko" });
    expect(getSessionControlNotices(makeSession({ events: [cancel, invoked, uncertain, native(4, "running")] }))[0]?.kind).toBe("unknown");
    expect(getSessionControlNotices(makeSession({ events: [cancel, invoked, uncertain, native(4, "running"), resolved] }))[0]?.stage).toBe("requested");
  });

  it.each(["provider", "native session"])("does not clear another unknown checkpoint sharing a run id across %s", (difference) => {
    const unknown = native(1, "unknown_outcome");
    const other = native(2, "completed");
    if (other.data.type === "native-runtime-reconciled") {
      if (difference === "provider") other.data.providerId = "codex";
      else other.data.agentSessionId = "other-native-session";
    }
    expect(getSessionControlNotices(makeSession({ events: [unknown, other] }))[0]?.kind).toBe("unknown");
  });

  it("keeps an unknown result after cleanup proves only that execution stopped", () => {
    const resolved = event(2, { type: "native-runtime-cleanup-resolved", agentSessionId: "native-session", runId: "run", providerId: "neko" });
    expect(getSessionControlNotices(makeSession({ events: [native(1, "unknown_outcome"), resolved] }))[0]?.kind).toBe("unknown");
  });
});

describe("transcript status visibility and capability copy", () => {
  it.each(["streaming", "dispatching", "stopping"] as const)("shows failures immediately while %s and preserves rendered content", (status) => {
    const session = makeSession({ status, statusDetail: "Cancellation failed before dispatch", messages: [{ id: "reply", role: "assistant", blocks: [{ id: "answer", type: "answer", content: "Existing streamed content" }] }] });
    render(<NekoTranscript session={session} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    expect(screen.getByTestId("session-control-detail").textContent).toContain(session.statusDetail);
    expect(screen.getByTestId("markdown-content").textContent).toBe("Existing streamed content");
    expect(screen.getByTestId("markdown-content").getAttribute("data-streaming")).toBe(String(status === "streaming"));
  });

  it("announces a long fatal message as safe wrapping text without recovery actions", () => {
    const detail = `<img src=x onerror=alert(1)> ${"C:/long-path/".repeat(80)}`;
    const session = makeSession({ status: "error", statusDetail: detail, events: [native(1, "unknown_outcome")] });
    const before = JSON.stringify(session);
    const { container } = render(<SessionControlStatus session={session} />);
    const notice = screen.getByTestId("session-control-detail");
    expect(notice.getAttribute("role")).toBe("alert");
    expect(notice.getAttribute("aria-atomic")).toBe("true");
    expect(notice.className).toContain("[overflow-wrap:anywhere]");
    expect(notice.textContent).toBe(detail);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByTestId("session-control-unknown").textContent).toContain("Giữ nguyên phiên và bản nháp");
    expect(JSON.stringify(session)).toBe(before);
  });

  it("passes session context to the permission card without another status role", () => {
    const session = makeSession({ events: [cancel], cancelPending: true, pendingPermission: { requestId: "permission", title: "Write file", options: [] } });
    render(<NekoTranscript session={session} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    expect(screen.getByTestId("permission-session").getAttribute("data-session-id")).toBe(session.id);
    expect(screen.getByRole("status").textContent).toBe("Approval pending");
    expect(screen.getByTestId("session-control-cancel").getAttribute("aria-live")).toBe("polite");
    expect(screen.queryByTestId("neko-working-state")).toBeNull();
  });

  it.each(["acp", "codex-app-server", "wiii-cloud"] as const)("uses declared isolation rather than %s provider identity", (kind) => {
    const session = makeSession({ status: "idle" });
    session.runtime = { ...session.runtime!, kind, workspaceIsolation: "advisory" };
    expect(workspaceIsolationLabel(session)).toContain("mức hướng dẫn");
    session.runtime.workspaceIsolation = "enforced";
    expect(workspaceIsolationLabel(session)).toBe("Runtime báo có áp dụng cách ly thư mục làm việc.");
    session.runtime = null;
    expect(workspaceIsolationLabel(session)).toContain("Chưa có thông tin");
  });

  it("keeps starter prompts as draft insertions and removes the confinement claim", () => {
    const onInsertPrompt = vi.fn();
    render(<NekoTranscript session={makeSession({ status: "idle", runtime: null })} onResolvePermission={vi.fn()} onInsertPrompt={onInsertPrompt} />);
    expect(screen.queryByText(/Agent chỉ làm việc/)).toBeNull();
    expect(screen.getByTestId("workspace-isolation-notice").textContent).toContain("Chưa có thông tin");
    fireEvent.click(screen.getAllByRole("button")[0]);
    expect(onInsertPrompt).toHaveBeenCalledTimes(1);
  });
});


describe("correlated runtime turn completion", () => {
  const input = event(10, { type: "model-input", source: "live", messageId: "message", text: "Task", providerInstanceId: "instance", delivery: "staged" });
  const prompt = event(11, { type: "dispatch-invoked", action: "prompt", targetEventId: input.eventId!, providerInstanceId: "instance" });
  const command = event(12, { ...cancel.data, promptEventId: input.eventId! } as NekoSessionEventData);
  const dispatch = event(14, { type: "dispatch-invoked", action: "cancel", targetEventId: command.eventId!, providerInstanceId: "instance" });
  const terminal = (stopReason = "cancelled", instance = "instance", promptId = input.eventId!) => event(13, {
    type: "turn-terminal", providerInstanceId: instance, promptEventId: promptId, stopReason,
  } as NekoSessionEventData);
  it("confirms canonical cancelled even when the ACP host remains alive", () => {
    const session = makeSession({ status: "idle", events: [input, prompt, command, dispatch, terminal()] });
    expect(getSessionControlNotices(session)[0]?.stage).toBe("cancelled");
    expect(getSessionControlNotices(session)[0]?.text).toContain("lượt đã dừng");
  });
  it("joins terminal before the cancel dispatch marker, using sequence not array arrival", () => {
    const session = makeSession({ events: [dispatch, terminal(), command, prompt, input] });
    expect(getSessionControlNotices(session)[0]?.stage).toBe("cancelled");
  });
  it.each(["foreign prompt", "foreign instance", "terminal before request", "uninvoked prompt", "uninvoked cancel"])("keeps cancellation unconfirmed for %s", (scenario) => {
    const ended = terminal("cancelled", scenario === "foreign instance" ? "old-instance" : "instance", scenario === "foreign prompt" ? "old-prompt" : input.eventId!);
    if (scenario === "terminal before request") ended.seq = 9;
    const events = [input, ...(scenario === "uninvoked prompt" ? [] : [prompt]), command, ...(scenario === "uninvoked cancel" ? [] : [dispatch]), ended];
    expect(getSessionControlNotices(makeSession({ status: "idle", events })).find(n => n.kind === "cancel")?.stage).toBe(scenario === "uninvoked cancel" ? "staged" : "requested");
  });
  it.each(["end_turn", "error", "refusal", "max_tokens"])("reports %s without claiming cancellation applied", (reason) => {
    const notice = getSessionControlNotices(makeSession({ events: [input, prompt, command, dispatch, terminal(reason)] }))[0];
    expect(notice.stage).toBe("turn-ended");
    expect(notice.text).not.toContain("lượt đã dừng");
  });
  it("preserves unknown outcome priority over a cancelled terminal", () => {
    expect(getSessionControlNotices(makeSession({ events: [input, prompt, command, dispatch, terminal(), native(15, "unknown_outcome")] }))[0].kind).toBe("unknown");
  });
});
