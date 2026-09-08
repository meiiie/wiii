import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { nekoLayoutStorage } from "../browser-storage";
import { completionPlayer } from "../completion-sound";

export interface CompletionNotice {
  id: string;
  sessionId: string;
  title: string;
}

interface CompletionNoticeState {
  enabled: boolean;
  sound: boolean;
  notices: CompletionNotice[];
  setEnabled: (enabled: boolean) => void;
  setSound: (enabled: boolean) => void;
  publish: (notice: CompletionNotice) => void;
  dismiss: (id: string) => void;
}

export const useCompletionNoticeStore = create<CompletionNoticeState>()(persist((set, get) => ({
  enabled: true,
  sound: true,
  notices: [],
  setEnabled: (enabled) => set({ enabled, ...(!enabled ? { notices: [] } : {}) }),
  setSound: (sound) => set({ sound }),
  publish: (notice) => {
    const state = get();
    if (!state.enabled || state.notices.some((item) => item.id === notice.id)) return;
    set({ notices: [...state.notices, { ...notice, title: notice.title.slice(0, 120) }].slice(-3) });
    if (state.sound) void completionPlayer.play();
  },
  dismiss: (id) => set((state) => ({ notices: state.notices.filter((notice) => notice.id !== id) })),
}), {
  name: "wiii-completion-preferences-v1",
  storage: createJSONStorage(() => nekoLayoutStorage),
  partialize: (state) => ({ enabled: state.enabled, sound: state.sound }),
  merge: (saved, current) => {
    const values = saved as Partial<CompletionNoticeState> | null;
    return { ...current, enabled: typeof values?.enabled === "boolean" ? values.enabled : true,
      sound: typeof values?.sound === "boolean" ? values.sound : true };
  },
}));
