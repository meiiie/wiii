import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/stores/auth-store";
import { useSettingsStore } from "@/stores/settings-store";
import { useOrgStore } from "@/stores/org-store";

const session = vi.hoisted(() => ({ loading: false, error: null as string | null, retry: vi.fn() }));
vi.mock("@/workbench/wiii-service-session", () => ({ useWiiiServiceSession: () => session }));
vi.mock("@/components/auth/LoginScreen", () => ({ LoginScreen: ({ onOpenLocal }: { onOpenLocal: () => void }) => <button onClick={onOpenLocal}>Connexion Service</button> }));
vi.mock("@/components/common/WiiiMark", () => ({ WiiiMark: () => null }));
vi.mock("@/components/connect/WiiiConnectPage", async () => {
  const { FullPageView } = await import("@/components/layout/FullPageView");
  return { WiiiConnectPage: ({ onClose, backLabel }: { onClose: () => void; backLabel: string }) => (
    <FullPageView title="Kết nối" icon={null} tabs={[]} activeTab="" onTabChange={() => {}} onClose={onClose} backLabel={backLabel}>Catalogue</FullPageView>
  ) };
});
import { WiiiServiceSurface } from "@/workbench/WiiiServiceSurface";

describe("native Service surface", () => {
  const onBack = vi.fn();
  const onOpenConnect = vi.fn();
  beforeEach(() => {
    vi.clearAllMocks();
    session.loading = false; session.error = null;
    useSettingsStore.setState({ settings: { ...useSettingsStore.getState().settings, server_url: "https://service.example", display_name: "Neko User" }, updateSettings: vi.fn(async () => {}) });
    useOrgStore.setState({ organizations: [], activeOrgId: null, setActiveOrg: vi.fn() });
    useAuthStore.setState({ isAuthenticated: false, user: null, logout: vi.fn(async () => { useAuthStore.setState({ isAuthenticated: false }); }) });
  });
  afterEach(cleanup);
  const mount = (view: "service" | "connect" = "service") => render(<WiiiServiceSurface view={view} onBack={onBack} onOpenConnect={onOpenConnect} />);

  it("shows the bootstrap splash", () => {
    session.loading = true; mount();
    expect(screen.getByText("Wiii đang kết nối Service...")).toBeTruthy();
  });
  it("shows login without auth and returns locally", () => {
    mount(); fireEvent.click(screen.getByText("Connexion Service")); expect(onBack).toHaveBeenCalledOnce();
  });
  it("requires an endpoint even when authenticated", () => {
    useAuthStore.setState({ isAuthenticated: true });
    useSettingsStore.setState({ settings: { ...useSettingsStore.getState().settings, server_url: "" } });
    mount(); expect(screen.getByText("Connexion Service")).toBeTruthy();
  });
  it("reacts to login, opens connections, and shows login again after logout", async () => {
    const { rerender } = mount();
    useAuthStore.setState({ isAuthenticated: true });
    rerender(<WiiiServiceSurface view="service" onBack={onBack} onOpenConnect={onOpenConnect} />);
    expect(screen.getByText("Neko User")).toBeTruthy();
    expect(screen.getByText("https://service.example")).toBeTruthy();
    expect(screen.queryByLabelText("Tổ chức")).toBeNull();
    fireEvent.click(screen.getByText("Tài khoản & ứng dụng")); expect(onOpenConnect).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByText("Đăng xuất"));
    expect(await screen.findByText("Connexion Service")).toBeTruthy();
  });
  it("updates the selected organization and persisted header settings", () => {
    useAuthStore.setState({ isAuthenticated: true });
    useOrgStore.setState({ organizations: [
      { id: "one", name: "Một", is_active: true, allowed_domains: [] },
      { id: "two", name: "Hai", is_active: true, allowed_domains: [] },
    ], activeOrgId: "one" });
    mount(); fireEvent.change(screen.getByLabelText("Tổ chức"), { target: { value: "two" } });
    expect(useOrgStore.getState().setActiveOrg).toHaveBeenCalledWith("two");
    expect(useSettingsStore.getState().updateSettings).toHaveBeenCalledWith({ organization_id: "two" });
  });
  it("uses the native Connect back label and callback", () => {
    useAuthStore.setState({ isAuthenticated: true }); mount("connect");
    fireEvent.click(screen.getByRole("button", { name: "Quay lại Neko" })); expect(onBack).toHaveBeenCalledOnce();
  });
  it("offers retry on bootstrap failure", () => {
    session.error = "Lecture impossible"; mount();
    expect(screen.getByText("Lecture impossible")).toBeTruthy();
    fireEvent.click(screen.getByText("Thử khởi động lại")); expect(session.retry).toHaveBeenCalledOnce();
  });
});
