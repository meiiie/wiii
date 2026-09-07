import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NekoChillApp from "@/neko-chill/NekoChillApp";
import {
  formatReasoningDuration,
  formatReasoningLabel,
  formatReasoningPreview,
  formatToolActivity,
  groupTranscriptBlocks,
  NekoTranscript,
  shouldVirtualizeTranscript,
  streamingActivityLabel,
  ThinkingDisclosure,
  ToolDisclosure,
  toolActivityFailed,
} from "@/neko-chill/components/NekoTranscript";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import {
  type NekoSession,
  useNekoSessionStore,
} from "@/neko-chill/stores/neko-session-store";
import { useNekoWorkspaceStore } from "@/neko-chill/stores/neko-workspace-store";
import { useNekoProjectStore } from "@/neko-chill/stores/neko-project-store";

vi.mock("@/neko-coworker/NekoCoworkerHome", () => ({
  NekoCoworkerHome: () => <div data-testid="neko-coworker-home">Coworker workstation</div>,
}));

function makeSession(
  id: string,
  title: string,
  workspace: NekoSession["workspace"],
  overrides: Partial<NekoSession> = {},
): NekoSession {
  return {
    id,
    agentId: "neko",
    agentName: "Neko Core",
    title,
    createdAt: 1_786_598_400_000,
    updatedAt: 1_786_598_400_000,
    workspace,
    launchProfile: null,
    controls: [],
    commands: [],
    pendingControlId: null,
    lastActivityAt: 1_786_598_400_000,
    status: "exited",
    statusDetail: "Đã lưu",
    messages: [],
    events: [],
    eventHighWaterMark: 0,
    runtime: null,
    pendingPermission: null,
    resolvingPermissionId: null,
    cancelPending: false,
    closePending: false,
    deletePending: false,
    ...overrides,
  };
}

describe("Neko Chill shell UI", () => {
  beforeEach(() => {
    useNekoAgentStore.setState({
      agents: [],
      isLoading: false,
      error: null,
      detect: vi.fn(async () => {}),
    });
    useNekoSessionStore.setState({
      sessions: {},
      activeSessionId: null,
      hydrated: true,
      hydrating: false,
      hydrationError: null,
      hydrate: vi.fn(async () => {}),
    });
    useNekoWorkspaceStore.setState({ sessions: {} });
    useNekoProjectStore.setState({
      projects: [],
      hydrated: true,
      hydrating: false,
      error: null,
    });
  });

  it("opens coworker workstation management as a first-class Neko surface", async () => {
    render(<NekoChillApp />);

    const link = screen.getByTestId("neko-coworker-link");
    expect(link.getAttribute("aria-current")).toBeNull();
    fireEvent.click(link);

    expect(await screen.findByTestId("neko-coworker-home")).toBeTruthy();
    expect(link.getAttribute("aria-current")).toBe("page");
    expect(screen.queryByTestId("neko-overview")).toBeNull();
  });

  it("opens account connections from the primary Neko navigation", () => {
    const onOpenConnections = vi.fn();
    render(<NekoChillApp onOpenConnections={onOpenConnections} />);

    fireEvent.click(screen.getByTestId("neko-connections-link"));

    expect(onOpenConnections).toHaveBeenCalledTimes(1);
  });

  it("keeps history closed on hydration failure and exposes a retry", () => {
    const hydrate = vi.fn(async () => {});
    useNekoSessionStore.setState({
      sessions: {},
      activeSessionId: null,
      hydrated: false,
      hydrating: false,
      hydrationError: "Snapshot phiên local-1 có schema không hợp lệ.",
      hydrate,
    });

    render(<NekoChillApp />);

    expect(screen.getByRole("alert").textContent).toContain("Chưa thể mở lịch sử phiên");
    expect(screen.getByText(/khóa việc tạo và mở phiên/i)).toBeTruthy();
    expect(screen.queryByTestId("session-sidebar")).toBeNull();
    expect(screen.queryByTestId("start-neko")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Thử tải lại" }));
    expect(hydrate).toHaveBeenCalledTimes(2);
  });

  it("removes transport emphasis markers from reasoning labels only", () => {
    expect(formatReasoningLabel("**Inspecting workspace**")).toBe("Inspecting workspace");
    expect(formatReasoningLabel("Keep **inner emphasis** here")).toBe(
      "Keep **inner emphasis** here",
    );
  });

  it("keeps reasoning compact until the reader asks for details", () => {
    expect(formatReasoningPreview("**Inspecting workspace files**", 22)).toBe(
      "Inspecting workspace…",
    );
    expect(formatReasoningDuration({
      type: "thinking",
      id: "duration",
      content: "Done",
      toolCalls: [],
      startTime: 1_000,
      endTime: 66_000,
    })).toBe("1 phút 5 giây");

    render(<ThinkingDisclosure block={{
      type: "thinking",
      id: "compact",
      content: "Inspecting the workspace before choosing the smallest safe change.",
      toolCalls: [],
      startTime: 1_000,
      endTime: 3_000,
    }} />);

    const disclosure = screen.getByTestId("thinking-block") as HTMLDetailsElement;
    expect(disclosure.open).toBe(false);
    expect(screen.getByTestId("thinking-preview").textContent).toContain("Inspecting the workspace");
    expect(screen.getByText("2 giây")).toBeTruthy();

    fireEvent.click(screen.getByLabelText("Đã suy nghĩ. Mở chi tiết suy luận"));
    expect(disclosure.open).toBe(true);
  });

  it("marks thinking as live only when the owning session says it is live", () => {
    const block = {
      type: "thinking" as const,
      id: "live",
      content: "Checking the current project",
      toolCalls: [],
    };
    const { rerender } = render(<ThinkingDisclosure block={block} />);
    expect(screen.getByLabelText("Đã suy nghĩ. Mở chi tiết suy luận")).toBeTruthy();

    rerender(<ThinkingDisclosure block={block} active />);
    expect(screen.getByLabelText("Đang suy nghĩ. Mở chi tiết suy luận")).toBeTruthy();
  });

  it("reduces verbose native tool titles to a stable timeline label and preview", () => {
    expect(formatToolActivity("Write(src/neko/session.ts)")).toEqual({
      label: "Write",
      preview: "src/neko/session.ts",
    });
    expect(formatToolActivity("Bash(npm run test)", "exit 0", 20)).toEqual({
      label: "Bash",
      preview: "exit 0",
    });

    render(<ToolDisclosure block={{
      type: "tool_execution",
      id: "failed-command",
      status: "completed",
      tool: { id: "failed-command", name: "Bash(npm test)", result: "exit 1 — command FAILED" },
    }} />);
    expect(screen.getByLabelText("Bash thất bại. Mở chi tiết")).toBeTruthy();
  });

  it("groups adjacent reasoning and tool activity without swallowing answer blocks", () => {
    const thinking = { type: "thinking" as const, id: "think", content: "Inspect", toolCalls: [] };
    const tool = {
      type: "tool_execution" as const,
      id: "tool",
      status: "completed" as const,
      tool: { id: "tool", name: "Read(src/app.ts)", result: "done" },
    };
    const answer = { type: "answer" as const, id: "answer", content: "Result" };
    const groups = groupTranscriptBlocks([thinking, tool, answer, thinking]);

    expect(groups.map((group) => group.kind)).toEqual(["activity", "content", "activity"]);
    expect(groups[0]?.kind === "activity" ? groups[0].blocks.map((block) => block.id) : []).toEqual([
      "think",
      "tool",
    ]);
    expect(toolActivityFailed({ ...tool, tool: { ...tool.tool, result: "exit 2" } })).toBe(true);

    const session = makeSession("grouped", "Grouped activity", { name: "Wiii", path: "E:\\Wiii" }, {
      messages: [{
        id: "assistant",
        role: "assistant",
        text: "",
        blocks: [thinking, tool, answer],
      }],
    });
    render(<NekoTranscript session={session} onResolvePermission={vi.fn()} onInsertPrompt={vi.fn()} />);
    const disclosure = screen.getByTestId("activity-group") as HTMLDetailsElement;
    expect(disclosure.open).toBe(false);
    fireEvent.click(screen.getByLabelText("2 bước đã thực hiện, 1 phân tích · 1 công cụ. Mở chi tiết"));
    expect(disclosure.open).toBe(true);
  });

  it("virtualizes only sessions long enough to benefit", () => {
    expect(shouldVirtualizeTranscript(50)).toBe(false);
    expect(shouldVirtualizeTranscript(51)).toBe(true);
  });

  it("keeps the working state explicit while complete response blocks are buffered", () => {
    const base = makeSession(
      "streaming",
      "Streaming",
      { path: "C:/work/neko", name: "Neko" },
      { status: "streaming", agentName: "Codex" },
    );
    expect(streamingActivityLabel(base)).toBe("Codex đang viết…");

    const withThinking = makeSession(
      "thinking",
      "Thinking",
      { path: "C:/work/neko", name: "Neko" },
      {
        status: "streaming",
        agentName: "Neko Core",
        messages: [{
          id: "assistant-thinking",
          role: "assistant",
          blocks: [{
            type: "thinking",
            id: "thinking",
            content: "Đang phân tích",
            toolCalls: [],
          }],
        }],
      },
    );
    expect(streamingActivityLabel(withThinking)).toBe("Neko Core đang suy nghĩ…");

    const withTool = makeSession(
      "tool",
      "Tool",
      { path: "C:/work/neko", name: "Neko" },
      {
        status: "streaming",
        messages: [{
          id: "assistant-tool",
          role: "assistant",
          blocks: [{
            type: "tool_execution",
            id: "tool",
            status: "pending",
            tool: { name: "Read(workspace)", result: "" },
          }],
        }],
      },
    );
    expect(streamingActivityLabel(withTool)).toBe("Đang chạy Read…");
  });

  it("lets readers pause tail-following and jump back to the newest message", () => {
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên dài",
          { path: "C:/work/neko", name: "Neko" },
          { status: "idle", statusDetail: undefined, messages: [
            { id: "one", role: "user", text: "Tin nhắn" },
          ] },
        ),
      },
      activeSessionId: "active",
    });
    render(<NekoChillApp />);

    const transcript = screen.getByTestId("neko-transcript");
    Object.defineProperties(transcript, {
      scrollHeight: { configurable: true, value: 1200 },
      clientHeight: { configurable: true, value: 500 },
      scrollTop: { configurable: true, value: 100, writable: true },
    });
    fireEvent.scroll(transcript);
    const jump = screen.getByRole("button", { name: "Đi tới tin nhắn mới nhất" });
    fireEvent.click(jump);
    expect(screen.queryByRole("button", { name: "Đi tới tin nhắn mới nhất" })).toBeNull();
  });

  it("creates a session only after submitting from Project Home", async () => {
    const createSession = vi.fn(async () => "new-session-id");
    const sendPrompt = vi.fn(async () => {});
    useNekoAgentStore.setState({
      agents: [{
        id: "gemini",
        name: "Gemini CLI",
        version: "1.0.0",
        found: true,
        availability: "available",
        supportsProfiles: false,
      }],
      isLoading: false,
      error: null,
      detect: vi.fn(async () => {}),
    });
    useNekoProjectStore.setState({
      projects: [{
        id: "project-wiii",
        name: "Wiii",
        roots: [{ path: "C:/work/wiii", name: "wiii" }],
        preferredHarnessId: "gemini",
        createdAt: 1,
        updatedAt: 1,
      }],
    });
    useNekoSessionStore.setState({ createSession, sendPrompt });

    render(<NekoChillApp />);
    expect(screen.getByText("Mọi phiên agent, ở một nơi.")).toBeTruthy();
    expect(screen.getByTestId("neko-overview-link").getAttribute("aria-current")).toBe("page");
    fireEvent.click(screen.getByTestId("new-session"));
    expect(screen.getByTestId("project-home")).toBeTruthy();
    expect(within(screen.getByTestId("desktop-titlebar")).queryByRole("button", { name: "Mở công cụ Project" })).toBeNull();
    expect(within(screen.getByTestId("work-area-toolbar")).getByRole("button", { name: "Mở công cụ Project" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Mở công cụ Project" })).toHaveLength(1);
    const workspaceToggle = screen.getByTestId("project-workspace-toggle");
    expect(workspaceToggle.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(screen.getAllByRole("button", { name: "Mở công cụ Project" })[0]);
    expect(await screen.findByTestId("neko-workspace-pane", {}, { timeout: 5000 })).toBeTruthy();
    expect(workspaceToggle.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("navigation", { name: "Công cụ Project" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Đóng workspace" }));
    expect(screen.getByText(/Bạn muốn làm gì trong/).textContent).toContain("Wiii");
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(screen.queryByTestId("neko-overview")).toBeNull();
    expect(createSession).not.toHaveBeenCalled();
    fireEvent.change(screen.getByTestId("project-home-input"), {
      target: { value: "Kiểm tra runtime" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Gửi và mở phiên" }));
    await vi.waitFor(() => {
      expect(createSession).toHaveBeenCalledTimes(1);
      expect(sendPrompt).toHaveBeenCalledWith("Kiểm tra runtime");
    });
    expect(createSession).toHaveBeenCalledWith(
      expect.objectContaining({ id: "gemini" }),
      { path: "C:/work/wiii", name: "wiii" },
      null,
      { projectId: "project-wiii" },
    );

    const switcher = screen.getByRole("button", {
      name: "Mở điều hướng Wiii. Khu vực hiện tại: Neko Chill",
    });
    expect(switcher.getAttribute("aria-expanded")).toBe("false");
    expect(switcher.textContent).toContain("Wiii");

    fireEvent.click(switcher);
    expect(switcher.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("menu", { name: "Điều hướng Wiii" })).toBeTruthy();
    expect(screen.getByText("Không gian trên máy")).toBeTruthy();
    expect(screen.queryByRole("menuitem", { name: /Công việc/i })).toBeNull();
    expect(screen.getByRole("menuitem", { name: /Neko Chill.*Đang mở/i }).getAttribute("aria-current"))
      .toBe("page");
    expect(screen.getByText(/Quản lý project, harness và các phiên trên máy này/i)).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: /Wiii Service/i })).toBeTruthy();
    expect(screen.getByText(/Đồng bộ và tri thức trực tuyến.*tùy chọn/i)).toBeTruthy();
    expect(screen.queryByText("Wiii Knowledge")).toBeNull();

    fireEvent.keyDown(window, { key: "Escape" });
    expect(switcher.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("menu", { name: "Điều hướng Wiii" })).toBeNull();
    expect(document.activeElement).toBe(switcher);
  });

  it("uses a bounded modal only for editing Project metadata", async () => {
    const updateProject = vi.fn(async () => {});
    useNekoProjectStore.setState({
      projects: [{
        id: "project-wiii",
        name: "Wiii",
        roots: [{ path: "C:/work/wiii", name: "wiii" }],
        preferredHarnessId: null,
        createdAt: 1,
        updatedAt: 1,
      }],
      updateProject,
    });

    render(<NekoChillApp />);
    fireEvent.click(screen.getByRole("button", { name: "Chỉnh sửa Project Wiii" }));
    expect(screen.getByRole("dialog", { name: "Chỉnh sửa Project" })).toBeTruthy();
    const name = screen.getByLabelText("Tên Project");
    fireEvent.change(name, { target: { value: "Wiii Desktop" } });
    fireEvent.click(screen.getByRole("button", { name: "Lưu thay đổi" }));

    await vi.waitFor(() => expect(updateProject).toHaveBeenCalledWith(
      "project-wiii",
      "Wiii Desktop",
      [{ path: "C:/work/wiii", name: "wiii" }],
    ));
    await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("keeps project navigation primary and offers harness as an alternate catalog projection", () => {
    useNekoSessionStore.setState({
      sessions: {
        codexWiii: makeSession(
          "codex-wiii",
          "Fix auth",
          { path: "C:/work/wiii", name: "Wiii" },
          { agentId: "codex", agentName: "Codex", updatedAt: 30 },
        ),
        nekoWiii: makeSession(
          "neko-wiii",
          "Review runtime",
          { path: "C:/work/wiii", name: "Wiii" },
          { agentId: "neko", agentName: "Neko Core", updatedAt: 20 },
        ),
        codexVideo: makeSession(
          "codex-video",
          "Optimize export",
          { path: "C:/work/video", name: "neko-video-cut" },
          { agentId: "codex", agentName: "Codex", updatedAt: 10 },
        ),
      },
      activeSessionId: null,
    });

    render(<NekoChillApp />);

    expect(screen.getByText("Mọi phiên agent, ở một nơi.")).toBeTruthy();
    expect(within(screen.getByLabelText("Tổng quan phiên")).getByText("3")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wiii 2" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "neko-video-cut 1" })).toBeTruthy();

    const overview = screen.getByTestId("neko-overview");
    fireEvent.click(within(overview).getByRole("button", { name: "Harness" }));

    expect(within(overview).getAllByText("Codex").length).toBeGreaterThan(0);
    expect(within(overview).getAllByText("Neko Core").length).toBeGreaterThan(0);
    expect(within(overview).getAllByText("neko-video-cut").length).toBeGreaterThan(0);
    expect(within(overview).getByText(/3 phiên · 3 do Wiii quản lý/i)).toBeTruthy();
  });

  it("groups every persisted session and searches all local history from Ctrl+K", () => {
    useNekoSessionStore.setState({
      sessions: {
        alpha: makeSession(
          "alpha",
          "Kiểm tra bản đồ",
          { path: "C:/work/alpha", name: "Project Alpha" },
          {
            messages: [{ id: "a1", role: "user", text: "phân tích hàng hải" }],
            updatedAt: 30,
          },
        ),
        beta: makeSession(
          "beta",
          "Gemini review",
          { path: "C:/work/beta", name: "Project Beta" },
          { agentId: "gemini", agentName: "Gemini CLI", updatedAt: 20 },
        ),
        legacy: makeSession("legacy", "Phiên cũ", null, { updatedAt: 10 }),
      },
      activeSessionId: null,
    });

    render(<NekoChillApp />);

    expect(screen.getAllByText("Project Alpha").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Project Beta").length).toBeGreaterThan(0);
    expect(screen.getByText("Legacy · Chưa gắn Project")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Mở phiên Kiểm tra bản đồ" })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Xoá phiên Phiên cũ" })).toBeTruthy();

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(screen.getByRole("dialog", { name: "Trung tâm lệnh Neko Chill" })).toBeTruthy();
    const commandSearch = screen.getByRole("searchbox", { name: "Tìm phiên hoặc lệnh",
    });
    fireEvent.change(commandSearch, { target: { value: "hàng hải" } });
    expect(screen.getByRole("option", { name: /Kiểm tra bản đồ.*Project Alpha/i })).toBeTruthy();
    expect(screen.queryByRole("option", { name: /Gemini review/i })).toBeNull();
  });

  it("routes provider controls and inserts agent slash commands", async () => {
    const setConfigOption = vi.fn(async () => {});
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên ACP",
          { path: "C:/work/neko", name: "Neko" },
          {
            status: "idle",
            statusDetail: undefined,
            launchProfile: {
              id: "chatgpt",
              provider: "chatgpt",
              model: "gpt-5.6-luna",
              active: true,
            },
            controls: [
              {
                id: "mode",
                label: "Chế độ",
                category: "mode",
                kind: "select",
                currentValue: "default",
                choices: [
                  { value: "default", label: "Default" },
                  { value: "plan", label: "Plan" },
                ],
              },
            ],
            commands: [{ name: "memory show", description: "Hiện bộ nhớ" }],
          },
        ),
      },
      activeSessionId: "active",
      setConfigOption,
    });

    render(<NekoChillApp />);

    const modeSelects = screen.getAllByLabelText("Chế độ");
    fireEvent.change(modeSelects[0], { target: { value: "plan" } });
    expect(setConfigOption).toHaveBeenCalledWith("mode", "plan");
    expect(screen.getAllByText("C:/work/neko").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/gpt-5\.6-luna/).length).toBeGreaterThan(0);

    const composer = screen.getByTestId("neko-composer-input");
    fireEvent.change(composer, { target: { value: "/memory" } });
    expect(screen.getByRole("listbox", { name: "Lệnh slash" })).toBeTruthy();
    expect(screen.getByRole("option", { name: /memory show.*Agent/i })).toBeTruthy();
    fireEvent.keyDown(composer, { key: "Enter" });
    expect((composer as HTMLTextAreaElement).value).toBe("/memory show");

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    const commandSearch = screen.getByRole("searchbox", { name: "Tìm phiên hoặc lệnh",
    });
    fireEvent.change(commandSearch, { target: { value: "memory" } });
    fireEvent.click(screen.getByRole("option", { name: /memory show.*Agent/i }));
    expect((composer as HTMLTextAreaElement).value).toBe("/memory show");
    await vi.waitFor(() => expect(document.activeElement).toBe(composer));
  });

  it("keeps navigation and inspector progressively disclosed", () => {
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên gọn gàng",
          { path: "C:/work/neko", name: "Neko" },
          { status: "idle", statusDetail: undefined },
        ),
      },
      activeSessionId: "active",
    });

    render(<NekoChillApp />);

    expect(screen.queryByTestId("session-inspector")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Mở thông tin phiên" }));
    expect(screen.getByTestId("session-inspector")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Ẩn cây dự án và phiên" }));
    expect(screen.queryByTestId("session-sidebar")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Hiện cây dự án và phiên" }));
    expect(screen.getByTestId("session-sidebar")).toBeTruthy();

    fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    expect(screen.queryByTestId("session-sidebar")).toBeNull();
    fireEvent.keyDown(window, { key: "b", metaKey: true });
    expect(screen.getByTestId("session-sidebar")).toBeTruthy();
  });

  it("opens, switches, closes, and dismisses the session workspace with Escape", async () => {
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên workspace",
          { path: "C:/work/neko", name: "Neko" },
          { status: "idle", statusDetail: undefined },
        ),
      },
      activeSessionId: "active",
    });

    render(<NekoChillApp />);
    const titleWorkspaceToggle = screen.getByTestId("session-workspace-toggle");
    expect(titleWorkspaceToggle.getAttribute("aria-label")).toBe("Mở workspace phiên");
    expect(titleWorkspaceToggle.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(titleWorkspaceToggle);
    expect(titleWorkspaceToggle.getAttribute("aria-label")).toBe("Ẩn workspace phiên");
    expect(titleWorkspaceToggle.getAttribute("aria-pressed")).toBe("true");
    expect(await screen.findByTestId("neko-workspace-pane")).toBeTruthy();
    const projectTools = screen.getByRole("navigation", { name: "Công cụ Project" });
    expect(within(projectTools).getByRole("button", { name: "Tệp" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByTestId("workspace-file-navigator")).toBeTruthy();

    fireEvent.click(within(projectTools).getByRole("button", { name: "Terminal" }));
    expect(within(projectTools).getByRole("button", { name: "Terminal" }).getAttribute("aria-pressed")).toBe("true");
    expect(await screen.findByText("Máy tính công việc của Neko")).toBeTruthy();
    expect(screen.queryByTestId("workspace-file-navigator")).toBeNull();
    fireEvent.click(within(projectTools).getByRole("button", { name: "Trình duyệt" }));
    expect(within(projectTools).getByRole("button", { name: "Trình duyệt" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByTestId("workspace-file-navigator")).toBeNull();
    fireEvent.click(within(projectTools).getByRole("button", { name: "Computer" }));
    expect(within(projectTools).getByRole("button", { name: "Computer" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByTestId("workspace-file-navigator")).toBeNull();
    fireEvent.click(within(projectTools).getByRole("button", { name: "Tệp" }));
    expect(screen.getByTestId("workspace-file-navigator")).toBeTruthy();

    fireEvent.keyDown(screen.getByRole("button", { name: "Đóng workspace" }), { key: "Escape" });
    expect(screen.queryByTestId("neko-workspace-pane")).toBeNull();
    expect(titleWorkspaceToggle.getAttribute("aria-pressed")).toBe("false");
    expect(document.activeElement).toBe(titleWorkspaceToggle);

    fireEvent.click(titleWorkspaceToggle);
    fireEvent.click(screen.getByRole("button", { name: "Đóng workspace" }));
    expect(screen.queryByTestId("neko-workspace-pane")).toBeNull();
  });

  it("keeps sidebar and workspace keyboard shortcuts independent", async () => {
    useNekoSessionStore.setState({ sessions: {
      active: makeSession("active", "Bàn làm việc", { path: "C:/work/neko", name: "Neko" }),
    }, activeSessionId: "active" });
    render(<NekoChillApp />);
    const sidebar = screen.getByTestId("neko-sidebar-toggle");
    const workspace = screen.getByTestId("session-workspace-toggle");
    fireEvent.keyDown(window, { key: "b", ctrlKey: true, altKey: true });
    expect(await screen.findByTestId("neko-workspace-pane")).toBeTruthy();
    expect(sidebar.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    expect(sidebar.getAttribute("aria-expanded")).toBe("false");
    expect(workspace.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(window, { key: "b", ctrlKey: true, altKey: true, isComposing: true });
    expect(workspace.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(window, { key: "b", metaKey: true, altKey: true });
    expect(workspace.getAttribute("aria-expanded")).toBe("false");
  });

  it("lets the navigation menu own Escape without closing the workspace", async () => {
    useNekoSessionStore.setState({ sessions: {
      active: makeSession("active", "Bàn làm việc", { path: "C:/work/neko", name: "Neko" }),
    }, activeSessionId: "active" });
    render(<NekoChillApp />);
    fireEvent.click(screen.getByTestId("session-workspace-toggle"));
    await screen.findByTestId("neko-workspace-pane");
    const trigger = screen.getByTestId("mode-switcher");
    fireEvent.click(trigger);
    const items = within(screen.getByRole("menu", { name: "Điều hướng Wiii" })).getAllByRole("menuitem");
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(items[1], { key: "End" });
    expect(document.activeElement).toBe(items.at(-1));
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(screen.getByTestId("neko-workspace-pane")).toBeTruthy();
  });

  it("gives an empty live session a useful, non-executing start state", () => {
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên mới",
          { path: "C:/work/neko", name: "Neko" },
          { status: "idle", statusDetail: undefined },
        ),
      },
      activeSessionId: "active",
    });

    render(<NekoChillApp />);

    expect(screen.getByText("Sẵn sàng trong Neko")).toBeTruthy();
    expect(screen.getByText(/Gõ \/ để xem lệnh/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Chèn gợi ý Kiểm tra dự án này" }));
    const composer = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    expect(composer.value).toBe("Kiểm tra dự án này và cho tôi biết điểm cần chú ý.");
  });

  it("shows in-flight durability states and disables duplicate actions", () => {
    const resolvePermission = vi.fn(async () => {});
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên đang lưu",
          { path: "C:/work/neko", name: "Neko" },
          {
            status: "dispatching",
            statusDetail: undefined,
            pendingPermission: {
              requestId: "perm-1",
              title: "Write(config.json)",
              options: [
                { optionId: "allow_once", label: "Cho phép", kind: "allow_once",
                },
                { optionId: "reject_once", label: "Từ chối", kind: "reject_once",
                },
              ],
            },
            resolvingPermissionId: "perm-1",
          },
        ),
      },
      activeSessionId: "active",
      resolvePermission,
    });

    render(<NekoChillApp />);

    expect(screen.getByText(/đang lưu & gửi/i)).toBeTruthy();
    expect(screen.getByText("Đang lưu quyết định…")).toBeTruthy();
    const allow = screen.getByRole("button", { name: "Cho phép" }) as HTMLButtonElement;
    const reject = screen.getByRole("button", { name: "Từ chối" }) as HTMLButtonElement;
    expect(allow.disabled).toBe(false);
    expect(reject.disabled).toBe(false);
    expect(allow.getAttribute("aria-disabled")).toBe("true");
    expect(reject.getAttribute("aria-disabled")).toBe("true");
    allow.focus();
    fireEvent.click(allow);
    expect(resolvePermission).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(allow);
    const composer = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    expect(composer.disabled).toBe(false);
    expect(composer.readOnly).toBe(true);
    expect(composer.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByRole("status").textContent).toBe("Đang lưu quyết định…");
  });

  it("shows cancel durability progress and blocks duplicate stop clicks", () => {
    const cancelTurn = vi.fn(async () => {});
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên đang dừng",
          { path: "C:/work/neko", name: "Neko" },
          {
            status: "streaming",
            cancelPending: true,
            pendingPermission: {
              requestId: "perm-cancel",
              title: "Write(config.json)",
              options: [{ optionId: "allow_once", label: "Cho phép", kind: "allow_once" }],
            },
          },
        ),
      },
      activeSessionId: "active",
      cancelTurn,
    });

    render(<NekoChillApp />);

    const cancel = screen.getByRole("button", { name: "Đang lưu yêu cầu dừng",
    });
    expect((cancel as HTMLButtonElement).disabled).toBe(false);
    expect(cancel.getAttribute("aria-disabled")).toBe("true");
    expect(cancel.getAttribute("aria-busy")).toBe("true");
    const allow = screen.getByRole("button", { name: "Cho phép" }) as HTMLButtonElement;
    expect(allow.disabled).toBe(false);
    expect(allow.getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByRole("status").textContent).toBe("Đang lưu yêu cầu dừng…");
    cancel.focus();
    fireEvent.click(cancel);
    expect(cancelTurn).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(cancel);
  });

  it("allows an exited session to send while keeping runtime controls locked", () => {
    const sendPrompt = vi.fn(async () => {});
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên đã dừng",
          { path: "C:/work/neko", name: "Neko" },
          {
            status: "exited",
            controls: [{
              id: "model",
              label: "Model",
              category: "model",
              kind: "select",
              currentValue: "stable",
              choices: [
                { value: "stable", label: "Stable" },
                { value: "preview", label: "Preview" },
              ],
            }],
          },
        ),
      },
      activeSessionId: "active",
      sendPrompt,
    });

    render(<NekoChillApp />);

    const composer = screen.getByTestId("neko-composer-input") as HTMLTextAreaElement;
    expect(composer.readOnly).toBe(false);
    expect((screen.getByRole("combobox", { name: "Model" }) as HTMLSelectElement).disabled)
      .toBe(true);
    fireEvent.change(composer, { target: { value: "khởi động lại" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi tin nhắn" }));
    expect(sendPrompt).toHaveBeenCalledWith("khởi động lại", expect.any(Function));
  });

  it("keeps the close action available when a session is in error", () => {
    const closeSession = vi.fn(async () => {});
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên cần phục hồi",
          { path: "C:/work/neko", name: "Neko" },
          {
            status: "error",
            statusDetail: "Runtime báo lỗi",
            runtime: {
              sessionId: "active",
              providerId: "neko",
              instanceId: "runtime-live",
              kind: "acp",
              capabilities: ["prompt", "cancel"],
              contextContinuity: "process",
              workspaceIsolation: "advisory",
            },
          },
        ),
      },
      activeSessionId: "active",
      closeSession,
    });

    render(<NekoChillApp />);
    fireEvent.click(screen.getByRole("button", { name: "Kết thúc" }));

    expect(closeSession).toHaveBeenCalledWith("active");
  });

  it("keeps a durability error without a runtime fail-closed", () => {
    useNekoSessionStore.setState({
      sessions: {
        active: makeSession(
          "active",
          "Phiên chưa lưu được",
          { path: "C:/work/neko", name: "Neko" },
          {
            status: "error",
            statusDetail: "Không thể lưu ngữ cảnh dự án",
            runtime: null,
          },
        ),
      },
      activeSessionId: "active",
    });

    render(<NekoChillApp />);

    expect(screen.queryByRole("button", { name: "Kết thúc" })).toBeNull();
  });

  it("opens the exact recent Project without creating an empty session", async () => {
    const createSession = vi.fn(async () => "created");
    const sendPrompt = vi.fn(async () => {});
    const agent = {
      id: "gemini",
      name: "Gemini CLI",
      version: "0.24.0",
      found: true,
      availability: "available",
      supportsProfiles: false,
    };
    useNekoAgentStore.setState({ agents: [agent], isLoading: false });
    useNekoProjectStore.setState({ projects: [{
      id: "recent-project",
      name: "project",
      roots: [{ path: "C:/Users/me/project", name: "project" }],
      preferredHarnessId: "gemini",
      createdAt: 1,
      updatedAt: 1,
    }] });
    useNekoSessionStore.setState({
      sessions: {
        recent: makeSession("recent", "Lịch sử", {
          path: "C:/Users/me/project",
          name: "project",
        }),
      },
      activeSessionId: null,
      createSession,
      sendPrompt,
    });

    render(<NekoChillApp />);

    fireEvent.click(screen.getByTestId("new-session"));
    expect(await screen.findByTestId("project-home")).toBeTruthy();
    expect(screen.getAllByText("C:/Users/me/project").length).toBeGreaterThan(0);
    expect(createSession).not.toHaveBeenCalled();
    expect(sendPrompt).not.toHaveBeenCalled();
  });

  it("dispatches the first prompt into the session it just created", async () => {
    const createSession = vi.fn(async () => "created");
    const sendPrompt = vi.fn(async () => {});
    const agent = {
      id: "gemini",
      name: "Gemini CLI",
      version: "0.24.0",
      found: true,
      availability: "available",
      supportsProfiles: false,
    };
    useNekoAgentStore.setState({ agents: [agent], isLoading: false });
    useNekoProjectStore.setState({ projects: [{
      id: "recent-project",
      name: "project",
      roots: [{ path: "C:/Users/me/project", name: "project" }],
      preferredHarnessId: "gemini",
      createdAt: 1,
      updatedAt: 1,
    }] });
    useNekoSessionStore.setState({
      sessions: {
        recent: makeSession("recent", "Lịch sử", {
          path: "C:/Users/me/project",
          name: "project",
        }),
      },
      activeSessionId: null,
      createSession,
      sendPrompt,
    });

    render(<NekoChillApp />);
    fireEvent.click(screen.getByTestId("new-session"));
    fireEvent.change(screen.getByRole("textbox", { name: "Lời nhắn đầu tiên" }), {
      target: { value: "  Kiểm tra authentication  " },
    });
    const start = screen.getByRole("button", { name: "Gửi và mở phiên" }) as HTMLButtonElement;
    await vi.waitFor(() => expect(start.disabled).toBe(false));
    fireEvent.click(start);

    await vi.waitFor(() => {
      expect(createSession).toHaveBeenCalledTimes(1);
      expect(sendPrompt).toHaveBeenCalledWith("Kiểm tra authentication");
    });
    expect(createSession.mock.invocationCallOrder[0])
      .toBeLessThan(sendPrompt.mock.invocationCallOrder[0]);
  });

  it("keeps unavailable harness details on Overview and blocks dispatch", async () => {
    useNekoAgentStore.setState({
      agents: [{
        id: "neko",
        name: "Neko Core",
        version: null,
        found: false,
        availability: "host_unsupported",
        supportsProfiles: true,
      }],
      isLoading: false,
    });
    useNekoSessionStore.setState({
      sessions: {
        recent: makeSession("recent", "Lịch sử", {
          path: "C:/Users/me/project",
          name: "project",
        }),
      },
      activeSessionId: null,
    });
    useNekoProjectStore.setState({ projects: [{
      id: "recent-project",
      name: "project",
      roots: [{ path: "C:/Users/me/project", name: "project" }],
      preferredHarnessId: null,
      createdAt: 1,
      updatedAt: 1,
    }] });

    render(<NekoChillApp />);
    expect(screen.getByText("Wiii chưa hỗ trợ chạy trên hệ điều hành này")).toBeTruthy();
    fireEvent.click(screen.getByTestId("new-session"));

    const harness = await screen.findByRole("combobox", { name: "Chọn Harness" }) as HTMLSelectElement;
    expect(harness.value).toBe("neko");
    expect((screen.getByRole("button", { name: "Gửi và mở phiên" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("routes Project recovery to the focused harness manager without leaking technical errors", async () => {
    const detect = vi.fn(async () => {});
    useNekoAgentStore.setState({
      agents: [],
      isLoading: false,
      error: "Không thể dò agent cục bộ: journal unavailable",
      detect,
    });
    useNekoSessionStore.setState({
      sessions: {
        recent: makeSession("recent", "Lịch sử", {
          path: "C:/Users/me/project",
          name: "project",
        }),
      },
      activeSessionId: null,
    });
    useNekoProjectStore.setState({ projects: [{
      id: "recent-project",
      name: "project",
      roots: [{ path: "C:/Users/me/project", name: "project" }],
      preferredHarnessId: null,
      createdAt: 1,
      updatedAt: 1,
    }] });

    render(<NekoChillApp />);
    fireEvent.click(screen.getByTestId("new-session"));
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Quản lý harness" }));
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Quản lý harness" }));
    expect(screen.getByRole("alert").textContent).toContain("Chưa kiểm tra được agent trên máy");
    fireEvent.click(screen.getByText("Chi tiết kiểm tra"));
    expect(screen.getByText(/journal unavailable/).closest("details")?.open).toBe(true);
    expect(screen.queryByText(/Đang dò agent/i)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    await vi.waitFor(() => expect(detect).toHaveBeenCalledTimes(2));
    expect(detect).toHaveBeenLastCalledWith("neko");
  });

  it("keeps healthy harnesses selectable when another safe probe fails", async () => {
    useNekoAgentStore.setState({
      agents: [
        {
          id: "neko",
          name: "Neko Core",
          version: "0.24.0",
          found: true,
          availability: "available",
          supportsProfiles: true,
        },
        {
          id: "gemini",
          name: "Gemini CLI",
          version: null,
          found: false,
          availability: "probe_failed",
          detail: "provider probe timed out",
          supportsProfiles: false,
        },
      ],
      isLoading: false,
      error: null,
    });
    useNekoSessionStore.setState({
      sessions: {
        recent: makeSession("recent", "Lịch sử", {
          path: "C:/Users/me/project",
          name: "project",
        }),
      },
      activeSessionId: null,
    });
    useNekoProjectStore.setState({ projects: [{
      id: "recent-project",
      name: "project",
      roots: [{ path: "C:/Users/me/project", name: "project" }],
      preferredHarnessId: "neko",
      createdAt: 1,
      updatedAt: 1,
    }] });

    render(<NekoChillApp />);
    fireEvent.click(screen.getByTestId("new-session"));

    const harness = await screen.findByRole("combobox", { name: "Chọn Harness" }) as HTMLSelectElement;
    expect(within(harness).getByRole("option", { name: "Neko Core" })).toBeTruthy();
    expect(within(harness).queryByRole("option", { name: "Gemini CLI" })).toBeNull();
    expect(screen.queryByText(/Không thể hoàn tất việc dò harness an toàn/)).toBeNull();
  });
});
