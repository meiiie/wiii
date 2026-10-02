import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionSidebar } from "@/neko-chill/components/SessionSidebar";
import { useNekoSessionStore } from "@/neko-chill/stores/neko-session-store";
import type { NekoProject } from "@/neko-chill/stores/neko-project-store";
const project = { id: "p", name: "Alpha", roots: [{ name: "Alpha", path: "/alpha" }], createdAt: 1, updatedAt: 1 } as NekoProject;
function mount() { return render(<SessionSidebar projects={[project]} selectedProjectId={null} overviewActive={false} coworkerActive={false} externalSessionCount={0} onShowOverview={vi.fn()} onShowCoworker={vi.fn()} onShowConnections={vi.fn()} onNewSession={vi.fn()} onCreateProject={vi.fn()} onSelectProject={vi.fn()} onEditProject={vi.fn()} onOpenSession={vi.fn()} />); }
beforeEach(() => useNekoSessionStore.setState({ sessions: {}, activeSessionId: null }));
describe("sidebar search feedback", () => {
  it("shows a recovery action for no matches even with existing projects", () => {
    mount(); const search = screen.getByRole("searchbox"); fireEvent.change(search, { target: { value: "missing" } });
    expect(screen.getByRole("status").textContent).toContain("Không tìm thấy");
    fireEvent.click(screen.getByRole("button", { name: "Xóa bộ lọc" })); expect(document.activeElement).toBe(search);
    expect(screen.getByTestId("project-p")).toBeTruthy();
  });
  it("Escape clears the filter without navigating away", () => {
    mount(); const search = screen.getByRole("searchbox"); search.focus(); fireEvent.change(search, { target: { value: "missing" } });
    fireEvent.keyDown(search, { key: "Escape" }); expect((search as HTMLInputElement).value).toBe(""); expect(document.activeElement).toBe(search); expect(screen.getByTestId("project-p")).toBeTruthy();
  });
});
