import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { WorkbenchHost } from "@/workbench/host";

const fixture = vi.hoisted(() => ({
  stopReaper: vi.fn(), startReaper: vi.fn(), disposeRuntimes: vi.fn(async () => {}),
  storage: new Map<string, unknown>(),
  readStore: vi.fn(),
  createSession: vi.fn(async () => "must-not-launch"), spawnProvider: vi.fn(async () => {}),
  sessions: {} as Record<string, { status: string; cancelPending: boolean; closePending: boolean;
    pendingPermission: object | null; resolvingPermissionId: string | null }>,
  cancelTurn: vi.fn(), closeSession: vi.fn(),
}));
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, fallback: unknown) => {
    fixture.readStore(store); return fixture.storage.get(`${store}:${key}`) ?? fallback;
  }),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => { fixture.storage.set(`${store}:${key}`, value); }),
  deleteStore: vi.fn(), clearStore: vi.fn(),
}));
vi.mock("@/workbench/WorkbenchBoot", () => ({ BootSplash: ({ label }: { label: string }) => <div role="status">{label}</div> }));
vi.mock("@/components/common/WiiiMark", () => ({ WiiiMark: () => <span /> }));
vi.mock("@/neko/control-client", () => ({ getNekoControlClient: () => ({ spawnProvider: fixture.spawnProvider }) }));
vi.mock("@/neko-chill/stores/neko-outbox-store", () => ({ startNekoOutbox: vi.fn(() => vi.fn()) }));
vi.mock("@/neko-chill/stores/neko-session-store", () => ({
  startIdleReaper: fixture.startReaper, disposeAllNekoRuntimes: fixture.disposeRuntimes,
  useNekoSessionStore: { getState: () => ({ sessions: fixture.sessions,
    createSession: fixture.createSession, cancelTurn: fixture.cancelTurn, closeSession: fixture.closeSession }) },
}));
vi.mock("@/neko-chill/NekoChillApp", () => ({
  default: ({ active = true, onOpenManaged, onOpenConnections }: {
    active?: boolean; onOpenManaged: () => void; onOpenConnections: () => void;
  }) => <div data-testid="local-neko" data-active={active}>
    <button type="button" onClick={onOpenManaged}>Managed</button>
    <button type="button" onClick={onOpenConnections}>Connections</button>
  </div>,
}));
vi.mock("@/workbench/WiiiServiceSurface", () => ({
  WiiiServiceSurface: ({ view, onBack, onOpenConnect }: { view: string; onBack: () => void; onOpenConnect: () => void }) => (
    <div data-testid={`native-${view}`}>
      <button onClick={onBack}>Quay lại Neko</button>
      <button onClick={onOpenConnect}>Tài khoản &amp; ứng dụng</button>
    </div>
  ),
}));
import App, { WorkbenchGate } from "@/App";
import { useWorkbenchStore } from "@/workbench/workbench-store";
import { useUIStore } from "@/stores/ui-store";

const desktop: WorkbenchHost = { kind: "desktop", capabilities: {
  localProcess: true, localWorkspace: true, nativeWindow: true,
  tray: true, secureSecretStore: false, remoteRuntime: true,
} };
const web: WorkbenchHost = { kind: "web", capabilities: {
  ...desktop.capabilities, localProcess: false, localWorkspace: false, nativeWindow: false, tray: false,
} };

describe("local workspace without the retired Work feature", () => {
  beforeEach(() => {
    fixture.storage.clear(); vi.clearAllMocks();
    fixture.startReaper.mockReturnValue(fixture.stopReaper);
    for (const id of Object.keys(fixture.sessions)) delete fixture.sessions[id];
    useWorkbenchStore.setState({ surface: "local", isLoaded: false });
    useUIStore.setState({ activeView: "chat", wiiiConnectFocusProvider: null });
    Object.defineProperty(window, "__TAURI_INTERNALS__", { value: {}, configurable: true });
  });
  afterEach(() => {
    cleanup(); Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    window.history.replaceState(null, "", "/");
  });

  it("opens only the workspace and leaves legacy Work data untouched and unread", async () => {
    const legacy = { v: 1, graph: { tasks: [{ id: "old-task" }] } };
    fixture.storage.set("wiii-ade-work.json:snapshot", legacy);
    render(<WorkbenchGate host={desktop} />);
    await screen.findByTestId("local-neko");
    expect(screen.queryByText(/Công việc/)).toBeNull();
    expect(fixture.readStore).not.toHaveBeenCalledWith("wiii-ade-work.json");
    expect(fixture.storage.get("wiii-ade-work.json:snapshot")).toBe(legacy);
    expect(fixture.createSession).not.toHaveBeenCalled();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });

  it.each(["Managed", "Connections"])("retains the same transcript through a %s detour", async (button) => {
    render(<WorkbenchGate host={desktop} />);
    const transcript = await screen.findByTestId("local-neko");
    fireEvent.click(screen.getByRole("button", { name: button }));
    await screen.findByTestId(button === "Managed" ? "native-service" : "native-connect");
    expect(transcript.getAttribute("data-active")).toBe("false");
    if (button === "Managed") {
      fireEvent.click(screen.getByRole("button", { name: "Tài khoản & ứng dụng" }));
      await screen.findByTestId("native-connect");
    }
    expect(useUIStore.getState().wiiiConnectFocusProvider).toBe("gmail");
    fireEvent.click(screen.getByRole("button", { name: "Quay lại Neko" }));
    await waitFor(() => expect(transcript.getAttribute("data-active")).toBe("true"));
    expect(screen.getByTestId("local-neko")).toBe(transcript);
    expect(fixture.disposeRuntimes).not.toHaveBeenCalled();
    expect(fixture.stopReaper).not.toHaveBeenCalled();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });

  it.each(["Managed", "Connections"])("blocks %s without stopping a busy or approval-bound native session", async (button) => {
    render(<WorkbenchGate host={desktop} />);
    const transcript = await screen.findByTestId("local-neko");
    const idle = { status: "idle", cancelPending: false, closePending: false, pendingPermission: null, resolvingPermissionId: null };
    for (const busy of [
      { status: "connecting" }, { status: "dispatching" }, { status: "streaming" }, { status: "stopping" },
      { cancelPending: true }, { closePending: true }, { pendingPermission: { requestId: "permission" } },
      { resolvingPermissionId: "permission" },
    ]) {
      fixture.sessions.active = { ...idle, ...busy };
      fireEvent.click(screen.getByRole("button", { name: button }));
      await screen.findByTestId("work-navigation-status");
      expect(await screen.findByTestId("local-neko")).toBe(transcript);
      expect(screen.queryByTestId("native-service")).toBeNull();
      expect(screen.queryByTestId("native-connect")).toBeNull();
    }
    expect(fixture.cancelTurn).not.toHaveBeenCalled();
    expect(fixture.closeSession).not.toHaveBeenCalled();
    expect(fixture.disposeRuntimes).not.toHaveBeenCalled();
  });

  it("does not expose or dispatch a local session on web", async () => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    render(<WorkbenchGate host={web} />);
    await screen.findByRole("heading", { name: "Wiii chạy trên ứng dụng desktop" });
    expect(screen.queryByTestId("local-neko")).toBeNull();
    expect(fixture.createSession).not.toHaveBeenCalled();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });

  it("does not resurrect the removed feature through its old preview URL", async () => {
    Reflect.deleteProperty(window, "__TAURI_INTERNALS__");
    window.history.replaceState(null, "", "/?preview=ade");
    render(<App />);
    await screen.findByRole("heading", { name: "Wiii chạy trên ứng dụng desktop" });
    expect(screen.queryByTestId("wiii-ade-app")).toBeNull();
    expect(fixture.spawnProvider).not.toHaveBeenCalled();
  });
});
