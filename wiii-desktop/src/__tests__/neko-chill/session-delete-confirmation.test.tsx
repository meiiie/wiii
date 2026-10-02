import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionSidebar } from "@/neko-chill/components/SessionSidebar";
import { useNekoSessionStore, type NekoSession } from "@/neko-chill/stores/neko-session-store";

const originalDelete = useNekoSessionStore.getState().deleteSession;
const title = "Phiên cần xác nhận";
const targetId = "delete-target-123";

function session(id: string, name: string, overrides: Partial<NekoSession> = {}): NekoSession {
  return {
    id, title: name, agentId: "neko", agentName: "Neko Core", workspace: null,
    launchProfile: null, controls: [], commands: [], pendingControlId: null,
    createdAt: 1, updatedAt: 1, lastActivityAt: 1, status: "exited", statusDetail: "Đã lưu",
    messages: [], events: [], eventHighWaterMark: 0, runtime: null,
    pendingPermission: null, resolvingPermissionId: null,
    cancelPending: false, closePending: false, deletePending: false, ...overrides,
  };
}

function mount() {
  return render(<SessionSidebar
    overviewActive={false} coworkerActive={false} projects={[]} selectedProjectId={null}
    externalSessionCount={0} onShowOverview={vi.fn()} onShowCoworker={vi.fn()}
    onShowConnections={vi.fn()} onNewSession={vi.fn()} onCreateProject={vi.fn()}
    onSelectProject={vi.fn()} onEditProject={vi.fn()} onOpenSession={vi.fn()}
  />);
}

function open(name = title) {
  const opener = screen.getByRole("button", { name: `Xoá phiên ${name}`.trim() });
  opener.focus();
  fireEvent.click(opener);
  return { opener, dialog: screen.getByRole("dialog", { name: "Xóa lịch sử phiên?" }) };
}

function deferred() {
  let resolve!: () => void;
  let reject!: (cause: Error) => void;
  const promise = new Promise<void>((accept, decline) => { resolve = accept; reject = decline; });
  return { promise, resolve, reject };
}

function remove(id: string) {
  useNekoSessionStore.setState((state) => {
    const sessions = { ...state.sessions };
    delete sessions[id];
    return { sessions, activeSessionId: state.activeSessionId === id ? null : state.activeSessionId };
  });
}

beforeEach(() => {
  useNekoSessionStore.setState({
    sessions: { [targetId]: session(targetId, title), other: session("other", "Phiên khác") },
    activeSessionId: targetId, deleteSession: vi.fn(async () => {}),
  });
});

afterEach(() => {
  cleanup();
  useNekoSessionStore.setState({ sessions: {}, activeSessionId: null, deleteSession: originalDelete });
});

describe("Session delete confirmation", () => {
  it("opens a named confirmation for the exact selected session and never deletes on the first click", () => {
    mount();
    const { dialog } = open();
    const body = within(dialog);
    expect(useNekoSessionStore.getState().deleteSession).not.toHaveBeenCalled();
    expect(body.getByTestId("session-delete-title").textContent).toBe(title);
    expect(body.getByText(`ID: ${targetId}`)).toBeTruthy();
    expect(body.getByText(/chọn Kết thúc/)).toBeTruthy();
    expect(body.getByText(/Không thể hoàn tác/)).toBeTruthy();
    expect(document.activeElement).toBe(body.getByRole("button", { name: "Hủy" }));
  });

  it.each(["cancel", "escape", "native-cancel", "backdrop"])("%s closes without deleting and restores the opener", async (method) => {
    mount();
    const { dialog, opener } = open();
    if (method === "cancel") fireEvent.click(within(dialog).getByRole("button", { name: "Hủy" }));
    else if (method === "escape") fireEvent.keyDown(dialog, { key: "Escape" });
    else if (method === "native-cancel") fireEvent(dialog, new Event("cancel", { bubbles: false, cancelable: true }));
    else fireEvent.mouseDown(screen.getByTestId("session-delete-dialog").parentElement!);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(useNekoSessionStore.getState().deleteSession).not.toHaveBeenCalled();
    await waitFor(() => expect(document.activeElement).toBe(opener));
  });

  it("traps Tab and Shift+Tab within the confirmation controls", () => {
    mount();
    const { dialog } = open();
    const cancel = within(dialog).getByRole("button", { name: "Hủy" });
    const confirm = within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" });
    fireEvent.keyDown(cancel, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(confirm);
    fireEvent.keyDown(confirm, { key: "Tab" });
    expect(document.activeElement).toBe(cancel);
  });

  it("dispatches a double confirm only once and prevents dismissing while deletion is pending", async () => {
    const work = deferred();
    const deleteSession = vi.fn(() => work.promise);
    useNekoSessionStore.setState({ deleteSession });
    mount();
    const { dialog } = open();
    const confirm = within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" });
    act(() => {
      fireEvent.click(confirm);
      fireEvent.click(confirm);
    });
    expect(deleteSession).toHaveBeenCalledExactlyOnceWith(targetId);
    expect((within(dialog).getByRole("button", { name: "Đang xóa…" }) as HTMLButtonElement).disabled).toBe(true);
    expect((within(dialog).getByRole("button", { name: "Hủy" }) as HTMLButtonElement).disabled).toBe(true);
    expect(dialog.getAttribute("aria-busy")).toBe("true");
    expect(document.activeElement).toBe(dialog);
    fireEvent.keyDown(dialog, { key: "Escape" });
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    fireEvent.mouseDown(screen.getByTestId("session-delete-dialog").parentElement!);
    expect(screen.getByRole("dialog")).toBe(dialog);
    await act(async () => work.resolve());
    expect(deleteSession).toHaveBeenCalledTimes(1);
    expect(within(dialog).getByRole("alert").textContent).toContain("Chưa xóa được phiên");
  });

  it("closes after verified removal and focuses the new-session sidebar action", async () => {
    const deleteSession = vi.fn(async (id: string) => remove(id));
    useNekoSessionStore.setState({ deleteSession });
    mount();
    const { dialog } = open();
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" })));
    expect(deleteSession).toHaveBeenCalledExactlyOnceWith(targetId);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: `Mở phiên ${title}` })).toBeNull();
    expect(screen.getByRole("button", { name: "Mở phiên Phiên khác" })).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("new-session")));
  });

  it("keeps the dialog and row when the store reports a swallowed cleanup failure, then allows retry", async () => {
    const deleteSession = vi.fn(async (id: string) => {
      const current = useNekoSessionStore.getState().sessions[id];
      useNekoSessionStore.setState({ sessions: {
        ...useNekoSessionStore.getState().sessions,
        [id]: { ...current, status: "error", statusDetail: "Runtime chưa đóng sạch.", deletePending: false },
      } });
    });
    useNekoSessionStore.setState({ deleteSession });
    mount();
    const { dialog } = open();
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" })));
    expect(within(dialog).getByRole("alert").textContent).toContain("Lịch sử vẫn được giữ. Runtime chưa đóng sạch.");
    expect(screen.getByRole("button", { name: `Mở phiên ${title}` })).toBeTruthy();
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Hủy" }));
    deleteSession.mockImplementationOnce(async (id) => remove(id));
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" })));
    expect(deleteSession).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows a localized rejection and retains the selected row and history", async () => {
    const deleteSession = vi.fn().mockRejectedValueOnce(new Error("Storage denied"));
    useNekoSessionStore.setState({ deleteSession });
    mount();
    const { dialog } = open();
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" })));
    expect(within(dialog).getByRole("alert").textContent).toContain("Chưa xóa được phiên. Lịch sử vẫn được giữ. Storage denied");
    expect(screen.getByRole("button", { name: `Mở phiên ${title}` })).toBeTruthy();
    expect((within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("never switches the captured target when active session or its displayed title changes", async () => {
    const deleteSession = vi.fn(async () => {});
    useNekoSessionStore.setState({ deleteSession });
    mount();
    const { dialog } = open();
    act(() => useNekoSessionStore.setState({
      activeSessionId: "other",
      sessions: { ...useNekoSessionStore.getState().sessions, [targetId]: session(targetId, "Tiêu đề đã đổi") },
    }));
    expect(within(dialog).getByTestId("session-delete-title").textContent).toBe(title);
    expect(within(dialog).getByText(`ID: ${targetId}`)).toBeTruthy();
    expect(document.activeElement).toBe(within(dialog).getByRole("button", { name: "Hủy" }));
    await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" })));
    expect(deleteSession).toHaveBeenCalledExactlyOnceWith(targetId);
    expect(useNekoSessionStore.getState().sessions.other).toBeTruthy();
  });

  it("disables confirmation if the source session disappears before confirmation", async () => {
    mount();
    const { dialog } = open();
    act(() => remove(targetId));
    const confirm = within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    expect(within(dialog).getByRole("status").textContent).toContain("Phiên này không còn");
    fireEvent.click(confirm);
    expect(useNekoSessionStore.getState().deleteSession).not.toHaveBeenCalled();
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("new-session")));
  });

  it.each(["resolve", "reject"] as const)("verifies source removal after an asynchronous %s before completing", async (outcome) => {
    const work = deferred();
    const deleteSession = vi.fn(() => work.promise);
    useNekoSessionStore.setState({ deleteSession });
    mount();
    const { dialog } = open();
    fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" }));
    act(() => remove(targetId));
    await act(async () => {
      if (outcome === "resolve") work.resolve();
      else work.reject(new Error("Late request failure"));
    });
    expect(deleteSession).toHaveBeenCalledExactlyOnceWith(targetId);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(useNekoSessionStore.getState().sessions.other).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByTestId("new-session")));
  });

  it("honors an existing lifecycle deletion lock without dispatching a second delete", () => {
    useNekoSessionStore.setState({ sessions: { [targetId]: session(targetId, title, { deletePending: true, status: "stopping" }) } });
    mount();
    const { dialog } = open();
    expect(dialog.getAttribute("aria-busy")).toBe("true");
    expect(document.activeElement).toBe(dialog);
    const confirm = within(dialog).getByRole("button", { name: "Đang xóa…" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(confirm);
    expect(useNekoSessionStore.getState().deleteSession).not.toHaveBeenCalled();
  });

  it("retains a complete long title and session id without truncating the confirmation", () => {
    const longTitle = "Phiên phân tích dữ liệu rất dài / ".repeat(12);
    useNekoSessionStore.setState({ sessions: { [targetId]: session(targetId, longTitle) } });
    mount();
    const { dialog } = open(longTitle);
    const label = within(dialog).getByTestId("session-delete-title");
    expect(label.textContent).toBe(longTitle);
    expect(label.className).toContain("overflow-wrap:anywhere");
    expect(label.className).not.toContain("truncate");
  });

  it("does not perform further UI work after the sidebar is unmounted during deletion", async () => {
    const work = deferred();
    const deleteSession = vi.fn(() => work.promise);
    useNekoSessionStore.setState({ deleteSession });
    const view = mount();
    const { dialog } = open();
    fireEvent.click(within(dialog).getByRole("button", { name: "Xóa phiên và lịch sử" }));
    view.unmount();
    await act(async () => work.reject(new Error("Late failure")));
    expect(deleteSession).toHaveBeenCalledExactlyOnceWith(targetId);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
