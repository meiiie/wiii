/**
 * Detected local providers. Neko Control owns host discovery; this store only
 * caches the roster needed by the current session launcher.
 */
import { create } from "zustand";
import { getNekoControlClient } from "@/neko/control-client";
import type {
  NekoDetectedProvider,
  NekoLaunchProfile,
} from "@/neko/contracts";

export interface DetectedAgent extends NekoDetectedProvider {}
export interface AgentLaunchProfile extends NekoLaunchProfile {}

/** Read-only, workspace-aware Neko profile discovery. Other agents return none. */
export async function loadAgentProfiles(
  agent: DetectedAgent,
  workspacePath: string,
): Promise<AgentLaunchProfile[]> {
  if (!agent.supportsProfiles || !agent.found || !workspacePath) return [];
  return getNekoControlClient().listProfiles({
    providerId: agent.id,
    workspacePath,
  });
}

interface NekoAgentState {
  agents: DetectedAgent[];
  isLoading: boolean;
  error: string | null;
  probeStates: Record<string, "checking" | "ready" | "error">;
  detect: (providerId?: string) => Promise<void>;
}

/** Rust-side detection; resolves empty in browser dev (no Tauri runtime). */
async function detectAgents(providerId?: string): Promise<DetectedAgent[]> {
  return getNekoControlClient().listProviders(providerId);
}

const probes = new Map<string, Promise<void>>();

export const useNekoAgentStore = create<NekoAgentState>((set, get) => ({
  agents: [],
  isLoading: false,
  error: null,
  probeStates: {},

  detect: async (providerId) => {
    const key = providerId ?? "*";
    const existing = probes.get("*") ?? probes.get(key);
    if (existing) return existing;
    const preceding = providerId ? [] : [...probes.values()];
    const requestedIds = providerId ? [providerId] : get().agents.map((agent) => agent.id);
    const markProbes = (status: "checking" | "ready" | "error") => set((state) => ({
      probeStates: { ...state.probeStates, ...Object.fromEntries(requestedIds.map((id) => [id, status])) },
    }));
    set({ isLoading: true, error: null });
    markProbes("checking");
    const probe = (async () => {
      try {
        await Promise.all(preceding);
        const agents = await detectAgents(providerId);
        set((state) => ({
          agents: providerId
            ? [...state.agents.filter((agent) => !agents.some((item) => item.id === agent.id)), ...agents]
            : agents,
          probeStates: { ...state.probeStates, ...Object.fromEntries(agents.map((agent) => [agent.id, "ready" as const])) },
        }));
      } catch (cause) {
        const detail = cause instanceof Error ? cause.message : String(cause);
        set({ error: `Không thể dò agent cục bộ: ${detail}` });
        markProbes("error");
      } finally {
        probes.delete(key);
        set({ isLoading: probes.size > 0 });
      }
    })();
    probes.set(key, probe);
    return probe;
  },
}));
