/**
 * Reusable confirmation dialog — modal with title, message, confirm/cancel.
 * Sprint 81: Foundation UX component.
 */
import { useEffect, useRef } from "react";
import { AlertTriangle } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "default";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Xác nhận",
  cancelLabel = "Huỷ",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus trap + Escape to cancel
  useEffect(() => {
    if (!open) return;

    // Focus the cancel button (safe default) when dialog opens
    confirmRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }

      // Simple focus trap
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  const isDanger = variant === "danger";

  return (
    <div
      className="fixed inset-0 z-[90] flex items-center justify-center bg-black/40 animate-fade-in"
      onClick={onCancel}
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div
        ref={dialogRef}
        className="bg-surface rounded-xl shadow-2xl w-full max-w-sm mx-4 border border-border animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 pt-5 pb-4">
          <div className="flex items-start gap-3">
            {isDanger && (
              <div className="shrink-0 w-9 h-9 rounded-full bg-red-100 dark:bg-red-950/50 flex items-center justify-center">
                <AlertTriangle size={18} className="text-red-500" />
              </div>
            )}
            <div className="flex-1">
              <h3
                id="confirm-dialog-title"
                className="text-sm font-semibold text-text"
              >
                {title}
              </h3>
              <p className="mt-1 text-sm text-text-secondary">{message}</p>
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-5 pb-4">
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded-lg border border-border text-sm font-medium text-text-secondary hover:bg-surface-tertiary active:scale-[0.98] transition-all"
          >
            {cancelLabel}
          </button>
          <button
            ref={confirmRef}
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-sm font-medium text-white active:scale-[0.98] transition-all ${
              isDanger
                ? "bg-red-500 hover:bg-red-600"
                : "bg-[var(--accent)] hover:bg-[var(--accent-hover)]"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
