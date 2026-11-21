import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSettingsStore } from "@/stores/settings-store";
import { useAuthStore } from "@/stores/auth-store";
import { useConnectionStore } from "@/stores/connection-store";
import { useOrgStore } from "@/stores/org-store";
const client = vi.hoisted(() => ({ setHeaderResolver: vi.fn(), setOnUnauthorized: vi.fn() }));
vi.mock("@/api/client", () => ({ initClient: vi.fn(() => client) }));
import { configureWiiiServiceClient, useWiiiServiceSession } from "@/workbench/wiii-service-session";

describe("Service session lifecycle", () => {
  const order: string[] = [];
  beforeEach(() => {
    vi.clearAllMocks(); order.length = 0;
    useSettingsStore.setState({ settings: { ...useSettingsStore.getState().settings, server_url: "https://service.example", organization_id: "org" }, loadSettings: vi.fn(async () => { order.push("settings"); }), getAuthHeaders: vi.fn(() => ({ Authorization: "fresh" })) });
    useAuthStore.setState({ isAuthenticated: true, authMode: "oauth", user: null, loadAuth: vi.fn(async () => { order.push("auth"); }), refreshAccessToken: vi.fn(async () => true), logout: vi.fn(async () => {}), isTokenExpiringSoon: () => true });
    useConnectionStore.setState({ startPolling: vi.fn(), stopPolling: vi.fn() });
    useOrgStore.setState({ fetchOrganizations: vi.fn(async () => { order.push("organizations"); }), fetchAdminContext: vi.fn(async () => { order.push("admin"); }), setActiveOrg: vi.fn() });
  });
  afterEach(() => { cleanup(); vi.useRealTimers(); });

  it("loads settings before auth, configures polling/org restoration and cleans up", async () => {
    const { result, unmount } = renderHook(useWiiiServiceSession);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(order).toEqual(["settings", "auth", "organizations", "admin"]);
    expect(useOrgStore.getState().setActiveOrg).toHaveBeenCalledWith("org");
    expect(useConnectionStore.getState().startPolling).toHaveBeenCalledOnce();
    unmount(); expect(useConnectionStore.getState().stopPolling).toHaveBeenCalledOnce();
  });
  it("refreshes expiring JWTs and stops the timer on unmount", async () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(useWiiiServiceSession);
    await act(async () => {});
    await act(async () => { vi.advanceTimersByTime(60_000); });
    expect(useAuthStore.getState().refreshAccessToken).toHaveBeenCalledOnce();
    unmount();
    await act(async () => { vi.advanceTimersByTime(60_000); });
    expect(useAuthStore.getState().refreshAccessToken).toHaveBeenCalledOnce();
  });
  it("does not start services without authentication", async () => {
    useAuthStore.setState({ isAuthenticated: false });
    const { result } = renderHook(useWiiiServiceSession);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(useConnectionStore.getState().startPolling).not.toHaveBeenCalled();
  });
  it("reports persisted-state load errors and supports retry", async () => {
    vi.mocked(useSettingsStore.getState().loadSettings).mockRejectedValueOnce(new Error("disk"));
    const { result } = renderHook(useWiiiServiceSession);
    await waitFor(() => expect(result.current.error).toBe("disk"));
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeNull();
  });
  it("resolves fresh headers and handles OAuth and legacy unauthorized responses", async () => {
    configureWiiiServiceClient("https://service.example");
    expect(client.setHeaderResolver.mock.calls[0][0]()).toEqual({ Authorization: "fresh" });
    const unauthorized = client.setOnUnauthorized.mock.calls[0][0];
    expect(await unauthorized()).toBe(true);
    expect(useAuthStore.getState().refreshAccessToken).toHaveBeenCalledWith("https://service.example");
    useAuthStore.setState({ authMode: "legacy" });
    expect(await unauthorized()).toBe(false);
    expect(useAuthStore.getState().logout).toHaveBeenCalledOnce();
  });
});
