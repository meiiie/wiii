/**
 * Memory store — user memory facts state.
 * Sprint 80: ChatGPT-style memory management (view/delete facts).
 */
import { create } from "zustand";
import { fetchMemories, deleteMemory } from "@/api/memories";
import type { MemoryItem } from "@/api/types";

/** Vietnamese labels for fact types (Sprint 73: 15 FactTypes). */
export const FACT_TYPE_LABELS: Record<string, string> = {
  name: "Tên",
  age: "Tuổi",
  location: "Nơi ở",
  organization: "Tổ chức",
  role: "Vai trò",
  level: "Cấp bậc",
  goal: "Mục tiêu",
  preference: "Sở thích học",
  weakness: "Điểm yếu",
  strength: "Điểm mạnh",
  learning_style: "Phong cách học",
  hobby: "Sở thích",
  interest: "Quan tâm",
  emotion: "Tâm trạng",
  recent_topic: "Chủ đề gần đây",
  pronoun_style: "Xưng hô",
  hometown: "Quê quán",
};

interface MemoryState {
  memories: MemoryItem[];
  isLoading: boolean;
  error: string | null;

  fetchMemories: (userId: string) => Promise<void>;
  deleteOne: (userId: string, memoryId: string) => Promise<void>;
  clearAll: (userId: string) => Promise<void>;
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  memories: [],
  isLoading: false,
  error: null,

  fetchMemories: async (userId: string) => {
    if (!userId) return;
    set({ isLoading: true, error: null });
    try {
      const res = await fetchMemories(userId);
      set({ memories: res.data ?? [], isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to fetch memories",
      });
    }
  },

  deleteOne: async (userId: string, memoryId: string) => {
    try {
      await deleteMemory(userId, memoryId);
      // Optimistic removal
      set((state) => ({
        memories: state.memories.filter((m) => m.id !== memoryId),
      }));
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to delete memory",
      });
    }
  },

  clearAll: async (userId: string) => {
    const { memories } = get();
    set({ isLoading: true, error: null });
    try {
      // Delete all memories one by one (backend has no bulk delete)
      await Promise.all(
        memories.map((m) => deleteMemory(userId, m.id))
      );
      set({ memories: [], isLoading: false });
    } catch (err) {
      set({
        isLoading: false,
        error: err instanceof Error ? err.message : "Failed to clear memories",
      });
      // Refresh to get actual state
      await get().fetchMemories(userId);
    }
  },
}));
