/**
 * Settings store — persisted via tauri-plugin-store.
 * Manages server URL, API key, user info, theme, etc.
 */
import { create } from "zustand";
import type { AppSettings } from "@/api/types";
import {
  DEFAULT_SERVER_URL,
  DEFAULT_USER_ID,
  DEFAULT_USER_ROLE,
  DEFAULT_DISPLAY_NAME,
  DEFAULT_DOMAIN,
  DEFAULT_LANGUAGE,
  DEFAULT_STREAMING_VERSION,
} from "@/lib/constants";

const DEFAULT_SETTINGS: AppSettings = {
  server_url: DEFAULT_SERVER_URL,
  api_key: "",
  user_id: DEFAULT_USER_ID,
  user_role: DEFAULT_USER_ROLE,
  display_name: DEFAULT_DISPLAY_NAME,
  default_domain: DEFAULT_DOMAIN,
  theme: "system",
  language: DEFAULT_LANGUAGE,
  show_thinking: true,
  show_reasoning_trace: false,
  streaming_version: DEFAULT_STREAMING_VERSION,
  thinking_level: "balanced",
  facebook_cookie: "",  // Sprint 154: Facebook cookie for logged-in search
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
        set({
          settings: { ...DEFAULT_SETTINGS, ...saved },
          isLoaded: true,
        });
      } else {
        set({ isLoaded: true });
      }
    } catch (err) {
      console.warn("[Settings] Failed to load, using defaults:", err);
      // Browser fallback: try localStorage
      try {
        const raw = localStorage.getItem("wiii:app_settings");
        if (raw) {
          const saved = JSON.parse(raw) as Partial<AppSettings>;
          set({ settings: { ...DEFAULT_SETTINGS, ...saved }, isLoaded: true });
          return;
        }
      } catch { /* ignore */ }
      set({ isLoaded: true });
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
    set({ settings: DEFAULT_SETTINGS });

    try {
      const { Store } = await import("@tauri-apps/plugin-store");
      const store = await Store.load("settings.json");
      await store.set("app_settings", DEFAULT_SETTINGS);
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
    if (settings.api_key) headers["X-API-Key"] = settings.api_key;
    headers["X-User-ID"] = settings.user_id;
    headers["X-Role"] = settings.user_role;
    // Sprint 156: Include org ID when not personal workspace
    if (settings.organization_id && settings.organization_id !== "personal") {
      headers["X-Organization-ID"] = settings.organization_id;
    }
    return headers;
  },
}));
