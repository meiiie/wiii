/**
 * Living Agent store — Sprint 170: "Linh Hồn Sống"
 *
 * Manages Wiii's autonomous life state: emotional state, skills, journal, heartbeat.
 */
import { create } from "zustand";
import type {
  LivingAgentStatus,
  LivingAgentEmotionalState,
  LivingAgentJournalEntry,
  LivingAgentSkill,
  LivingAgentHeartbeat,
  LivingAgentGoal,
  LivingAgentReflection,
} from "@/api/types";
import {
  getLivingAgentStatus,
  getEmotionalState,
  getJournalEntries,
  getSkills,
  triggerHeartbeat,
  getGoals,
  getReflections,
} from "@/api/living-agent";

interface LivingAgentState {
  // Data
  enabled: boolean;
  soulName: string;
  emotionalState: LivingAgentEmotionalState | null;
  heartbeat: LivingAgentHeartbeat | null;
  journalEntries: LivingAgentJournalEntry[];
  skills: LivingAgentSkill[];
  goals: LivingAgentGoal[];
  reflections: LivingAgentReflection[];
  loading: boolean;
  error: string | null;
  lastFetched: number | null;

  // Actions
  fetchStatus: () => Promise<void>;
  fetchEmotionalState: () => Promise<void>;
  fetchJournal: (days?: number) => Promise<void>;
  fetchSkills: (params?: { status?: string; domain?: string }) => Promise<void>;
  fetchGoals: () => Promise<void>;
  fetchReflections: (days?: number) => Promise<void>;
  triggerHeartbeat: () => Promise<boolean>;
  reset: () => void;
}

const INITIAL_STATE = {
  enabled: false,
  soulName: "",
  emotionalState: null,
  heartbeat: null,
  journalEntries: [],
  skills: [],
  goals: [],
  reflections: [],
  loading: false,
  error: null,
  lastFetched: null,
};

export const useLivingAgentStore = create<LivingAgentState>((set, get) => ({
  ...INITIAL_STATE,

  fetchStatus: async () => {
    set({ loading: true, error: null });
    try {
      const status: LivingAgentStatus = await getLivingAgentStatus();
      set({
        enabled: status.enabled,
        soulName: status.soul_name || "",
        emotionalState: status.emotional_state,
        heartbeat: status.heartbeat,
        loading: false,
        lastFetched: Date.now(),
      });
    } catch (e) {
      set({ loading: false, error: String(e) });
    }
  },

  fetchEmotionalState: async () => {
    try {
      const state = await getEmotionalState();
      set({ emotionalState: state });
    } catch (e) {
      // Silent — emotional state is non-critical
      console.warn("[living-agent] Failed to fetch emotional state:", e);
    }
  },

  fetchJournal: async (days = 7) => {
    try {
      const entries = await getJournalEntries(days);
      set({ journalEntries: entries });
    } catch (e) {
      console.warn("[living-agent] Failed to fetch journal:", e);
    }
  },

  fetchSkills: async (params) => {
    try {
      const skills = await getSkills(params);
      set({ skills });
    } catch (e) {
      console.warn("[living-agent] Failed to fetch skills:", e);
    }
  },

  fetchGoals: async () => {
    try {
      const goals = await getGoals();
      set({ goals });
    } catch (e) {
      console.warn("[living-agent] Failed to fetch goals:", e);
    }
  },

  fetchReflections: async (days = 14) => {
    try {
      const reflections = await getReflections(days);
      set({ reflections });
    } catch (e) {
      console.warn("[living-agent] Failed to fetch reflections:", e);
    }
  },

  triggerHeartbeat: async () => {
    try {
      const result = await triggerHeartbeat();
      if (result.success) {
        // Refresh status after heartbeat
        await get().fetchStatus();
      }
      return result.success;
    } catch (e) {
      console.warn("[living-agent] Failed to trigger heartbeat:", e);
      return false;
    }
  },

  reset: () => set(INITIAL_STATE),
}));
