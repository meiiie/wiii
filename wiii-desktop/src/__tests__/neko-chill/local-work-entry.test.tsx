vi.mock("@/neko-chill/stores/neko-outbox-store", () => ({ startNekoOutbox: vi.fn(() => vi.fn()) }));
/** Real Workbench host boundary and ADE surface; runtime dispatch is observed
 * through inert store/control mocks, never a browser process bypass.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { WorkbenchHost } from "@/workbench/host";

const fixture = vi.hoisted(() => ({
  stopReaper: vi.fn(),
  startReaper: vi.fn(),
  disposeRuntimes: vi.fn(async () => {}),
  storage: new Map<string, unknown>(),
  graph: { projects: [], workspaces: [], tasks: [], specs: [], runs: [], environments: [], agentSessions: [] },
  hydrateWork: vi.fn(async () => {}),
  hydrateSessions: vi.fn(async () => {}),
  createTaskRun: vi.fn(async () => {}),
  createSession: vi.fn(async () => "must-not-launch"),
  spawnProvider: vi.fn(async () => {}),
  setActiveSession: vi.fn(),
  sessions: {} as Record<string, {
    status: string; cancelPending: boolean; closePending: boolean;
    pendingPermission: object | null; resolvingPermissionId: string | null;
    runtime?: { instanceId: string } | null;
  }>,
  cancelTurn: vi.fn(async () => {}),
  closeSession: vi.fn(async () => {}),
}));
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, fallback: unknown) => fixture.storage.get(`${store}:${key}`) ?? fallback),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => { fixture.storage.set(`${store}:${key}`, value); }),
  deleteStore: vi.fn(async () => {}), clearStore: vi.fn(async () => {}),
}));
vi.mock("@/workbench/WorkbenchBoot", () => ({ BootSplash: ({ label }: { label: string }) => <div role="status">{label}</div> }));
vi.mock("@/components/layout/TitleBar", () => ({ TitleBar: () => <div /> }));
vi.mock("@/components/common/WiiiMark", () => ({ WiiiMark: () => <span /> }));
vi.mock("@/neko/control-client", () => ({ getNekoControlClient: () => ({
  listSessions: async () => [], spawnProvider: fixture.spawnProvider,
}) }));
vi.mock("@/ade/store", () => {
  const state = { graph: fixture.graph, hydrate: fixture.hydrateWork,
    hydrated: true, error: null, createTaskRun: fixture.createTaskRun };
  return { useAdeWorkStore: Object.assign((select: (value: typeof state) => unknown) => select(state), {
    getState: () => state,
  }) };
});
vi.mock("@/neko-chill/stores/neko-session-store", () => {
  const state = { sessions: fixture.sessions, hydrate: fixture.hydrateSessions,
    createSession: fixture.createSession, setActiveSession: fixture.setActiveSession,
    cancelTurn: fixture.cancelTurn, closeSession: fixture.closeSession };
  return { startIdleReaper: fixture.startReaper, disposeAllNekoRuntimes: fixture.disposeRuntimes, useNekoSessionStore: Object.assign((select: (value: typeof state) => unknown) => select(state), {
    getState: () => state,
  }) };
});
vi.mock("@/neko-chill/NekoChillApp", () => ({
  default: ({ onOpenManaged, onOpenConnections, onOpenWork, showWorkNavigation }: {
    onOpenManaged?: () => void; onOpenConnections?: () => void;
    onOpenWork?: () => void; showWorkNavigation?: boolean;
  }) => <div data-testid="local-neko">
    <button type="button" onClick={onOpenManaged}>Managed</button>
    <button type="button" onClick={onOpenConnections}>Connections</button>
    {showWorkNavigation ? <button type="button" onClick={onOpenWork}>Mở bản thử nghiệm Công việc</button> : null}
  </div>,
}));
vi.mock("@/workbench/WiiiCloudApp", () => ({
  default: ({ onOpenLocal }: { onOpenLocal?: () => void }) => <div data-testid="managed">
    {onOpenLocal ? <button type="button" onClick={onOpenLocal}>Back local</button> : null}
  </div>,
}));

import { WorkbenchGate } from "@/App";
import { useWorkbenchStore } from "@/workbench/workbench-store";
import { useUIStore } from "@/stores/ui-store";

const desktop: WorkbenchHost = { kind: "desktop", capabilities: {
  localProcess: true, localWorkspace: true, nativeWindow: true,
  tray: true, secureSecretStore: false, remoteRuntime: true,
} };
const web: WorkbenchHost = { kind: "web", capabilities: {
  ...desktop.capabilities, localProcess: false, localWorkspace: false,
  nativeWindow: false, tray: false,
} };
async function nativeLocal() {
  render(<WorkbenchGate host={desktop} />);
  await screen.findByTestId("local-neko");
}

describe("normal local Work entry preserves Workbench boundaries", () => {
  beforeEach(() => {
    fixture.storage.clear(); vi.clearAllMocks();
    fixture.startReaper.mockReturnValue(fixture.stopReaper);
    for (const id of Object.keys(fixture.sessions)) delete fixture.sessions[id];
    useWorkbenchStore.setState({ surface: "local", isLoaded: false });
    useUIStore.setState({ activeView: "chat", wiiiConnectFocusProvider: null });
    Object.defineProperty(window, "__TAURI_INTERNALS__", { value: {}, configurable: true });
  });
  afterEach(() => { cleanup(); delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__; });

  it("keeps native entry on Neko and opens the existing Work beta only by an explicit action", async () => {
    await nativeLocal();
    expect(screen.queryByTestId("wiii-ade-app")).toBeNull();
    expect(fixture.hydrateWork).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Mở bản thử nghiệm Công việc" }));
    await screen.findByTestId("work-home");
    expect(screen.getByTestId("wiii-ade-app")).toBeTruthy();
    expect(fixture.hydrateWork).toHaveBeenCalledOnce();
    expect(fixture.createTaskRun).not.toHaveBeenCalled();
    expect(fixture.disposeRuntimes).not.toHaveBeenCalled();
    expect(fixture.createSession).not.toHaveBeenCalled();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });

  it("keeps Managed and Gmail Connections routing through the host boundary, including ADE's manual Neko view", async () => {
    await nativeLocal();
    fireEvent.click(screen.getByRole("button", { name: "Managed" }));
    await screen.findByTestId("managed");
    expect(useUIStore.getState().activeView).toBe("chat");
    expect(fixture.disposeRuntimes).toHaveBeenCalledOnce();
    expect(fixture.stopReaper).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Back local" }));
    await screen.findByTestId("local-neko");
    fireEvent.click(screen.getByRole("button", { name: "Connections" }));
    await screen.findByTestId("managed");
    expect(useUIStore.getState().activeView).toBe("wiii-connect");
    expect(useUIStore.getState().wiiiConnectFocusProvider).toBe("gmail");
    fireEvent.click(screen.getByRole("button", { name: "Back local" }));
    await screen.findByTestId("local-neko");
    fireEvent.click(screen.getByRole("button", { name: "Mở bản thử nghiệm Công việc" }));
    await screen.findByTestId("work-home");
    fireEvent.click(screen.getByTestId("open-neko"));
    await screen.findByTestId("local-neko");
    fireEvent.click(screen.getByRole("button", { name: "Connections" }));
    await screen.findByTestId("managed");
    expect(useUIStore.getState().wiiiConnectFocusProvider).toBe("gmail");
  });

  it("does not expose local Work or dispatch a local session when the web host has no local-process capability", async () => {
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
    fixture.storage.set("wiii-workbench.json:surface", "local");
    render(<WorkbenchGate host={web} />);
    await screen.findByTestId("managed");
    await waitFor(() => expect(useWorkbenchStore.getState().isLoaded).toBe(true));
    expect(screen.queryByTestId("local-neko")).toBeNull();
    expect(screen.queryByTestId("wiii-ade-app")).toBeNull();
    expect(screen.queryByRole("button", { name: "Back local" })).toBeNull();
    expect(fixture.hydrateWork).not.toHaveBeenCalled();
    expect(fixture.createTaskRun).not.toHaveBeenCalled();
    expect(fixture.disposeRuntimes).not.toHaveBeenCalled();
    expect(fixture.createSession).not.toHaveBeenCalled();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });

  it("keeps a busy or approval-bound native session mounted without sending Stop, then opens Work after it is idle", async () => {
    await nativeLocal();
    const idle = { status: "idle", cancelPending: false, closePending: false,
      pendingPermission: null, resolvingPermissionId: null };
    for (const busy of [
      { status: "connecting" }, { status: "dispatching" }, { status: "streaming" }, { status: "stopping" },
      { cancelPending: true }, { closePending: true },
      { pendingPermission: { requestId: "synthetic-permission" } }, { resolvingPermissionId: "synthetic-permission" },
    ]) {
      fixture.sessions["synthetic-active"] = { ...idle, ...busy };
      await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Mở bản thử nghiệm Công việc" })); });
      expect(await screen.findByTestId("work-navigation-status")).toBeTruthy();
      expect(screen.getByTestId("local-neko")).toBeTruthy();
      expect(screen.queryByTestId("wiii-ade-app")).toBeNull();
      expect(fixture.hydrateWork).not.toHaveBeenCalled();
      expect(fixture.cancelTurn).not.toHaveBeenCalled();
      expect(fixture.closeSession).not.toHaveBeenCalled();
    }
    // Idle navigation remains inside the same runtime owner.
    fixture.sessions["synthetic-active"] = { ...idle, runtime: { instanceId: "synthetic-idle-process" } };
    fireEvent.click(screen.getByRole("button", { name: "Mở bản thử nghiệm Công việc" }));
    await screen.findByTestId("work-home");
    expect(screen.queryByTestId("work-navigation-status")).toBeNull();
    expect(fixture.disposeRuntimes).not.toHaveBeenCalled();
    expect(fixture.createSession).not.toHaveBeenCalled();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });

  it("keeps ADE's inner Neko session mounted when Work is requested during a live turn or approval", async () => {
    await nativeLocal();
    fireEvent.click(screen.getByRole("button", { name: "Mở bản thử nghiệm Công việc" }));
    await screen.findByTestId("work-home");
    fireEvent.click(screen.getByTestId("open-neko"));
    await screen.findByTestId("local-neko");
    const idle = { status: "idle", cancelPending: false, closePending: false,
      pendingPermission: null, resolvingPermissionId: null };
    for (const busy of [
      { status: "connecting" }, { status: "dispatching" }, { status: "streaming" }, { status: "stopping" },
      { cancelPending: true }, { closePending: true },
      { pendingPermission: { requestId: "synthetic-scoped-permission" } },
      { resolvingPermissionId: "synthetic-scoped-permission" },
    ]) {
      fixture.sessions["synthetic-scoped-active"] = { ...idle, ...busy };
      fireEvent.click(screen.getByRole("button", { name: "Mở bản thử nghiệm Công việc" }));
      expect(await screen.findByTestId("work-navigation-status")).toBeTruthy();
      expect(screen.getByTestId("local-neko")).toBeTruthy();
      expect(screen.queryByTestId("work-home")).toBeNull();
      expect(fixture.cancelTurn).not.toHaveBeenCalled();
      expect(fixture.closeSession).not.toHaveBeenCalled();
    }
    fixture.sessions["synthetic-scoped-active"] = idle;
    fireEvent.click(screen.getByRole("button", { name: "Mở bản thử nghiệm Công việc" }));
    await screen.findByTestId("work-home");
    expect(screen.queryByTestId("work-navigation-status")).toBeNull();
    expect(fixture.disposeRuntimes).not.toHaveBeenCalled();
    expect(fixture.createSession).not.toHaveBeenCalled();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });
});
