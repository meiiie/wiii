/**
 * Toast notification container — renders stack of toasts top-right.
 * Sprint 81: Foundation UX component.
 */
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";
import { useToastStore } from "@/stores/toast-store";
import type { ToastType } from "@/stores/toast-store";

const ICONS: Record<ToastType, typeof CheckCircle> = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const STYLES: Record<ToastType, string> = {
  success:
    "bg-green-50 dark:bg-green-950/80 border-green-300 dark:border-green-700 text-green-800 dark:text-green-200",
  error:
    "bg-red-50 dark:bg-red-950/80 border-red-300 dark:border-red-700 text-red-800 dark:text-red-200",
  info: "bg-blue-50 dark:bg-blue-950/80 border-blue-300 dark:border-blue-700 text-blue-800 dark:text-blue-200",
};

const ICON_COLORS: Record<ToastType, string> = {
  success: "text-green-500",
  error: "text-red-500",
  info: "text-blue-500",
};

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-3 right-3 z-[100] flex flex-col gap-2 pointer-events-none"
      role="status"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const Icon = ICONS[toast.type];
        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-center gap-2.5 px-4 py-3 rounded-lg border shadow-lg text-sm animate-slide-in min-w-[280px] max-w-[400px] ${STYLES[toast.type]}`}
          >
            <Icon size={16} className={`shrink-0 ${ICON_COLORS[toast.type]}`} />
            <span className="flex-1">{toast.message}</span>
            <button
              onClick={() => removeToast(toast.id)}
              className="shrink-0 p-0.5 rounded hover:opacity-70 transition-opacity"
              aria-label="Đóng thông báo"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
