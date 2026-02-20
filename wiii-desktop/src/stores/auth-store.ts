/**
 * Auth store — manages authentication state.
 * Sprint 157: Google OAuth login, JWT tokens, user profile.
 *
 * Two auth modes:
 * 1. OAuth (Google login) — JWT tokens managed by this store
 * 2. Legacy (API key) — backward compat for development/LMS backends
 */
import { create } from "zustand";
import { loadStore, saveStore } from "@/lib/storage";

export interface AuthUser {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  role: string;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_at: number; // Unix timestamp (ms)
}

interface AuthState {
  isAuthenticated: boolean;
  user: AuthUser | null;
  tokens: AuthTokens | null;
  authMode: "oauth" | "legacy"; // oauth = Google login, legacy = API key

  // Actions
  loadAuth: () => Promise<void>;
  loginWithTokens: (
    accessToken: string,
    refreshToken: string,
    expiresIn: number,
    user: AuthUser,
  ) => Promise<void>;
  logout: () => Promise<void>;
  setLegacyMode: () => void;
  refreshAccessToken: (serverUrl: string) => Promise<boolean>;

  // Helpers
  getAuthHeaders: () => Record<string, string>;
  isTokenExpiringSoon: () => boolean;
}

const AUTH_STORE_KEY = "auth_state";

export const useAuthStore = create<AuthState>((set, get) => ({
  isAuthenticated: false,
  user: null,
  tokens: null,
  authMode: "legacy",

  loadAuth: async () => {
    try {
      const saved = await loadStore<{
        user: AuthUser | null;
        tokens: AuthTokens | null;
        authMode: "oauth" | "legacy";
      } | null>(AUTH_STORE_KEY, "data", null);

      if (saved?.tokens && saved?.user) {
        // Check if refresh token exists (access token may have expired — that's OK)
        set({
          isAuthenticated: true,
          user: saved.user,
          tokens: saved.tokens,
          authMode: saved.authMode || "oauth",
        });
      } else if (saved?.authMode === "legacy") {
        set({ authMode: "legacy" });
      }
    } catch (err) {
      console.warn("[Auth] Failed to load saved auth:", err);
    }
  },

  loginWithTokens: async (accessToken, refreshToken, expiresIn, user) => {
    const tokens: AuthTokens = {
      access_token: accessToken,
      refresh_token: refreshToken,
      expires_at: Date.now() + expiresIn * 1000,
    };

    set({
      isAuthenticated: true,
      user,
      tokens,
      authMode: "oauth",
    });

    // Persist
    try {
      await saveStore(AUTH_STORE_KEY, "data", {
        user,
        tokens,
        authMode: "oauth",
      });
    } catch (err) {
      console.warn("[Auth] Failed to save auth:", err);
    }
  },

  logout: async () => {
    const { tokens } = get();

    // Try to revoke on server
    if (tokens?.access_token) {
      try {
        const { useSettingsStore } = await import("@/stores/settings-store");
        const serverUrl = useSettingsStore.getState().settings.server_url;
        await fetch(`${serverUrl}/api/v1/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${tokens.access_token}`,
          },
        });
      } catch {
        // Best effort — ignore server errors
      }
    }

    set({
      isAuthenticated: false,
      user: null,
      tokens: null,
      authMode: "oauth",
    });

    try {
      await saveStore(AUTH_STORE_KEY, "data", { user: null, tokens: null, authMode: "oauth" });
    } catch {
      // ignore
    }
  },

  setLegacyMode: () => {
    set({ authMode: "legacy", isAuthenticated: true });
  },

  refreshAccessToken: async (serverUrl: string) => {
    const { tokens, user } = get();
    if (!tokens?.refresh_token) return false;

    try {
      const resp = await fetch(`${serverUrl}/api/v1/auth/token/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: tokens.refresh_token }),
      });

      if (!resp.ok) {
        // Refresh failed — log out
        console.warn("[Auth] Refresh failed:", resp.status);
        await get().logout();
        return false;
      }

      const data = await resp.json();
      const newTokens: AuthTokens = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_at: Date.now() + data.expires_in * 1000,
      };

      set({ tokens: newTokens });

      // Persist
      try {
        await saveStore(AUTH_STORE_KEY, "data", {
          user,
          tokens: newTokens,
          authMode: "oauth",
        });
      } catch {
        // ignore
      }

      return true;
    } catch (err) {
      console.warn("[Auth] Refresh error:", err);
      return false;
    }
  },

  getAuthHeaders: (): Record<string, string> => {
    const { tokens, authMode } = get();
    if (authMode === "oauth" && tokens?.access_token) {
      return { Authorization: `Bearer ${tokens.access_token}` };
    }
    return {};
  },

  isTokenExpiringSoon: () => {
    const { tokens } = get();
    if (!tokens) return false;
    // Expiring within 5 minutes
    return tokens.expires_at - Date.now() < 5 * 60 * 1000;
  },
}));
