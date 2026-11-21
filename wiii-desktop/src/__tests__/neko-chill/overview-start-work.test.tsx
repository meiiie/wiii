import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { NekoOverview } from "@/neko-chill/components/NekoOverview";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";

const props = {
  sessions: [], agents: [], providerCatalogs: [], discoveryLoading: false,
  onNewSession: vi.fn(), onOpenSession: vi.fn(), onRefreshDiscovery: vi.fn(),
  onImportProviderSession: vi.fn(async () => {}),
};

beforeEach(() => {
  vi.clearAllMocks();
  useNekoAgentStore.setState({ agents: [], isLoading: false, error: null });
});

describe("desktop home actions", () => {
  it("starts chat without routing through project creation", () => {
    const chat = vi.fn();
    const create = vi.fn();
    render(<NekoOverview {...props} onQuickChat={chat} onCreateProject={create} />);
    fireEvent.click(screen.getByTestId("overview-quick-chat"));
    expect(chat).toHaveBeenCalledOnce();
    expect(create).not.toHaveBeenCalled();
    expect(props.onNewSession).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("overview-create-first-project"));
    expect(create).toHaveBeenCalledOnce();
  });

  it("opens a recent project directly and omits scratch workspaces", () => {
    const open = vi.fn();
    const project = { id: "project", name: "Wiii", roots: [{ name: "wiii", path: "/work/wiii" }], preferredHarnessId: null, createdAt: 1, updatedAt: 1 };
    render(<NekoOverview {...props} projects={[project, { ...project, id: "scratch", name: "Private scratch", roots: [{ name: "scratch", path: "/scratch", kind: "scratch" }] }]} projectCount={1} onOpenProject={open} />);
    fireEvent.click(screen.getByRole("button", { name: "Wiii /work/wiii" }));
    expect(open).toHaveBeenCalledWith("project");
    expect(screen.queryByText("Private scratch")).toBeNull();
  });

  it("opens agent details before moving focus on a setup request", () => {
    const { rerender } = render(<NekoOverview {...props} />);
    const details = screen.getByTestId("overview-agent-details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    rerender(<NekoOverview {...props} harnessFocusRequest={1} />);
    expect(details.open).toBe(true);
    expect(document.activeElement).toBe(screen.getByRole("heading", { name: "Quản lý agent" }));
  });

  it("blocks duplicate quick-chat actions while preparing", () => {
    const chat = vi.fn();
    render(<NekoOverview {...props} onQuickChat={chat} quickChatPending />);
    fireEvent.click(screen.getByTestId("overview-quick-chat"));
    expect(chat).not.toHaveBeenCalled();
  });

  it("keeps session scan recovery available when discovery is empty", () => {
    render(<NekoOverview {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Quét lại" }));
    expect(props.onRefreshDiscovery).toHaveBeenCalledOnce();
  });
});
