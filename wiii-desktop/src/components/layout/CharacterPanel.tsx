/**
 * CharacterPanel — Wiii personality blocks + mood display.
 * Sprint 120: Shows character blocks with usage bars and current mood.
 */
import { useEffect } from "react";
import { X, Loader2, RefreshCw } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useUIStore } from "@/stores/ui-store";
import { useCharacterStore, BLOCK_LABELS, MOOD_LABELS, MOOD_COLORS, MOOD_EMOJI } from "@/stores/character-store";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import { slideUp } from "@/lib/animations";

/** Color for usage bar based on percentage. */
function usageColor(percent: number): string {
  if (percent >= 80) return "bg-orange-500";
  if (percent >= 50) return "bg-yellow-500";
  return "bg-green-500";
}

export function CharacterPanel() {
  const { characterPanelOpen, toggleCharacterPanel } = useUIStore();
  const {
    blocks,
    totalBlocks,
    isLoading,
    error,
    mood,
    positivity,
    energy,
    moodEnabled,
    fetchCharacter,
  } = useCharacterStore();

  // Fetch character state when panel opens
  useEffect(() => {
    if (characterPanelOpen) {
      fetchCharacter();
    }
  }, [characterPanelOpen, fetchCharacter]);

  return (
    <AnimatePresence>
      {characterPanelOpen && (
        <motion.div
          variants={slideUp}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="border-t border-border bg-surface px-4 py-3 text-sm"
          role="region"
          aria-label="Tính cách Wiii"
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <WiiiAvatar state="idle" size={20} />
              <span className="font-medium text-text">Wiii</span>
              {moodEnabled && (
                <span
                  className={`text-xs ${MOOD_COLORS[mood]}`}
                  title={`Tâm trạng: ${MOOD_LABELS[mood]}`}
                >
                  {MOOD_EMOJI[mood]} {MOOD_LABELS[mood]}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => fetchCharacter()}
                disabled={isLoading}
                className="p-1 rounded hover:bg-surface-tertiary text-text-secondary"
                title="Tải lại"
                aria-label="Tải lại tính cách"
              >
                <RefreshCw size={12} className={isLoading ? "animate-spin" : ""} />
              </button>
              <button
                onClick={toggleCharacterPanel}
                className="p-1 rounded hover:bg-surface-tertiary text-text-secondary"
                aria-label="Đóng bảng tính cách"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Mood meter (if enabled) */}
          {moodEnabled && (
            <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-text-secondary">Tích cực:</span>
                <div className="w-full h-1.5 bg-surface-tertiary rounded-full mt-0.5 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-green-500 transition-all duration-500"
                    style={{ width: `${Math.max(0, (positivity + 1) / 2 * 100)}%` }}
                  />
                </div>
              </div>
              <div>
                <span className="text-text-secondary">Năng lượng:</span>
                <div className="w-full h-1.5 bg-surface-tertiary rounded-full mt-0.5 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500 transition-all duration-500"
                    style={{ width: `${energy * 100}%` }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Loading */}
          {isLoading && blocks.length === 0 && (
            <div className="flex items-center justify-center py-4 text-text-secondary text-xs">
              <Loader2 size={14} className="animate-spin mr-2" />
              Đang tải...
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="text-xs text-red-500 mb-2">{error}</div>
          )}

          {/* Character blocks */}
          {blocks.length > 0 && (
            <div className="space-y-2">
              {blocks.map((block) => (
                <div key={block.label} className="rounded-lg border border-border p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-text">
                      {BLOCK_LABELS[block.label] || block.label}
                    </span>
                    <span className="text-[10px] text-text-secondary">
                      {Math.round(block.usage_percent)}%
                    </span>
                  </div>
                  {/* Usage bar */}
                  <div className="w-full h-1 bg-surface-tertiary rounded-full overflow-hidden mb-1.5">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${usageColor(block.usage_percent)}`}
                      style={{ width: `${Math.min(block.usage_percent, 100)}%` }}
                    />
                  </div>
                  {/* Content preview */}
                  {block.content && (
                    <p className="text-[11px] text-text-secondary line-clamp-2 leading-relaxed">
                      {block.content}
                    </p>
                  )}
                  {!block.content && (
                    <p className="text-[11px] text-text-tertiary italic">
                      Chưa có nội dung
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {!isLoading && blocks.length === 0 && !error && (
            <div className="text-center py-4 text-xs text-text-secondary">
              Wiii chưa có ghi nhớ tính cách nào.
              <br />
              Hãy trò chuyện thêm nhé!
            </div>
          )}

          {/* Total */}
          {totalBlocks > 0 && (
            <div className="mt-2 text-[10px] text-text-tertiary text-right">
              {totalBlocks} blocks
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
