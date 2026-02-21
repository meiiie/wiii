/**
 * Sprint 157: Auth store tests.
 * Tests OAuth login, logout, token refresh, legacy mode.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuthStore } from "@/stores/auth-store";
import type { AuthUser } from "@/stores/auth-store";

// Mock storage
vi.mock("@/lib/storage", () => ({
  loadStore: vi.fn().mockResolvedValue(null),
  saveStore: vi.fn().mockResolvedValue(undefined),
}));

const MOCK_USER: AuthUser = {
  id: "user-123",
  email: "test@gmail.com",
  name: "Test User",
  avatar_url: "https://example.com/avatar.jpg",
  role: "student",
};

function resetStore() {
  useAuthStore.setState({
    isAuthenticated: false,
    user: null,
    tokens: null,
    authMode: "legacy",
  });
}

describe("AuthStore", () => {
  beforeEach(() => {
    resetStore();
    vi.clearAllMocks();
  });

  it("has correct initial state", () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.tokens).toBeNull();
    expect(state.authMode).toBe("legacy");
  });

  it("loginWithTokens sets authenticated state", async () => {
    await useAuthStore.getState().loginWithTokens(
      "access-token-abc",
      "refresh-token-xyz",
      1800,
      MOCK_USER,
    );

    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.user).toEqual(MOCK_USER);
    expect(state.tokens?.access_token).toBe("access-token-abc");
    expect(state.tokens?.refresh_token).toBe("refresh-token-xyz");
    expect(state.authMode).toBe("oauth");
  });

  it("loginWithTokens sets correct expires_at", async () => {
    const before = Date.now();
    await useAuthStore.getState().loginWithTokens(
      "access-token",
      "refresh-token",
      1800, // 30 minutes
      MOCK_USER,
    );
    const after = Date.now();

    const expiresAt = useAuthStore.getState().tokens!.expires_at;
    // expires_at should be ~30 minutes from now
    expect(expiresAt).toBeGreaterThanOrEqual(before + 1800 * 1000);
    expect(expiresAt).toBeLessThanOrEqual(after + 1800 * 1000);
  });

  it("logout clears auth state", async () => {
    // Login first
    await useAuthStore.getState().loginWithTokens(
      "access-token",
      "refresh-token",
      1800,
      MOCK_USER,
    );
    expect(useAuthStore.getState().isAuthenticated).toBe(true);

    // Logout
    await useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
    expect(state.tokens).toBeNull();
  });

  it("setLegacyMode enables legacy auth", () => {
    useAuthStore.getState().setLegacyMode();
    const state = useAuthStore.getState();
    expect(state.authMode).toBe("legacy");
    expect(state.isAuthenticated).toBe(true);
  });

  it("getAuthHeaders returns Bearer token in oauth mode", async () => {
    await useAuthStore.getState().loginWithTokens(
      "my-access-token",
      "refresh-token",
      1800,
      MOCK_USER,
    );

    const headers = useAuthStore.getState().getAuthHeaders();
    expect(headers["Authorization"]).toBe("Bearer my-access-token");
  });

  it("getAuthHeaders returns empty in legacy mode", () => {
    useAuthStore.getState().setLegacyMode();
    const headers = useAuthStore.getState().getAuthHeaders();
    expect(headers["Authorization"]).toBeUndefined();
  });

  it("getAuthHeaders returns empty when not authenticated", () => {
    const headers = useAuthStore.getState().getAuthHeaders();
    expect(headers["Authorization"]).toBeUndefined();
    expect(Object.keys(headers)).toHaveLength(0);
  });

  it("isTokenExpiringSoon returns false for fresh tokens", async () => {
    await useAuthStore.getState().loginWithTokens(
      "access-token",
      "refresh-token",
      1800, // 30 minutes — well beyond 5-minute threshold
      MOCK_USER,
    );

    expect(useAuthStore.getState().isTokenExpiringSoon()).toBe(false);
  });

  it("isTokenExpiringSoon returns true for nearly-expired tokens", async () => {
    await useAuthStore.getState().loginWithTokens(
      "access-token",
      "refresh-token",
      120, // 2 minutes — within 5-minute threshold
      MOCK_USER,
    );

    expect(useAuthStore.getState().isTokenExpiringSoon()).toBe(true);
  });

  it("isTokenExpiringSoon returns false when no tokens", () => {
    expect(useAuthStore.getState().isTokenExpiringSoon()).toBe(false);
  });

  it("persists auth state via saveStore", async () => {
    const { saveStore } = await import("@/lib/storage");

    await useAuthStore.getState().loginWithTokens(
      "access-token",
      "refresh-token",
      1800,
      MOCK_USER,
    );

    expect(saveStore).toHaveBeenCalledWith(
      "auth_state",
      "data",
      expect.objectContaining({
        user: MOCK_USER,
        authMode: "oauth",
        tokens: expect.objectContaining({
          access_token: "access-token",
          refresh_token: "refresh-token",
        }),
      }),
    );
  });

  it("refreshAccessToken calls server and updates tokens", async () => {
    // Setup: logged in with tokens
    await useAuthStore.getState().loginWithTokens(
      "old-access-token",
      "old-refresh-token",
      1800,
      MOCK_USER,
    );

    // Mock fetch for refresh endpoint
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        access_token: "new-access-token",
        refresh_token: "new-refresh-token",
        expires_in: 1800,
      }),
    });
    globalThis.fetch = mockFetch;

    const result = await useAuthStore.getState().refreshAccessToken("http://localhost:8000");
    expect(result).toBe(true);
    expect(useAuthStore.getState().tokens?.access_token).toBe("new-access-token");
    expect(useAuthStore.getState().tokens?.refresh_token).toBe("new-refresh-token");
  });

  it("refreshAccessToken logs out on failure", async () => {
    await useAuthStore.getState().loginWithTokens(
      "access-token",
      "refresh-token",
      1800,
      MOCK_USER,
    );

    const mockFetch = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    globalThis.fetch = mockFetch;

    const result = await useAuthStore.getState().refreshAccessToken("http://localhost:8000");
    expect(result).toBe(false);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
