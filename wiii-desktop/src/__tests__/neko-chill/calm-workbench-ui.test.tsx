import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectHome } from "@/neko-chill/components/ProjectHome";
import { NekoWorkspacePane } from "@/neko-chill/components/NekoWorkspacePane";
import { clearNekoComposerDraft } from "@/neko-chill/composer-drafts";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useNekoProjectStore } from "@/neko-chill/stores/neko-project-store";
import { useNekoSessionStore } from "@/neko-chill/stores/neko-session-store";
import { useNekoWorkspaceStore } from "@/neko-chill/stores/neko-workspace-store";

vi.mock("@/neko-computer/NekoComputerSurface", () => ({
  NekoComputerSurface: ({ mode }: { mode: string }) => <div data-testid="computer-surface">{mode}</div>,
}));

const workspace = { name: "workspace", path: "C:/ux-fixtures/project" };
const project = {
  id: "calm-ui", name: "Wiii", roots: [workspace], preferredHarnessId: "gemini",
  createdAt: 1, updatedAt: 1,
};

describe("calm workbench interaction contracts", () => {
  beforeEach(() => {
    clearNekoComposerDraft(`project:${project.id}`);
    useNekoProjectStore.setState({ projects: [project], hydrated: true });
    useNekoAgentStore.setState({
      agents: [{ id: "gemini", name: "Gemini CLI", found: true, version: "test", availability: "available", supportsProfiles: false }],
      isLoading: false, error: null, detect: vi.fn(async () => {}),
    });
    useNekoSessionStore.setState({
      createSession: vi.fn(async () => "created"), sendPrompt: vi.fn(async () => {}),
    });
    useNekoWorkspaceStore.setState({ sessions: {}, refresh: vi.fn(async () => {}) });
    useNekoWorkspaceStore.getState().ensureSession(project.id);
    useNekoWorkspaceStore.getState().toggle(project.id);
  });

  it.each([
    ["IME composition", { isComposing: true }],
    ["IME completion key", { keyCode: 229 }],
    ["multiline input", { shiftKey: true }],
  ])("does not send a draft during %s", async (_label, key) => {
    render(<ProjectHome project={project} />);
    const input = screen.getByRole("textbox", { name: "Lời nhắn đầu tiên" });
    fireEvent.change(input, { target: { value: "Tiếng Việt đang được nhập" } });
    await vi.waitFor(() => expect((screen.getByRole("button", { name: "Gửi và mở phiên" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.keyDown(input, { key: "Enter", ...key });
    expect(useNekoSessionStore.getState().createSession).not.toHaveBeenCalled();
    expect((input as HTMLTextAreaElement).value).toBe("Tiếng Việt đang được nhập");
  });

  it("still sends an intentional Enter once", async () => {
    render(<ProjectHome project={project} />);
    const input = screen.getByRole("textbox", { name: "Lời nhắn đầu tiên" });
    fireEvent.change(input, { target: { value: "Kiểm tra dự án" } });
    await vi.waitFor(() => expect((screen.getByRole("button", { name: "Gửi và mở phiên" }) as HTMLButtonElement).disabled).toBe(false));
    await act(async () => { fireEvent.keyDown(input, { key: "Enter" }); });
    await vi.waitFor(() => expect(useNekoSessionStore.getState().sendPrompt).toHaveBeenCalledWith("Kiểm tra dự án"));
    expect(useNekoSessionStore.getState().createSession).toHaveBeenCalledTimes(1);
  });

  function setWorkspaceFailure(loading = false) {
    const store = useNekoWorkspaceStore.getState();
    useNekoWorkspaceStore.setState({ sessions: {
      ...store.sessions,
      [project.id]: { ...store.sessions[project.id], loading, error: "QA fixture: filesystem unavailable" },
    } });
  }

  it.each(["computer", "browser", "terminal"] as const)("does not mask %s with a filesystem error or spinner", (mode) => {
    setWorkspaceFailure(true);
    render(<NekoWorkspacePane target={{ id: project.id, projectId: project.id, workspace }} requestedSurface={mode} />);
    expect(screen.getByTestId("computer-surface").textContent).toBe(mode);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText("Đang mở nội dung…")).toBeNull();
    expect(screen.queryByTestId("workspace-file-navigator")).toBeNull();
  });

  it("offers explicit retry and keeps error details inspectable", () => {
    setWorkspaceFailure();
    render(<NekoWorkspacePane target={{ id: project.id, projectId: project.id, workspace }} />);
    expect(screen.getByText("Chưa đọc được cây tệp.")).toBeTruthy();
    expect(screen.queryByText("Không tìm thấy tệp phù hợp.")).toBeNull();
    const alert = screen.getByRole("alert");
    expect(within(alert).getByText("QA fixture: filesystem unavailable").closest("details")?.open).toBe(false);
    fireEvent.click(within(alert).getByRole("button", { name: "Thử đọc lại" }));
    expect(useNekoWorkspaceStore.getState().refresh).toHaveBeenCalledWith(project.id, workspace, { force: true });
  });

  it("does not dismiss the workspace while Escape belongs to file search", () => {
    const onClose = vi.fn();
    render(<NekoWorkspacePane target={{ id: project.id, projectId: project.id, workspace }} onClose={onClose} />);
    fireEvent.keyDown(screen.getByRole("textbox", { name: "Tìm tệp trong workspace" }), { key: "Escape" });
    expect(useNekoWorkspaceStore.getState().sessions[project.id].open).toBe(true);
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole("button", { name: "Đóng workspace" }), { key: "Escape" });
    expect(useNekoWorkspaceStore.getState().sessions[project.id].open).toBe(false);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not label failed change discovery as a clean workspace", () => {
    setWorkspaceFailure();
    render(<NekoWorkspacePane target={{ id: project.id, projectId: project.id, workspace }} requestedSurface="changes" />);
    fireEvent.click(within(screen.getByRole("navigation", { name: "Công cụ Project" })).getByRole("button", { name: "Thay đổi" }));
    act(() => setWorkspaceFailure());
    expect(screen.getByText("Chưa kiểm tra được thay đổi.")).toBeTruthy();
    expect(screen.queryByText("Workspace đang sạch.")).toBeNull();
  });
});
