/**
 * @deprecated Sprint 141b — ThinkingFlow is no longer rendered by MessageList.
 * Replaced by interleaved block rendering (streamingBlocks.map → ThinkingBlock + AnswerBlock).
 *
 * Kept for reference and potential analytics use. The `streamingPhases` store field
 * and phase-related actions remain functional for data tracking.
 *
 * Original: Sprint 141 — unified multi-phase thinking display.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown } from "lucide-react";
import type { ThinkingPhase, ThinkingLevel } from "@/api/types";
import { SparkleIcon, InlineToolCard } from "./ThinkingBlock";
import { MarkdownRenderer } from "@/components/common/MarkdownRenderer";

interface ThinkingFlowProps {
  phases: ThinkingPhase[];
  startTime: number | null;
  isStreaming: boolean;
  thinkingLevel: ThinkingLevel;
}

export function ThinkingFlow({
  phases,
  startTime,
  isStreaming,
  thinkingLevel,
}: ThinkingFlowProps) {
  const [elapsed, setElapsed] = useState(0);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const collapseTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Live elapsed timer
  useEffect(() => {
    if (!startTime) return;
    setElapsed(Math.floor((Date.now() - startTime) / 1000));
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  // Auto-collapse all phases 1.5s after streaming ends (except detailed mode)
  useEffect(() => {
    if (!isStreaming && phases.length > 0 && thinkingLevel !== "detailed") {
      collapseTimerRef.current = setTimeout(() => {
        setCollapsed(new Set(phases.map((p) => p.id)));
      }, 1500);
      return () => {
        if (collapseTimerRef.current) clearTimeout(collapseTimerRef.current);
      };
    }
    // When streaming starts, reset collapsed set
    if (isStreaming) {
      setCollapsed(new Set());
    }
  }, [isStreaming, phases.length, thinkingLevel]);

  const togglePhase = useCallback((id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // Minimal mode: return null (ThinkingFlow hidden)
  if (thinkingLevel === "minimal") return null;
  if (phases.length === 0) return null;

  return (
    <div className="thinking-flow mb-3">
      {phases.map((phase) => {
        const isActive = phase.status === "active";
        // Active = expanded by default; completed = collapsed by default.
        // User toggle (collapsed set) overrides both directions.
        const phaseExpanded = collapsed.has(phase.id)
          ? false
          : isActive || thinkingLevel === "detailed";

        return (
          <PhaseItem
            key={phase.id}
            phase={phase}
            expanded={phaseExpanded}
            onToggle={() => togglePhase(phase.id)}
            isStreaming={isStreaming && isActive}
          />
        );
      })}

      {/* Overall flow timer */}
      {isStreaming && startTime && (
        <motion.div
          className="flex items-center gap-1.5 mt-1.5 text-[10px] text-text-tertiary"
          animate={{ opacity: [0.5, 0.9, 0.5] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
        >
          <span className="tabular-nums">
            {elapsed >= 60
              ? `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`
              : `${elapsed}s`}
          </span>
        </motion.div>
      )}
    </div>
  );
}

/* ---- Phase Item ---- */

function PhaseItem({
  phase,
  expanded,
  onToggle,
  isStreaming,
}: {
  phase: ThinkingPhase;
  expanded: boolean;
  onToggle: () => void;
  isStreaming: boolean;
}) {
  const duration =
    phase.startTime && phase.endTime
      ? Math.round((phase.endTime - phase.startTime) / 1000)
      : 0;

  const hasContent =
    phase.thinkingContent ||
    phase.toolCalls.length > 0 ||
    phase.statusMessages.length > 0;

  return (
    <div className="mb-1">
      {/* Phase header */}
      <button
        onClick={onToggle}
        className="thinking-phase-header w-full text-left"
        aria-expanded={expanded}
      >
        <SparkleIcon live={isStreaming} />
        <span className="text-[13px] font-medium text-[var(--thinking-text)]">
          {phase.label}
        </span>
        {isStreaming ? (
          <span className="w-2 h-2 rounded-full bg-[var(--accent-orange)] animate-pulse shrink-0" />
        ) : duration > 0 ? (
          <span className="text-[11px] text-text-tertiary tabular-nums">
            {duration}s
          </span>
        ) : null}
        {hasContent && (
          <ChevronDown
            size={12}
            className={`text-[var(--thinking-text)] transition-transform duration-200 ${
              expanded ? "rotate-0" : "-rotate-90"
            }`}
          />
        )}
      </button>

      {/* Phase content — collapsible */}
      <AnimatePresence initial={false}>
        {expanded && hasContent && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="thinking-phase-content">
              {/* Status messages */}
              {phase.statusMessages.length > 0 && (
                <div className="space-y-0.5 mb-1">
                  {phase.statusMessages.map((msg, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-1.5 text-[11px] text-text-tertiary"
                    >
                      <span className="text-[var(--accent-green)]">&#10003;</span>
                      <span>{msg}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Thinking content */}
              {phase.thinkingContent && (
                <div className="thinking-content text-xs text-[var(--thinking-text)] leading-relaxed">
                  <MarkdownRenderer content={phase.thinkingContent} />
                  {isStreaming && phase.toolCalls.length === 0 && (
                    <span className="inline-block w-1.5 h-3.5 bg-[var(--thinking-text)] opacity-40 ml-0.5 animate-pulse rounded-sm" />
                  )}
                </div>
              )}

              {/* Inline tool cards */}
              {phase.toolCalls.length > 0 && (
                <div className="mt-1 space-y-1">
                  {phase.toolCalls.map((tc, i) => (
                    <InlineToolCard
                      key={tc.id || i}
                      toolCall={tc}
                      isLast={i === phase.toolCalls.length - 1}
                      isStreaming={isStreaming}
                    />
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
