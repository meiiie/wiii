import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

const { saveGraph, saveSession, listNativeSessions } = vi.hoisted(() => ({
  listNativeSessions: vi.fn(async () => [] as { agentSessionId: string; state: string; operationPhase: string; continuity: string }[]),
  saveSession: vi.fn(async () => {}),
  saveGraph: vi.fn(async (graph: unknown) => ({
    v: 1,
    updatedAt: new Date().toISOString(),
    graph,
  })),
}));

vi.mock("@/neko/control-client", async () => {
  const actual = await vi.importActual<typeof import("@/neko/control-client")>("@/neko/control-client");
  return { ...actual, getNekoControlClient: () => ({
    listSessions: listNativeSessions,
    unresolvedStartSessionIds: () => [], reconcilableStartSessionIds: () => [],
    cancelUnresolvedStarts: async () => {},
  }) };
});

vi.mock("@/neko-chill/persistence", async () => ({
  ...await vi.importActual<typeof import("@/neko-chill/persistence")>("@/neko-chill/persistence"),
  persistSessionStrict: saveSession,
}));

vi.mock("@/ade/persistence", async () => {
  const actual = await vi.importActual<typeof import("@/ade/persistence")>("@/ade/persistence");
  return {
    ...actual,
    loadAdeWorkSnapshot: vi.fn(async () => null),
    saveAdeWorkGraph: saveGraph,
  };
});

vi.mock("@/neko-chill/workspace", async () => {
  const actual = await vi.importActual<typeof import("@/neko-chill/workspace")>("@/neko-chill/workspace");
  return {
    ...actual,
    chooseWorkspaceFolder: vi.fn(async () => ({
      path: "C:\\src\\wiii",
      name: "Wiii",
    })),
  };
});

vi.mock("@/neko-chill/NekoChillApp", () => ({
  default: ({ taskLaunch, onOpenWork }: {
    taskLaunch?: { title: string; acceptanceCriteria?: readonly string[]; execution: { taskId: string; runId: string } } | null;
    onOpenWork: () => void;
  }) => (
    <div data-testid="mock-neko">
      <span>{taskLaunch ? `Task launch: ${taskLaunch.title}` : "Manual Neko Chill"}</span>
      {taskLaunch ? <><span>Run {taskLaunch.execution.runId}</span><span data-testid="launch-criteria">{taskLaunch.acceptanceCriteria?.join(" | ")}</span></> : null}
      <button type="button" onClick={onOpenWork}>Về công việc</button>
    </div>
  ),
}));

import WiiiAdeApp from "@/ade/WiiiAdeApp";
import { resetAdeWorkStoreForTests, useAdeWorkStore } from "@/ade/store";
import { useNekoSessionStore } from "@/neko-chill/stores/neko-session-store";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import { appendSessionEvent } from "@/neko-chill/session-events";

describe("Wiii task-first desktop shell", () => {
  beforeEach(() => {
    saveGraph.mockClear();
    saveSession.mockReset().mockResolvedValue(undefined);
    listNativeSessions.mockReset().mockResolvedValue([]);
    resetAdeWorkStoreForTests();
    useAdeWorkStore.setState({ hydrated: true, hydrating: false, error: null });
    useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, hydrated: true });
  });

  it("opens on Wiii work and keeps manual Neko Chill one action away", () => {
    render(<WiiiAdeApp />);

    expect(screen.getByTestId("work-home")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Công việc" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Công việc mới/i }).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByTestId("open-neko"));
    expect(screen.getByText("Manual Neko Chill")).toBeTruthy();
  });

  it("explains missing Work prerequisites and marks the goal required", async () => {
    render(<WiiiAdeApp />);
    fireEvent.click(screen.getByTestId("new-task"));
    const next = screen.getByTestId("continue-task");
    const title = screen.getByTestId("task-title");
    expect(title.getAttribute("required")).not.toBeNull();
    expect(next.getAttribute("aria-describedby")).toBe("wiii-task-prerequisites");
    expect(screen.getByText("Chọn thư mục dự án và nhập mục tiêu để tiếp tục.")).toBeTruthy();
    fireEvent.change(title, { target: { value: "A clear goal" } });
    expect(screen.getByText("Chọn thư mục dự án để tiếp tục.")).toBeTruthy();
    fireEvent.click(screen.getByTestId("choose-task-workspace"));
    await screen.findByText("C:\\src\\wiii");
    expect(next.hasAttribute("disabled")).toBe(false);
    fireEvent.change(title, { target: { value: "   " } });
    expect(screen.getByText("Nhập mục tiêu cần hoàn thành để tiếp tục.")).toBeTruthy();
    expect(next.hasAttribute("disabled")).toBe(true);
    expect(saveGraph).not.toHaveBeenCalled();
  });

  it("commits Project, Task and Run before handing execution to Neko", async () => {
    render(<WiiiAdeApp />);

    fireEvent.click(screen.getByTestId("new-task"));
    fireEvent.click(screen.getByTestId("choose-task-workspace"));
    await screen.findByText("C:\\src\\wiii");
    fireEvent.change(screen.getByTestId("task-title"), {
      target: { value: "Activate task-first desktop" },
    });
    fireEvent.click(screen.getByTestId("continue-task"));

    await screen.findByText("Task launch: Activate task-first desktop");
    expect(saveGraph).toHaveBeenCalledTimes(1);
    const graph = useAdeWorkStore.getState().graph;
    expect(graph.tasks).toHaveLength(1);
    expect(graph.runs).toHaveLength(1);
    expect(graph.runs[0]).toMatchObject({
      taskId: graph.tasks[0].id,
      state: "starting",
    });
    expect(screen.getByText(`Run ${graph.runs[0].id}`)).toBeTruthy();
  });

  it("disarms a Task launcher when the user returns to Wiii work", async () => {
    render(<WiiiAdeApp />);

    fireEvent.click(screen.getByTestId("new-task"));
    fireEvent.click(screen.getByTestId("choose-task-workspace"));
    await screen.findByText("C:\\src\\wiii");
    fireEvent.change(screen.getByTestId("task-title"), {
      target: { value: "One durable launch" },
    });
    fireEvent.click(screen.getByTestId("continue-task"));
    await screen.findByText("Task launch: One durable launch");

    fireEvent.click(screen.getByRole("button", { name: "Về công việc" }));
    fireEvent.click(screen.getByTestId("open-neko"));
    expect(screen.getByText("Manual Neko Chill")).toBeTruthy();
    expect(screen.queryByText("Task launch: One durable launch")).toBeNull();
  });

  it("preserves saved criteria when revisiting a pending Work launch", async () => {
    await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" },
      title: "Saved draft", acceptanceCriteria: ["Keep source", "Pass checks"],
    });
    render(<WiiiAdeApp />);
    fireEvent.click(screen.getByRole("button", { name: /Saved draft/ }));
    fireEvent.click(screen.getByRole("button", { name: "Chọn trợ lý" }));
    expect((await screen.findByTestId("launch-criteria")).textContent).toBe("Keep source | Pass checks");
  });

  it("does not count a pending agent selection as a running execution", async () => {
    await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Choose later",
    });
    render(<WiiiAdeApp />);
    expect(screen.queryByLabelText(/lượt đang thực hiện/)).toBeNull();
    expect(screen.getByRole("button", { name: /Choose later/ }).textContent).toContain("Đang chuẩn bị thực thi");
  });

  it("shows current session status without rewriting a terminal Run", async () => {
    const created = await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Continued conversation",
    });
    await useAdeWorkStore.getState().transitionRun(created.runId, "cancelled");
    useNekoSessionStore.setState({ sessions: { continued: {
      id: "continued", agentName: "Neko Core", execution: created.execution,
      status: "idle", events: [], runtime: { instanceId: "live-instance" },
      cancelPending: false, closePending: false,
    } as NekoSession } });
    render(<WiiiAdeApp />);
    const row = screen.getByRole("button", { name: /Continued conversation/ });
    expect(row.textContent).toContain("Lần chạy: Đã dừng");
    fireEvent.click(row);
    expect(screen.getByText("Trò chuyện: sẵn sàng")).toBeTruthy();
    expect(screen.getByText(/Phiên hiện còn mở/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Mở trò chuyện" })).toBeTruthy();
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("cancelled");
    expect(useAdeWorkStore.getState().graph.tasks[0].state).toBe("cancelled");
  });

  it("presents acceptance criteria as requirements rather than passed checks", async () => {
    await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Unverified criteria",
      acceptanceCriteria: ["Keep behavior", "Keep behavior"],
    });
    render(<WiiiAdeApp />);
    fireEvent.click(screen.getByRole("button", { name: /Unverified criteria/ }));
    const requirements = screen.getByRole("list", { name: "Tiêu chí cần đáp ứng" });
    expect(requirements.querySelectorAll("li")).toHaveLength(2);
    expect(requirements.querySelector(".lucide-circle-check")).toBeNull();
  });

  it.each([true, false])("keeps unknown-outcome guidance visible without a runtime (session present: %s)", async (hasSession) => {
    const created = await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Interrupted work",
    });
    await useAdeWorkStore.getState().transitionRun(created.runId, "unknown_outcome");
    useNekoSessionStore.setState({ sessions: hasSession ? { interrupted: {
      id: "interrupted", execution: created.execution, status: "error", runtime: null, events: [],
    } as NekoSession } : {} });
    render(<WiiiAdeApp />);
    fireEvent.click(screen.getByRole("button", { name: /Interrupted work/ }));
    expect(screen.getByText(/Kết quả lần chạy chưa xác định/)).toBeTruthy();
    expect(screen.getByText(/không tự gửi lại yêu cầu/)).toBeTruthy();
    if (hasSession) expect(screen.getByRole("button", { name: "Mở trò chuyện" })).toBeTruthy();
    else expect(screen.queryByRole("button", { name: "Mở trò chuyện" })).toBeNull();
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("unknown_outcome");
  });

  it("does not call a saved idle snapshot connected without a runtime", async () => {
    const created = await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Saved only",
    });
    useNekoSessionStore.setState({ sessions: { saved: {
      id: "saved", execution: created.execution, status: "idle", events: [], runtime: null,
    } as NekoSession } });
    render(<WiiiAdeApp />);
    const row = screen.getByRole("button", { name: /Saved only/ });
    fireEvent.click(row);
    expect(screen.getByText("Trò chuyện: đã lưu · chưa kết nối")).toBeTruthy();
    expect(screen.queryByText("Trò chuyện: sẵn sàng")).toBeNull();
  });

  it("does not borrow the status of a session belonging to another Run", async () => {
    await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Isolated row",
    });
    useNekoSessionStore.setState({ sessions: { other: {
      id: "other", execution: { runId: "another-run", taskId: "another-task", environmentId: "other-env" },
      status: "streaming", events: [], runtime: { instanceId: "other-live" },
    } as NekoSession } });
    render(<WiiiAdeApp />);
    fireEvent.click(screen.getByRole("button", { name: /Isolated row/ }));
    expect(screen.queryByText(/Trò chuyện:/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Mở trò chuyện" })).toBeNull();
  });

  it("projects authoritative native completion to review and releases the environment", async () => {
    const created = await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" },
      title: "Review native result",
    });
    await useAdeWorkStore.getState().attachAgentSession({
      id: "native-agent-1",
      runId: created.runId,
      providerId: "codex",
      providerSessionId: "thread-1",
    });
    useNekoSessionStore.setState({
      sessions: {
        visible: {
          id: "visible",
          execution: created.execution,
          events: [{
            v: 1,
            eventId: "native-completed",
            seq: 1,
            at: 1,
            visibility: "runtime",
            data: {
              type: "native-runtime-reconciled",
              agentSessionId: "native-agent-1",
              runId: created.runId,
              providerId: "codex",
              state: "completed",
              operationPhase: "completed",
              continuity: "active",
              replayedFromSeq: 0,
              replayedThroughSeq: 1,
              replayedEventCount: 1,
            },
          }],
          status: "exited",
        } as NekoSession,
      },
      activeSessionId: null,
    });

    render(<WiiiAdeApp />);

    await waitFor(() => {
      expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("review");
    });
    expect(useAdeWorkStore.getState().graph.tasks[0].state).toBe("review");
    expect(useAdeWorkStore.getState().graph.environments[0].state).toBe("stopped");
  });

  async function bindCompletedTurn() {
    const created = await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Review ACP answer",
    });
    await useAdeWorkStore.getState().attachAgentSession({
      id: "native-neko", runId: created.runId, providerId: "neko", providerSessionId: "backend-neko",
    });
    const events: NekoSession["events"] = [];
    const input = appendSessionEvent(events, "model", {
      type: "model-input", source: "live", messageId: "input-1", text: "Do the work",
      providerInstanceId: "neko-live", delivery: "staged",
    });
    appendSessionEvent(events, "runtime", {
      type: "dispatch-invoked", action: "prompt", targetEventId: input.eventId!, providerInstanceId: "neko-live",
    });
    appendSessionEvent(events, "runtime", {
      type: "turn-terminal", promptEventId: input.eventId!, providerInstanceId: "neko-live", stopReason: "end_turn",
    });
    const session = {
      id: "visible", execution: created.execution, agentName: "Neko Core", events, status: "idle",
      runtime: { instanceId: "neko-live", providerId: "neko", kind: "acp" },
    } as NekoSession;
    useNekoSessionStore.setState({ sessions: { visible: session } });
    return session;
  }

  it("waits for durable ACP results, then shows review while keeping the chat alive", async () => {
    let saved!: () => void;
    saveSession.mockImplementationOnce(() => new Promise<void>((resolve) => { saved = resolve; }));
    const session = await bindCompletedTurn();
    render(<WiiiAdeApp />);
    await waitFor(() => expect(saveSession).toHaveBeenCalledTimes(1));
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("running");
    saved();
    await screen.findByText("1 cần duyệt");
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("review");
    expect(useNekoSessionStore.getState().sessions.visible.runtime).toBe(session.runtime);
    fireEvent.click(screen.getByRole("button", { name: /Review ACP answer/ }));
    expect(screen.getByText("Sẵn sàng duyệt")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Mở trò chuyện" }));
    expect(useNekoSessionStore.getState().activeSessionId).toBe("visible");
  });

  it("recovers a saved result after restart even when the idle host was subsequently closed", async () => {
    await bindCompletedTurn();
    useNekoSessionStore.setState((state) => {
      const session = state.sessions.visible;
      session.runtime = null;
      session.status = "exited";
      appendSessionEvent(session.events, "runtime", {
        type: "native-runtime-reconciled", agentSessionId: "native-neko", runId: session.execution!.runId,
        providerId: "neko", state: "cancelled", operationPhase: "completed", continuity: "active",
        replayedFromSeq: 0, replayedThroughSeq: 1, replayedEventCount: 1,
      });
    });
    render(<WiiiAdeApp />);
    await screen.findByText("1 cần duyệt");
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("review");
    expect(useAdeWorkStore.getState().graph.tasks[0].state).toBe("review");
  });

  it("does not advance Work when the result cannot be persisted", async () => {
    saveSession.mockRejectedValue(new Error("disk full"));
    await bindCompletedTurn();
    render(<WiiiAdeApp />);
    await screen.findByText("Chưa lưu được kết quả lần chạy.");
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("running");
    saveSession.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    await screen.findByText("1 cần duyệt");
  });

  it("keeps review while confirmed host cleanup settles and after native reconciliation", async () => {
    await bindCompletedTurn();
    listNativeSessions.mockResolvedValue([{
      agentSessionId: "native-neko", state: "cancelled", operationPhase: "completed", continuity: "active",
    }]);
    render(<WiiiAdeApp />);
    await screen.findByText("1 cần duyệt");
    await act(async () => {
      useNekoSessionStore.setState((state) => {
        const session = state.sessions.visible;
        session.runtime = null;
        session.status = "exited";
        session.closePending = true;
        appendSessionEvent(session.events, "runtime", {
          type: "native-runtime-cleanup-resolved", agentSessionId: "native-neko",
          runId: session.execution!.runId, providerId: "neko",
        });
      });
    });
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("review");
    expect(listNativeSessions).not.toHaveBeenCalled();
    await act(async () => {
      useNekoSessionStore.setState((state) => {
        const session = state.sessions.visible;
        session.closePending = false;
        appendSessionEvent(session.events, "runtime", {
          type: "native-runtime-reconciled", agentSessionId: "native-neko", runId: session.execution!.runId,
          providerId: "neko", state: "cancelled", operationPhase: "completed", continuity: "active",
          replayedFromSeq: 0, replayedThroughSeq: 4, replayedEventCount: 4,
        });
      });
    });
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("review");
  });

  it("does not let a late native host read overwrite a newly durable turn result", async () => {
    await bindCompletedTurn();
    const terminal = useNekoSessionStore.getState().sessions.visible.events.at(-1)!;
    useNekoSessionStore.setState((state) => {
      const session = state.sessions.visible;
      session.events.pop();
      session.runtime = null;
      session.status = "exited";
    });
    let nativeRead!: (records: Awaited<ReturnType<typeof listNativeSessions>>) => void;
    listNativeSessions.mockImplementationOnce(() => new Promise((resolve) => { nativeRead = resolve; }));
    render(<WiiiAdeApp />);
    await waitFor(() => expect(listNativeSessions).toHaveBeenCalledTimes(1));
    await act(async () => {
      useNekoSessionStore.setState((state) => { state.sessions.visible.events.push(terminal); });
    });
    await screen.findByText("1 cần duyệt");
    await act(async () => {
      nativeRead([{ agentSessionId: "native-neko", state: "cancelled", operationPhase: "completed", continuity: "active" }]);
    });
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("review");
  });

  it("rechecks correlation after saving instead of finishing a newer prompt", async () => {
    let saved!: () => void;
    saveSession.mockImplementationOnce(() => new Promise<void>((resolve) => { saved = resolve; }));
    await bindCompletedTurn();
    render(<WiiiAdeApp />);
    await waitFor(() => expect(saveSession).toHaveBeenCalledTimes(1));
    await act(async () => {
      useNekoSessionStore.setState((state) => {
        const session = state.sessions.visible;
        session.status = "streaming";
        appendSessionEvent(session.events, "model", {
          type: "model-input", source: "live", messageId: "input-2", text: "Next turn", providerInstanceId: "neko-live",
        });
      });
      saved();
    });
    expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("running");
  });

  it("never hides uncertain native cleanup behind an apparent completed turn", async () => {
    await bindCompletedTurn();
    useNekoSessionStore.setState((state) => {
      const session = state.sessions.visible;
      appendSessionEvent(session.events, "runtime", {
        type: "native-runtime-cleanup-uncertain", runId: session.execution!.runId, agentSessionId: "native-neko",
        providerId: "neko", reason: "termination not proven",
      });
    });
    render(<WiiiAdeApp />);
    await waitFor(() => expect(useAdeWorkStore.getState().graph.runs[0].state).toBe("unknown_outcome"));
    expect(saveSession).not.toHaveBeenCalled();
  });
});
