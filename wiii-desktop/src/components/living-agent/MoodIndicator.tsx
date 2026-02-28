/**
 * MoodIndicator — displays Wiii's current emotional state as a visual indicator.
 * Sprint 170: "Linh Hồn Sống"
 */
import { motion } from "motion/react";
import type { LivingAgentEmotionalState, WiiiMoodType } from "@/api/types";

interface MoodIndicatorProps {
  state: LivingAgentEmotionalState;
  compact?: boolean;
}

export const MOOD_CONFIG: Record<
  WiiiMoodType,
  { color: string; label: string; icon: string }
> = {
  curious: { color: "#6366f1", label: "Tò mò", icon: "?" },
  happy: { color: "#f59e0b", label: "Vui vẻ", icon: "^^" },
  excited: { color: "#ef4444", label: "Phấn khích", icon: "!!" },
  focused: { color: "#3b82f6", label: "Tập trung", icon: ">>" },
  calm: { color: "#10b981", label: "Bình yên", icon: "~" },
  tired: { color: "#9ca3af", label: "Hơi mệt", icon: ".." },
  concerned: { color: "#8b5cf6", label: "Lo lắng", icon: "??" },
  reflective: { color: "#06b6d4", label: "Trầm tư", icon: "..." },
  proud: { color: "#f97316", label: "Tự hào", icon: "*" },
  neutral: { color: "#6b7280", label: "Bình thường", icon: "-" },
};

function EnergyBar({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 text-[var(--text-secondary)] shrink-0">
        {label}
      </span>
      <div className="flex-1 h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{
            backgroundColor:
              value > 0.6
                ? "var(--accent)"
                : value > 0.3
                  ? "#f59e0b"
                  : "#ef4444",
          }}
          initial={{ width: 0 }}
          animate={{ width: `${value * 100}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
      </div>
      <span className="w-8 text-right text-[var(--text-tertiary)]">
        {Math.round(value * 100)}%
      </span>
    </div>
  );
}

export function MoodIndicator({ state, compact = false }: MoodIndicatorProps) {
  const config = MOOD_CONFIG[state.primary_mood] || MOOD_CONFIG.neutral;

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <motion.div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: config.color }}
          animate={{ scale: [1, 1.15, 1] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
        <span className="text-xs text-[var(--text-secondary)]">
          {config.label}
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Mood header */}
      <div className="flex items-center gap-3">
        <motion.div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-white font-mono text-sm"
          style={{ backgroundColor: config.color }}
          animate={{ scale: [1, 1.05, 1] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        >
          {config.icon}
        </motion.div>
        <div>
          <div className="text-sm font-medium text-[var(--text-primary)]">
            {state.mood_label || config.label}
          </div>
          <div className="text-xs text-[var(--text-tertiary)]">
            {state.primary_mood}
          </div>
        </div>
      </div>

      {/* Energy bars */}
      <div className="space-y-1.5">
        <EnergyBar value={state.energy_level} label="Năng lượng" />
        <EnergyBar value={state.social_battery} label="Xã hội" />
        <EnergyBar value={state.engagement} label="Tập trung" />
      </div>
    </div>
  );
}
