/**
 * ContextPanel — expandable context info panel above StatusBar.
 * Sprint 80: Always-visible context indicator with color-coded utilization.
 * Sprint 105: AnimatePresence slide-up, ConfirmDialog for clear, toast feedback.
 */
import { useState } from "react";
import { X, ChevronDown, Loader2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useContextStore } from "@/stores/context-store";
import { useChatStore } from "@/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { slideUp } from "@/lib/animations";
import { formatTokens } from "@/lib/format";
import type { ContextStatus } from "@/stores/context-store";

const STATUS_BAR_COLORS: Record<ContextStatus, string> = {
  unknown: "bg-gray-300",
  green: "bg-green-500",
  yellow: "bg-yellow-500",
  orange: "bg-orange-500",
  red: "bg-red-500",
};

export function ContextPanel() {
  const { info, status, isLoading, isPanelOpen, error, togglePanel, compact, clear } =
    useContextStore();
  const activeConv = useChatStore((s) => s.activeConversation());
  const sessionId = activeConv?.session_id || activeConv?.id || "";
  const { addToast } = useToastStore();
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const handleCompact = async () => {
    await compact(sessionId);
    addToast("success", "Wiii tóm tắt xong rồi!");
  };

  const handleClear = async () => {
    await clear(sessionId);
    setShowClearConfirm(false);
    addToast("success", "Wiii quên cuộc trò chuyện này rồi");
  };

  const utilization = info ? Math.round(info.utilization ?? 0) : 0;
  const totalBudget = info?.total_budget ?? 0;
  const totalUsed = info?.total_used ?? 0;

  return (
    <>
      <AnimatePresence>
        {isPanelOpen && info && (
          <motion.div
            variants={slideUp}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="border-t border-border bg-surface px-4 py-3 text-sm"
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <span className="font-medium text-text">Bộ nhớ hội thoại</span>
              <button
                onClick={togglePanel}
                className="p-1 rounded hover:bg-surface-tertiary text-text-secondary"
              >
                <X size={14} />
              </button>
            </div>

            {/* Progress bar */}
            <div className="mb-3">
              <div className="flex items-center justify-between text-xs text-text-secondary mb-1">
                <span>{utilization}%</span>
                <span>{formatTokens(totalUsed)}/{formatTokens(totalBudget)} tokens</span>
              </div>
              <div className="w-full h-2 bg-surface-tertiary rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${STATUS_BAR_COLORS[status]}`}
                  style={{ width: `${Math.min(utilization, 100)}%` }}
                />
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-3">
              <div className="flex justify-between text-text-secondary">
                <span>Tin nhắn:</span>
                <span className="text-text">{info.messages_included}/{info.total_history_messages}</span>
              </div>
              <div className="flex justify-between text-text-secondary">
                <span>Bị bỏ:</span>
                <span className="text-text">{info.messages_dropped}</span>
              </div>
              <div className="flex justify-between text-text-secondary">
                <span>Có tóm tắt:</span>
                <span className="text-text">{info.has_summary ? "Có" : "Không"}</span>
              </div>
              <div className="flex justify-between text-text-secondary">
                <span>Tóm tắt:</span>
                <span className="text-text">{info.running_summary_chars} ký tự</span>
              </div>
            </div>

            {/* Layer details */}
            <details className="mb-3">
              <summary className="text-xs text-text-secondary cursor-pointer hover:text-text">
                <ChevronDown size={12} className="inline mr-1" />
                Chi tiết layers
              </summary>
              <div className="mt-2 space-y-1 text-xs pl-4">
                {info.layers && (
                  <>
                    <LayerRow label="System Prompt" layer={info.layers.system_prompt} />
                    <LayerRow label="Core Memory" layer={info.layers.core_memory} />
                    <LayerRow label="Tóm tắt" layer={info.layers.summary} />
                    <LayerRow label="Tin nhắn" layer={info.layers.recent_messages} />
                  </>
                )}
              </div>
            </details>

            {/* Error */}
            {error && (
              <div className="text-xs text-red-500 mb-2">{error}</div>
            )}

            {/* Actions */}
            <div className="flex gap-2">
              <button
                onClick={handleCompact}
                disabled={isLoading}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs font-medium hover:bg-surface-tertiary transition-colors disabled:opacity-50"
              >
                {isLoading && <Loader2 size={12} className="animate-spin" />}
                Tóm tắt ngay
              </button>
              <button
                onClick={() => setShowClearConfirm(true)}
                disabled={isLoading}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-300 dark:border-red-800 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors disabled:opacity-50"
              >
                Xóa context
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <ConfirmDialog
        open={showClearConfirm}
        title="Xóa context hội thoại?"
        message="Tất cả lịch sử hội thoại và tóm tắt sẽ bị xóa. Bạn không thể hoàn tác."
        confirmLabel="Xóa context"
        cancelLabel="Hủy"
        variant="danger"
        onConfirm={handleClear}
        onCancel={() => setShowClearConfirm(false)}
      />
    </>
  );
}

function LayerRow({ label, layer }: { label: string; layer: { budget: number; used: number } }) {
  return (
    <div className="flex justify-between text-text-secondary">
      <span>{label}:</span>
      <span className="text-text">{formatTokens(layer.used)}/{formatTokens(layer.budget)}</span>
    </div>
  );
}
