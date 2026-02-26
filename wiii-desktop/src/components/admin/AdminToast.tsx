/**
 * Lightweight toast notification for admin panel.
 * Sprint 180: "Quản Trị Hoàn Thiện"
 */
import { CheckCircle, XCircle } from "lucide-react";
import { useAdminStore } from "@/stores/admin-store";

export function AdminToast() {
  const toast = useAdminStore((s) => s.toast);
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
