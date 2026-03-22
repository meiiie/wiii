/**
 * Model store — per-request LLM provider selection.
 *
 * Tracks available providers (fetched from /llm/status) and
 * the user's active choice ("auto" | "google" | "zhipu" | "ollama").
 * Persists activeProvider via settings-store so it survives page reloads.
 */
import { create } from "zustand";
import { getClient } from "@/api/client";
import { useSettingsStore } from "@/stores/settings-store";

export interface ProviderInfo {
  id: string;
  displayName: string;
  available: boolean;
  isPrimary: boolean;
  isFallback: boolean;
}

interface ModelState {
  activeProvider: string; // "auto" | "google" | "zhipu" | "ollama"
  providers: ProviderInfo[];
  isLoading: boolean;

  setActiveProvider: (id: string) => void;
  fetchProviders: () => Promise<void>;
}

export const useModelStore = create<ModelState>((set) => ({
  activeProvider: useSettingsStore.getState().settings.model_provider || "auto",
  providers: [],
  isLoading: false,

  setActiveProvider: (id) => {
    set({ activeProvider: id });
    useSettingsStore.getState().updateSettings({ model_provider: id as "auto" | "google" | "zhipu" | "ollama" });
  },

  fetchProviders: async () => {
    set({ isLoading: true });
    try {
      const client = getClient();
      const data = await client.get<{
        providers: Array<{
          id: string;
          display_name: string;
          available: boolean;
          is_primary: boolean;
          is_fallback: boolean;
        }>;
      }>("/api/v1/llm/status");
      const providers: ProviderInfo[] = (data.providers || []).map((p) => ({
        id: p.id,
        displayName: p.display_name,
        available: p.available,
        isPrimary: p.is_primary,
        isFallback: p.is_fallback,
      }));
      set({ providers, isLoading: false });
    } catch (err) {
      console.warn("[Model] Failed to fetch providers:", err);
      set({ isLoading: false });
    }
  },
}));
