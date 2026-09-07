/**
 * WorkbenchGate: entering the local surface mounts Neko Chill INSTEAD of the
 * managed app. The no-login guarantee is structural:
 * WiiiCloudApp (and with it every cloud init effect) never mounts.
 */

import { fireEvent, render, screen, waitFor, cleanup } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// jsdom does not implement matchMedia; the avatar hook (BootSplash) reads it
// on mount — same stub as login-screen-dev-login.test.tsx.
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

const storage = new Map<string, unknown>();

vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn(async (store: string, key: string, dflt: unknown) => {
    const hit = storage.get(`${store}:${key}`);
    return hit === undefined ? dflt : hit;
  }),
  saveStore: vi.fn(async (store: string, key: string, value: unknown) => {
    storage.set(`${store}:${key}`, value);
  }),
  deleteStore: vi.fn(async () => {}),
  clearStore: vi.fn(async () => {}),
}));

vi.mock("@/neko-chill/NekoChillApp", () => ({
  default: ({ onOpenConnections }: { onOpenConnections?: () => void }) => (
    <div data-testid="neko-chill-root">
      neko chill
      <button type="button" onClick={onOpenConnections}>open connections</button>
    </div>
  ),
}));

// The animated avatar needs IntersectionObserver/canvas APIs jsdom lacks;
// the gate test only cares about which SURFACE mounts.
vi.mock("@/components/common/WiiiAvatar", () => ({
  WiiiAvatar: () => <span data-testid="avatar-stub" />,
}));

import { WorkbenchGate } from "@/App";
import { useUIStore } from "@/stores/ui-store";
import { useWorkbenchStore } from "@/workbench/workbench-store";

const desktop = {
  kind: "desktop" as const,
  capabilities: {
    localProcess: true,
    localWorkspace: true,
    nativeWindow: true,
    tray: true,
    secureSecretStore: false,
    remoteRuntime: true,
  },
};

describe("WorkbenchGate (App.tsx seam)", () => {
  beforeEach(() => {
    storage.clear();
    useWorkbenchStore.setState({ surface: "local", isLoaded: false });
    useUIStore.setState({ activeView: "chat", wiiiConnectFocusProvider: null });
  });
  afterEach(() => cleanup());

  it("mounts Neko Chill as the local desktop surface instead of the cloud app", async () => {
    storage.set("neko-chill-mode.json:mode", "neko-chill");

    render(<WorkbenchGate host={desktop} />);

    await waitFor(() =>
      expect(screen.getByTestId("neko-chill-root")).toBeTruthy(),
    );
    // Cloud markers absent: no login screen, no cloud boot splash text.
    expect(screen.queryByText(/đăng nhập/i)).toBeNull();
    expect(screen.queryByText(/không gian trò chuyện/i)).toBeNull();
  });

  it("shows the boot splash until the persisted mode is loaded", () => {
    // Store load resolves async; before isLoaded the gate must not guess.
    storage.set("neko-chill-mode.json:mode", "neko-chill");
    render(<WorkbenchGate host={desktop} />);
    expect(screen.queryByTestId("neko-chill-root")).toBeNull();
  });

  it("routes the local Connections entry directly to Gmail management", async () => {
    storage.set("neko-chill-mode.json:mode", "neko-chill");
    render(<WorkbenchGate host={desktop} />);
    await screen.findByTestId("neko-chill-root");

    fireEvent.click(screen.getByRole("button", { name: "open connections" }));

    expect(useUIStore.getState().activeView).toBe("wiii-connect");
    expect(useUIStore.getState().wiiiConnectFocusProvider).toBe("gmail");
  });
});
