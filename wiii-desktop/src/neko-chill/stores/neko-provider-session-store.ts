import { create } from "zustand";
import { getNekoControlClient } from "@/neko/control-client";
import type { NekoProviderSessionCatalog } from "@/neko/contracts";
import type { DetectedAgent } from "./neko-agent-store";

interface NekoProviderSessionState {
  catalogs: Record<string, NekoProviderSessionCatalog>;
  loading: boolean;
  error: string | null;
  refresh: (
    agents: DetectedAgent[],
    workspacePaths: string[],
    options?: { includeProjectScoped?: boolean },
  ) => Promise<void>;
}

let refreshGeneration = 0;

export const useNekoProviderSessionStore = create<NekoProviderSessionState>((set) => ({
  catalogs: {},
  loading: false,
  error: null,

  refresh: async (agents, workspacePaths, options) => {
    const generation = ++refreshGeneration;
    const available = agents.filter((agent) => agent.found);
    if (available.length === 0) {
      set({ catalogs: {}, loading: false, error: null });
      return;
    }
    set({ loading: true, error: null });
    const results = await Promise.allSettled(
      available.map(async (agent) => {
        // Gemini exposes session listing per project and may generate missing
        // summaries while doing so. Keep startup discovery cheap and make the
        // broader project scan an explicit user action.
        if (agent.id === "gemini" && !options?.includeProjectScoped) {
          return {
            providerId: agent.id,
            catalog: {
              providerId: agent.id,
              scope: "known_projects" as const,
              complete: false,
              detail:
                "Gemini CLI chỉ liệt kê phiên theo project. Nhấn Quét lại để hỏi các folder Wiii đã biết.",
              sessions: [],
            },
          };
        }
        return {
          providerId: agent.id,
          catalog: await getNekoControlClient().listProviderSessions({
            providerId: agent.id,
            workspacePaths,
          }),
        };
      }),
    );
    if (generation !== refreshGeneration) return;
    const catalogs: Record<string, NekoProviderSessionCatalog> = {};
    const failures: string[] = [];
    for (const [index, result] of results.entries()) {
      const agent = available[index];
      if (result.status === "fulfilled") {
        catalogs[result.value.providerId] = result.value.catalog;
      } else {
        const detail = result.reason instanceof Error ? result.reason.message : String(result.reason);
        failures.push(`${agent.name}: ${detail}`);
        catalogs[agent.id] = {
          providerId: agent.id,
          scope: agent.id === "gemini" ? "known_projects" : "all",
          complete: false,
          detail: `Chưa thể đọc phiên từ ${agent.name}: ${detail}`,
          sessions: [],
        };
      }
    }
    set({
      catalogs,
      loading: false,
      error: failures.length ? failures.join(" · ") : null,
    });
  },
}));
