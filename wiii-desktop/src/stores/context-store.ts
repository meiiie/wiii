/**
 * Context store — context utilization state + polling.
 * Sprint 80: Always-visible context bar with color-coded utilization.
 */
import { create } from "zustand";
import {
  fetchContextInfo,
  compactContext,
  clearContext,
} from "@/api/context";
import { CONTEXT_POLL_INTERVAL } from "@/lib/constants";
import type { ContextInfoResponse } from "@/api/types";

export type ContextStatus = "unknown" | "green" | "yellow" | "orange" | "red";

function computeStatus(utilization: number): ContextStatus {
  if (utilization < 50) return "green";
  if (utilization < 75) return "yellow";
  if (utilization < 90) return "orange";
  return "red";
}

interface ContextState {
  info: ContextInfoResponse | null;
  status: ContextStatus;
  isLoading: boolean;
  isPanelOpen: boolean;
  error: string | null;
  pollIntervalId: ReturnType<typeof setInterval> | null;

  fetchContextInfo: (sessionId: string) => Promise<void>;
  compact: (sessionId: string) => Promise<void>;
  clear: (sessionId: string) => Promise<void>;
  togglePanel: () => void;
  startPolling: (sessionId: string, intervalMs?: number) => void;
  stopPolling: () => void;
}

export const useContextStore = create<ContextState>((set, get) => ({
  info: null,
  status: "unknown",
  isLoading: false,
  isPanelOpen: false,
  error: null,
  pollIntervalId: null,

  fetchContextInfo: async (sessionId: string) => {
    if (!sessionId) return;
    set({ isLoading: true, error: null });
    try {
      const info = await fetchContextInfo(sessionId);
      const utilization = info.utilization ?? 0;
      set({
        info,
        status: computeStatus(utilization),
        isLoading: false,
      });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : "Không thể tải thông tin ngữ cảnh",
      });
    }
  },

  compact: async (sessionId: string) => {
    if (!sessionId) return;
    set({ isLoading: true, error: null });
    try {
      await compactContext(sessionId);
      // Refresh info after compaction
      await get().fetchContextInfo(sessionId);
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : "Không thể tóm tắt",
      });
    }
  },

  clear: async (sessionId: string) => {
    if (!sessionId) return;
    set({ isLoading: true, error: null });
    try {
      await clearContext(sessionId);
      set({
        info: null,
        status: "unknown",
        isLoading: false,
      });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : "Không thể xóa ngữ cảnh",
      });
    }
  },

  togglePanel: () => {
    set((state) => ({ isPanelOpen: !state.isPanelOpen }));
  },

  startPolling: (sessionId: string, intervalMs?: number) => {
    const { pollIntervalId } = get();
    if (pollIntervalId) clearInterval(pollIntervalId);

    // Fetch immediately
    get().fetchContextInfo(sessionId);

    const id = setInterval(() => {
      get().fetchContextInfo(sessionId);
    }, intervalMs ?? CONTEXT_POLL_INTERVAL);

    set({ pollIntervalId: id });
  },

  stopPolling: () => {
    const { pollIntervalId } = get();
    if (pollIntervalId) {
      clearInterval(pollIntervalId);
      set({ pollIntervalId: null });
    }
  },
}));
