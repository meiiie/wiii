import { useState, useEffect } from "react";
import { motion } from "motion/react";
import { Check } from "lucide-react";
import type { StreamingStep } from "@/api/types";
import { stepEntry, stepStagger, checkmarkPop } from "@/lib/animations";

interface StreamingIndicatorProps {
  steps: StreamingStep[];
  startTime: number | null;
  currentStep?: string;
}

/**
 * Pipeline progress indicator — shows step list + live elapsed timer.
 *
 * Sprint 63: Replaces 3-dot animation with full progress panel.
 * - Completed steps show green checkmark
 * - Current step shows pulsing orange dot
 * - Live timer updates every 1s
 */
export function StreamingIndicator({ steps, startTime, currentStep }: StreamingIndicatorProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!startTime) return;
    setElapsed(Math.floor((Date.now() - startTime) / 1000));
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [startTime]);

  return (
    <div className="mb-2 space-y-0.5" role="status" aria-live="polite" aria-label="Trạng thái xử lý">
      {/* Pipeline steps */}
      <motion.div variants={stepStagger} initial="hidden" animate="visible" className="space-y-0.5">
        {steps.map((step, i) => {
          const isLast = i === steps.length - 1;
          return (
            <motion.div key={i} variants={stepEntry} className="flex items-center gap-1.5 text-xs">
              {isLast ? (
                <span className="w-3 h-3 rounded-full bg-[var(--accent-orange)] animate-pulse shrink-0" />
              ) : (
                <motion.span variants={checkmarkPop} initial="hidden" animate="visible">
                  <Check size={12} className="text-[var(--accent-green)] shrink-0" />
                </motion.span>
              )}
              <span className={isLast ? "text-text-secondary" : "text-text-tertiary"}>
                {step.label}
              </span>
            </motion.div>
          );
        })}
      </motion.div>

      {/* Fallback when no steps yet */}
      {steps.length === 0 && currentStep && (
        <div className="flex items-center gap-1.5 text-xs">
          <span className="w-3 h-3 rounded-full bg-[var(--accent-orange)] animate-pulse shrink-0" />
          <span className="text-text-secondary">{currentStep}</span>
        </div>
      )}

      {/* Pulsing dots when no steps and no currentStep */}
      {steps.length === 0 && !currentStep && (
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

      {/* Elapsed timer — Wiii personality */}
      {startTime && (
        <motion.div
          className="text-[11px] text-text-tertiary tabular-nums mt-1"
          animate={{ opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        >
          {elapsed < 5
            ? "Wiii đang đọc..."
            : elapsed < 15
              ? `Wiii suy nghĩ ${elapsed}s`
              : elapsed >= 60
                ? `Wiii phân tích kỹ ${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`
                : `Wiii tư duy ${elapsed}s`}
        </motion.div>
      )}
    </div>
  );
}
