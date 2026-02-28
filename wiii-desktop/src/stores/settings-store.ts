/**
 * Settings store — persisted via tauri-plugin-store.
 * Manages server URL, API key, user info, theme, etc.
 *
 * Sprint 194b: Security hardening
 * - Removed hardcoded DEFAULT_USER_ID — anonymous UUID generated at runtime
 * - facebook_cookie moved to secure-token-storage (PII protection)
 * - getAuthHeaders() no longer sends X-User-ID/X-Role in OAuth mode
 * - Legacy mode role restricted to student/teacher (no admin escalation)
 */
import { create } from "zustand";
import type { AppSettings } from "@/api/types";
import {
  DEFAULT_SERVER_URL,
  DEFAULT_USER_ROLE,
  DEFAULT_DISPLAY_NAME,
  DEFAULT_DOMAIN,
  DEFAULT_LANGUAGE,
  DEFAULT_STREAMING_VERSION,
} from "@/lib/constants";

/**
 * Generate a unique anonymous user ID.
 * Uses crypto.randomUUID when available (modern browsers + Node 19+),
 * falls back to a simple UUID v4 implementation.
 */
function generateAnonymousId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `anon-${crypto.randomUUID()}`;
  }
  // Fallback for older environments
  return `anon-${"xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  })}`;
}

const DEFAULT_SETTINGS: AppSettings = {
  server_url: DEFAULT_SERVER_URL,
  api_key: "",
  user_id: "",  // Sprint 194b: empty — generated on first load, never hardcoded
  user_role: DEFAULT_USER_ROLE,
  display_name: DEFAULT_DISPLAY_NAME,
  default_domain: DEFAULT_DOMAIN,
  theme: "system",
  language: DEFAULT_LANGUAGE,
  show_thinking: true,
  show_reasoning_trace: false,
  streaming_version: DEFAULT_STREAMING_VERSION,
  thinking_level: "balanced",
  // Sprint 194b: facebook_cookie removed — moved to secure-token-storage (H5)
  show_previews: true,  // Sprint 166: Rich preview cards
  show_artifacts: true, // Sprint 167: Interactive artifacts
};

interface SettingsState {
  settings: AppSettings;
  isLoaded: boolean;

  // Actions
  loadSettings: () => Promise<void>;
  updateSettings: (partial: Partial<AppSettings>) => Promise<void>;
  resetSettings: () => Promise<void>;
  getAuthHeaders: () => Record<string, string>;
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  settings: DEFAULT_SETTINGS,
  isLoaded: false,

  loadSettings: async () => {
    try {
      const { Store } = await import("@tauri-apps/plugin-store");
      const store = await Store.load("settings.json");
      const saved = await store.get<AppSettings>("app_settings");

      if (saved) {
        const merged = { ...DEFAULT_SETTINGS, ...saved };

        // Sprint 194b: Migrate away from hardcoded "desktop-user" or empty user_id
        if (!merged.user_id || merged.user_id === "desktop-user") {
          merged.user_id = generateAnonymousId();
          // Persist immediately so the UUID is stable across sessions
          await store.set("app_settings", merged);
          await store.save();
        }

        set({
          settings: merged,
          isLoaded: true,
        });
      } else {
        // First launch — generate anonymous ID
        const fresh = { ...DEFAULT_SETTINGS, user_id: generateAnonymousId() };
        set({ settings: fresh, isLoaded: true });
        // Persist so user_id is stable
        await store.set("app_settings", fresh);
        await store.save();
      }
    } catch (err) {
      console.warn("[Settings] Failed to load, using defaults:", err);
      // Browser fallback: try localStorage
      try {
        const raw = localStorage.getItem("wiii:app_settings");
        if (raw) {
          const saved = JSON.parse(raw) as Partial<AppSettings>;
          const merged = { ...DEFAULT_SETTINGS, ...saved };
          // Sprint 194b: Migrate hardcoded user_id
          if (!merged.user_id || merged.user_id === "desktop-user") {
            merged.user_id = generateAnonymousId();
            localStorage.setItem("wiii:app_settings", JSON.stringify(merged));
          }
          set({ settings: merged, isLoaded: true });
          return;
        }
      } catch { /* ignore */ }
      // Final fallback: generate anonymous ID in memory
      set({ settings: { ...DEFAULT_SETTINGS, user_id: generateAnonymousId() }, isLoaded: true });
    }
  },

  updateSettings: async (partial) => {
    const newSettings = { ...get().settings, ...partial };
    set({ settings: newSettings });

    try {
      const { Store } = await import("@tauri-apps/plugin-store");
      const store = await Store.load("settings.json");
      await store.set("app_settings", newSettings);
      await store.save();
    } catch (err) {
      console.warn("[Settings] Failed to save:", err);
      // Browser fallback: save to localStorage
      try {
        localStorage.setItem("wiii:app_settings", JSON.stringify(newSettings));
      } catch { /* ignore */ }
    }
  },

  resetSettings: async () => {
    // Sprint 194b: Generate fresh anonymous ID on reset
    const resetWith = { ...DEFAULT_SETTINGS, user_id: generateAnonymousId() };
    set({ settings: resetWith });

    try {
      const { Store } = await import("@tauri-apps/plugin-store");
      const store = await Store.load("settings.json");
      await store.set("app_settings", resetWith);
      await store.save();
    } catch (err) {
      console.warn("[Settings] Failed to reset:", err);
    }
  },

  getAuthHeaders: () => {
    const { settings } = get();
    const headers: Record<string, string> = {};

    // Sprint 157: Try OAuth JWT first, fallback to API key
    try {
      const { useAuthStore } = require("@/stores/auth-store");
      const authState = useAuthStore.getState();
      if (authState.authMode === "oauth" && authState.tokens?.access_token) {
        // Sprint 194b (H1): OAuth mode — identity from JWT only
        // DO NOT send X-User-ID or X-Role — backend extracts from token
        headers["Authorization"] = `Bearer ${authState.tokens.access_token}`;
        // Sprint 156: Include org ID when not personal workspace
        if (settings.organization_id && settings.organization_id !== "personal") {
          headers["X-Organization-ID"] = settings.organization_id;
        }
        return headers;
      }
    } catch {
      // auth-store not available — use legacy mode
    }

    // Legacy API key mode
    // Sprint 192: API key from settings (secure store loaded at init)
    if (settings.api_key) headers["X-API-Key"] = settings.api_key;
    headers["X-User-ID"] = settings.user_id;
    // Sprint 194b (C4): Legacy mode — restrict to student/teacher only.
    // Admin role must come via OAuth JWT, not spoofable X-Role header.
    const safeRole = ["student", "teacher"].includes(settings.user_role)
      ? settings.user_role
      : "student";
    headers["X-Role"] = safeRole;
    // Sprint 156: Include org ID when not personal workspace
    if (settings.organization_id && settings.organization_id !== "personal") {
      headers["X-Organization-ID"] = settings.organization_id;
    }
    return headers;
  },
}));

// Sprint 194b: Export for testing
export { generateAnonymousId };
