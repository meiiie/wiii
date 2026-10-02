import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const { saveGraph } = vi.hoisted(() => ({
  saveGraph: vi.fn(async (graph: unknown) => ({
    v: 1,
    updatedAt: new Date().toISOString(),
    graph,
  })),
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

describe("Wiii task-first desktop shell", () => {
  beforeEach(() => {
    saveGraph.mockClear();
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
    fireEvent.click(screen.getByRole("button", { name: "Chọn agent" }));
    expect((await screen.findByTestId("launch-criteria")).textContent).toBe("Keep source | Pass checks");
  });

  it("does not count a pending agent selection as a running execution", async () => {
    await useAdeWorkStore.getState().createTaskRun({
      workspace: { name: "Wiii", path: "C:\\src\\wiii" }, title: "Choose later",
    });
    render(<WiiiAdeApp />);
    expect(screen.getByText("0 lượt đang thực hiện")).toBeTruthy();
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
    expect(row.textContent).toContain("Phiên: sẵn sàng");
    fireEvent.click(row);
    expect(screen.getByText(/Phiên hiện còn mở/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Mở phiên agent" })).toBeTruthy();
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
    expect(screen.getByText("Danh sách yêu cầu, chưa phải kết quả kiểm chứng.")).toBeTruthy();
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
    if (hasSession) expect(screen.getByRole("button", { name: "Mở phiên agent" })).toBeTruthy();
    else expect(screen.queryByRole("button", { name: "Mở phiên agent" })).toBeNull();
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
    expect(row.textContent).toContain("Phiên: đã lưu · chưa kết nối");
    expect(row.textContent).not.toContain("Phiên: sẵn sàng");
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
    expect(screen.getByRole("button", { name: /Isolated row/ }).textContent).not.toContain("Phiên:");
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
});
