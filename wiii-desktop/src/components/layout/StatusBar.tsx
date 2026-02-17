/**
 * StatusBar — bottom bar showing domain, streaming status, context badge.
 * Sprint 105: Animated pulse on context badge when orange/red status.
 */
import { useDomainStore } from "@/stores/domain-store";
import { useChatStore } from "@/stores/chat-store";
import { useContextStore } from "@/stores/context-store";
import { useUIStore } from "@/stores/ui-store";
import { useCharacterStore, MOOD_LABELS, MOOD_EMOJI, MOOD_COLORS } from "@/stores/character-store";
import { motion } from "motion/react";
import { Anchor, Database } from "lucide-react";
import { DOMAIN_ICONS } from "@/lib/domain-config";
import { WiiiAvatar } from "@/components/common/WiiiAvatar";
import type { AvatarState } from "@/components/common/WiiiAvatar";
import type { ContextStatus } from "@/stores/context-store";

const CONTEXT_BADGE_COLORS: Record<ContextStatus, string> = {
  unknown: "text-text-tertiary",
  green: "text-green-500",
  yellow: "text-yellow-500",
  orange: "text-orange-500",
  red: "text-red-500",
};

function deriveAvatarState(isStreaming: boolean, hasContent: boolean, inputFocused: boolean): AvatarState {
  if (isStreaming) return hasContent ? "speaking" : "thinking";
  if (inputFocused) return "listening";
  return "idle";
}

export function StatusBar() {
  const { activeDomainId } = useDomainStore();
  const { isStreaming, streamingStep, streamingContent } = useChatStore();
  const { info, status, togglePanel } = useContextStore();
  const inputFocused = useUIStore((s) => s.inputFocused);
  const toggleCharacterPanel = useUIStore((s) => s.toggleCharacterPanel);
  const { mood, moodEnabled } = useCharacterStore();

  const avatarState = deriveAvatarState(isStreaming, !!streamingContent, inputFocused);

  const Icon = DOMAIN_ICONS[activeDomainId] || Anchor;
  const utilization = info ? Math.round(info.utilization ?? 0) : null;
  const msgCount = info?.messages_included ?? null;

  const shouldPulse = status === "orange" || status === "red";

  return (
    <div className="flex items-center justify-between h-7 px-3 bg-surface border-t border-border text-xs text-text-tertiary">
      {/* Left: Wiii presence + Mood + Domain */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={toggleCharacterPanel}
          className="flex items-center gap-1 hover:opacity-80 transition-opacity"
          title="Tính cách Wiii"
          aria-label="Mở bảng tính cách Wiii"
        >
          <WiiiAvatar state={avatarState} size={14} />
          {moodEnabled && (
            <span
              className={`text-[10px] ${MOOD_COLORS[mood]}`}
              title={`Tâm trạng: ${MOOD_LABELS[mood]}`}
            >
              {MOOD_EMOJI[mood]}
            </span>
          )}
        </button>
        <Icon size={12} />
        <span>{activeDomainId}</span>
      </div>

      {/* Center: Streaming status */}
      {isStreaming && streamingStep && (
        <div className="flex items-center gap-1.5 text-[var(--accent)]">
          <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-pulse" />
          <span>{streamingStep}</span>
        </div>
      )}

      {/* Right: Context badge */}
      {utilization !== null && (
        <motion.button
          onClick={togglePanel}
          className={`flex items-center gap-1.5 hover:opacity-80 transition-opacity ${CONTEXT_BADGE_COLORS[status]}`}
          title="Context window info"
          animate={shouldPulse ? { opacity: [0.7, 1, 0.7] } : { opacity: 1 }}
          transition={shouldPulse ? { duration: 2, repeat: Infinity, ease: "easeInOut" } : undefined}
        >
          <Database size={12} />
          <span>{utilization}%</span>
          {msgCount !== null && <span>| {msgCount} msgs</span>}
        </motion.button>
      )}
    </div>
  );
}
