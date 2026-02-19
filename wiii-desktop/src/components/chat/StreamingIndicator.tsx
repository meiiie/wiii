/**
 * @deprecated Sprint 141: Replaced by ThinkingFlow for streaming display.
 * Kept for potential minimal-mode fallback or AvatarPreview usage.
 */
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Check, ChevronDown } from "lucide-react";
import type { StreamingStep } from "@/api/types";
import { stepEntry, stepStagger, checkmarkPop } from "@/lib/animations";

interface StreamingIndicatorProps {
  steps: StreamingStep[];
  startTime: number | null;
  currentStep?: string;
}

/**
 * Pipeline progress indicator — 3-layer progressive disclosure.
 *
 * Sprint 63: Full progress panel with checkmarks + live elapsed timer.
 * Sprint 140: Progressive disclosure — compact by default, expand for details.
 *
 * L0 (always): Current step + elapsed timer (single line)
 * L1 (expand): Full pipeline step history with checkmarks
 * L2: Handled by ThinkingBlock (thinking content)
 */
export function StreamingIndicator({ steps, startTime, currentStep }: StreamingIndicatorProps) {
  const [elapsed, setElapsed] = useState(0);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!startTime) return;
    setElapsed(Math.floor((Date.now() - startTime) / 1000));
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  // Auto-expand when many steps arrive (indicates complex reasoning)
  useEffect(() => {
    if (steps.length >= 3 && !expanded) {
      setExpanded(true);
    }
  }, [steps.length, expanded]);

  const lastStep = steps.length > 0 ? steps[steps.length - 1] : null;
  const completedSteps = steps.slice(0, -1);
  const hasHistory = completedSteps.length > 0;

  return (
    <div className="mb-2" role="status" aria-live="polite" aria-label="Trạng thái xử lý">
      {/* L0: Compact current status line */}
      <div className="flex items-center gap-1.5">
        {/* Current step indicator */}
        {lastStep ? (
          <div className="flex items-center gap-1.5 text-xs">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent-orange)] animate-pulse shrink-0" />
            <span className="text-text-secondary">{lastStep.label}</span>
          </div>
        ) : currentStep ? (
          <div className="flex items-center gap-1.5 text-xs">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--accent-orange)] animate-pulse shrink-0" />
            <span className="text-text-secondary">{currentStep}</span>
          </div>
        ) : (
          <div className="flex items-center gap-1">
            <div
              className="w-1.5 h-1.5 rounded-full bg-[var(--accent-orange)] animate-pulse-dot"
              style={{ animationDelay: "0s" }}
            />
            <div
              className="w-1.5 h-1.5 rounded-full bg-[var(--accent-orange)] animate-pulse-dot"
              style={{ animationDelay: "0.2s" }}
            />
            <div
              className="w-1.5 h-1.5 rounded-full bg-[var(--accent-orange)] animate-pulse-dot"
              style={{ animationDelay: "0.4s" }}
            />
          </div>
        )}

        {/* Step counter + expand toggle (only when there's history) */}
        {hasHistory && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-0.5 text-[10px] text-text-tertiary hover:text-text-secondary transition-colors ml-1"
            aria-expanded={expanded}
            aria-label={expanded ? "Thu gọn chi tiết" : "Xem chi tiết"}
          >
            <span className="tabular-nums">{completedSteps.length} bước</span>
            <ChevronDown
              size={10}
              className={`transition-transform duration-200 ${expanded ? "rotate-0" : "-rotate-90"}`}
            />
          </button>
        )}

        {/* Elapsed timer — compact inline */}
        {startTime && (
          <motion.span
            className="text-[10px] text-text-tertiary tabular-nums ml-auto"
            animate={{ opacity: [0.5, 0.9, 0.5] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          >
            {elapsed >= 60
              ? `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`
              : `${elapsed}s`}
          </motion.span>
        )}
      </div>

      {/* L1: Expanded pipeline history */}
      <AnimatePresence initial={false}>
        {expanded && hasHistory && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <motion.div variants={stepStagger} initial="hidden" animate="visible" className="mt-1 ml-1 space-y-0.5 border-l border-[var(--border)] pl-2">
              {completedSteps.map((step, i) => (
                <motion.div key={i} variants={stepEntry} className="flex items-center gap-1.5 text-[11px]">
                  <motion.span variants={checkmarkPop} initial="hidden" animate="visible">
                    <Check size={10} className="text-[var(--accent-green)] shrink-0" />
                  </motion.span>
                  <span className="text-text-tertiary">{step.label}</span>
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Wiii personality timer message (below steps, only for longer waits) */}
      {startTime && elapsed >= 5 && (
        <motion.div
          className="text-[11px] text-text-tertiary mt-1"
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.7 }}
          transition={{ duration: 0.3 }}
        >
          {elapsed < 8
            ? "Wiii đang suy nghĩ..."
            : elapsed < 20
              ? "Wiii tư duy sâu..."
              : elapsed >= 60
                ? "Wiii đang phân tích kỹ cho bạn..."
                : "Wiii vẫn đang cố gắng..."}
        </motion.div>
      )}
    </div>
  );
}
