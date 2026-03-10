/**
 * Lightweight toast notification for admin/org-admin panels.
 * Sprint 180: "Quản Trị Hoàn Thiện"
 * Sprint 219d: Extracted PanelToast for reuse across admin + org-admin.
 */
import { CheckCircle, XCircle } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";

interface PanelToastProps {
  toast: { type: "success" | "error"; message: string } | null;
}

/** Generic panel toast — accepts toast object as prop. */
export function PanelToast({ toast }: PanelToastProps) {
  if (!toast) return null;

  const isSuccess = toast.type === "success";

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[80] animate-fade-in">
      <div
        className={`flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-lg border text-sm font-medium ${
          isSuccess
            ? "bg-green-50 dark:bg-green-950/60 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300"
            : "bg-red-50 dark:bg-red-950/60 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300"
        }`}
        role="status"
        aria-live="polite"
      >
        {isSuccess ? <CheckCircle size={16} /> : <XCircle size={16} />}
        {toast.message}
      </div>
    </div>
  );
}

/** Admin-panel toast — wired to admin-store. */
export function AdminToast() {
  const toast = useAdminStore((s) => s.toast);
  return <PanelToast toast={toast} />;
}
