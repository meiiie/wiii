/**
 * Toast notification store — stack-based, auto-dismiss.
 * Sprint 81: Foundation UX component.
 */
import { create } from "zustand";

export type ToastType = "success" | "error" | "info";

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (type: ToastType, message: string, duration?: number) => void;
  removeToast: (id: string) => void;
}

const MAX_VISIBLE_TOASTS = 3;
let _nextId = 0;

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],

  addToast: (type, message, duration = 3000) => {
    const id = `toast-${++_nextId}`;
    set((state) => {
      const next = [...state.toasts, { id, type, message, duration }];
      // Keep only the most recent toasts to prevent stacking
      return { toasts: next.length > MAX_VISIBLE_TOASTS ? next.slice(-MAX_VISIBLE_TOASTS) : next };
    });

    // Auto-dismiss
    if (duration > 0) {
      setTimeout(() => {
        set((state) => ({
          toasts: state.toasts.filter((t) => t.id !== id),
        }));
      }, duration);
    }
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    }));
  },
}));
