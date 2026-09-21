import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { NekoSession } from "@/neko-chill/stores/neko-session-store";
import { ProviderSessionCatalogPanel } from "@/neko-chill/components/ProviderSessionCatalogPanel";
import NekoChillApp from "@/neko-chill/NekoChillApp";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useNekoSessionStore } from "@/neko-chill/stores/neko-session-store";
import { useNekoWorkspaceStore } from "@/neko-chill/stores/neko-workspace-store";
import { useNekoProjectStore } from "@/neko-chill/stores/neko-project-store";

vi.mock("@/neko-coworker/NekoCoworkerHome", () => ({
  NekoCoworkerHome: () => <div data-testid="neko-coworker-home">Coworker workstation</div>,
}));

function managed(): NekoSession {
  return {
    id: "managed-stopped",
    agentId: "neko",
    agentName: "Neko Core",
    title: "Stopped seed session",
    createdAt: 1,
    updatedAt: Date.UTC(2026, 8, 21, 15, 39),
    workspace: { path: "/tmp/wiii-session-open-seed", name: "session-open-seed" },
    projectId: "proj-seed",
    launchProfile: { id: "glm", provider: "zai", model: "glm-5.3", active: true },
    backendSessionId: null,
    controls: [],
    commands: [],
    pendingControlId: null,
    lastActivityAt: 1,
    status: "exited",
    statusDetail: "Đã dừng",
    messages: [
      { id: "u1", role: "user", text: "hello seed" },
      { id: "a1", role: "assistant", text: "seed reply" },
    ],
    events: [],
    eventHighWaterMark: 0,
    runtime: null,
    pendingPermission: null,
    resolvingPermissionId: null,
    cancelPending: false,
    closePending: false,
    deletePending: false,
  };
}

describe("session-open click UX (Overview catalog)", () => {
  it("clicking Overview session title opens managed transcript", () => {
    const onOpenManaged = vi.fn();
    render(
      <ProviderSessionCatalogPanel
        managedSessions={[managed()]}
        providerSessions={[]}
        providerCatalogs={[]}
        providerNames={new Map([["neko", "Neko Core"]])}
        discoveryLoading={false}
        onRefresh={vi.fn()}
        onOpenManaged={onOpenManaged}
        onImportProvider={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mở phiên Stopped seed session" }));
    expect(onOpenManaged).toHaveBeenCalledTimes(1);
    expect(onOpenManaged).toHaveBeenCalledWith("managed-stopped");

    fireEvent.click(screen.getByRole("button", { name: "Mở" }));
    expect(onOpenManaged).toHaveBeenCalledTimes(2);
  });

  it("sidebar session row click opens transcript from Overview idle state", () => {
    useNekoAgentStore.setState({
      agents: [],
      isLoading: false,
      error: null,
      detect: vi.fn(async () => {}),
    });
    useNekoWorkspaceStore.setState({ sessions: {} });
    useNekoProjectStore.setState({
      projects: [{
        id: "proj-seed",
        name: "session-open-seed",
        roots: [{ path: "/tmp/wiii-session-open-seed", name: "session-open-seed" }],
        preferredHarnessId: null,
        createdAt: 1,
        updatedAt: 1,
      }],
      hydrated: true,
      hydrating: false,
      error: null,
      hydrate: vi.fn(async () => {}),
    });
    useNekoSessionStore.setState({
      sessions: { "managed-stopped": managed() },
      activeSessionId: null,
      hydrated: true,
      hydrating: false,
      hydrationError: null,
      hydrate: vi.fn(async () => {}),
    });

    render(<NekoChillApp />);

    expect(screen.getByTestId("neko-overview")).toBeTruthy();
    const sidebar = screen.getByTestId("session-sidebar");
    const sidebarOpen = Array.from(sidebar.querySelectorAll("button")).find(
      (b) => b.getAttribute("aria-label") === "Mở phiên Stopped seed session",
    );
    expect(sidebarOpen).toBeTruthy();
    fireEvent.click(sidebarOpen!);
    expect(useNekoSessionStore.getState().activeSessionId).toBe("managed-stopped");
  });
});
