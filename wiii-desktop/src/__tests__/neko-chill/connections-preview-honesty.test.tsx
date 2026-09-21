import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import NekoChillApp from "@/neko-chill/NekoChillApp";
import {
  CONNECTIONS_UNAVAILABLE_IN_CHILL_PREVIEW_VI,
  explainConnectionsUnavailableInPreview,
} from "@/neko-chill/connections-preview";
import { useNekoAgentStore } from "@/neko-chill/stores/neko-agent-store";
import { useNekoSessionStore } from "@/neko-chill/stores/neko-session-store";
import { useNekoWorkspaceStore } from "@/neko-chill/stores/neko-workspace-store";
import { useNekoProjectStore } from "@/neko-chill/stores/neko-project-store";

vi.mock("@/neko-coworker/NekoCoworkerHome", () => ({
  NekoCoworkerHome: () => <div data-testid="neko-coworker-home">Coworker workstation</div>,
}));

describe("connections preview honesty", () => {
  const hydrateProjects = useNekoProjectStore.getState().hydrate;

  beforeEach(() => {
    vi.stubGlobal("alert", vi.fn());
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
      hydrate: hydrateProjects,
    });
  });

  it("explains instead of silently no-opping when chill preview has no host wiring", () => {
    explainConnectionsUnavailableInPreview();
    expect(window.alert).toHaveBeenCalledWith(CONNECTIONS_UNAVAILABLE_IN_CHILL_PREVIEW_VI);
    expect(String(vi.mocked(window.alert).mock.calls[0][0])).toMatch(
      /trình duyệt|Wiii Service|preview=wiii-connect/i,
    );
  });

  it("surfaces honesty from sidebar Kết nối when NekoChillApp is mounted bare", () => {
    render(<NekoChillApp />);

    fireEvent.click(screen.getByTestId("neko-connections-link"));

    expect(window.alert).toHaveBeenCalledWith(CONNECTIONS_UNAVAILABLE_IN_CHILL_PREVIEW_VI);
  });

  it("still calls a parent-provided connections opener (production / Workbench)", () => {
    const onOpenConnections = vi.fn();
    render(<NekoChillApp onOpenConnections={onOpenConnections} />);

    fireEvent.click(screen.getByTestId("neko-connections-link"));

    expect(onOpenConnections).toHaveBeenCalledTimes(1);
    expect(window.alert).not.toHaveBeenCalled();
  });

  it("falls through to onOpenManaged when only managed is wired (ADE)", () => {
    const onOpenManaged = vi.fn();
    render(<NekoChillApp onOpenManaged={onOpenManaged} />);

    fireEvent.click(screen.getByTestId("neko-connections-link"));

    expect(onOpenManaged).toHaveBeenCalledTimes(1);
    expect(window.alert).not.toHaveBeenCalled();
  });
});
