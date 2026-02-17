import { useState } from "react";
import { ChevronRight, AlertTriangle } from "lucide-react";
import type { ReasoningTrace as ReasoningTraceType, ReasoningStep } from "@/api/types";

interface ReasoningTraceProps {
  trace: ReasoningTraceType;
}

/**
 * Step-by-step reasoning trace display.
 *
 * - Collapsed by default
 * - Header: total steps, total duration, final confidence badge
 * - Each step: icon, step_name, result, duration, confidence %
 * - Correction warning if was_corrected
 */
export function ReasoningTrace({ trace }: ReasoningTraceProps) {
  const [expanded, setExpanded] = useState(false);

  if (!trace || !trace.steps || trace.steps.length === 0) return null;

  const totalDurationSec = (trace.total_duration_ms / 1000).toFixed(1);

  return (
    <div className="my-2 rounded-lg border border-[var(--border)] bg-[var(--surface-secondary)] overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:opacity-80 transition-opacity"
      >
        <ChevronRight
          size={14}
          className={`text-text-tertiary transition-transform duration-200 shrink-0 ${
            expanded ? "rotate-90" : ""
          }`}
        />
        <span className="text-xs text-text-secondary">
          Reasoning ({trace.total_steps} steps, {totalDurationSec}s)
        </span>
        <ConfidenceBadge confidence={trace.final_confidence} />
      </button>

      {/* Expanded steps */}
      {expanded && (
        <div className="border-t border-[var(--border)] px-3 py-2 space-y-1">
          {trace.steps.map((step, i) => (
            <StepRow key={i} step={step} />
          ))}
          {trace.was_corrected && trace.correction_reason && (
            <div className="flex items-center gap-1.5 mt-1 text-[11px] text-amber-600 dark:text-amber-400">
              <AlertTriangle size={12} />
              <span>{trace.correction_reason}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StepRow({ step }: { step: ReasoningStep }) {
  const durationSec = (step.duration_ms / 1000).toFixed(1);
  const icon = getStepIcon(step);

  return (
    <div className="flex items-center gap-2 text-[11px]">
      <span className="shrink-0 w-3 text-center">{icon}</span>
      <span className="font-medium text-text-secondary truncate">
        {step.step_name}
      </span>
      <span className="text-text-tertiary truncate flex-1">
        {step.result}
      </span>
      <span className="text-text-tertiary shrink-0">{durationSec}s</span>
      {typeof step.confidence === "number" && (
        <ConfidenceBadge confidence={step.confidence} small />
      )}
    </div>
  );
}

function getStepIcon(step: ReasoningStep): string {
  if (step.step_name.includes("rewrite")) return "↻";
  if (typeof step.confidence === "number" && step.confidence < 50) return "⚠";
  return "✓";
}

function ConfidenceBadge({
  confidence,
  small = false,
}: {
  confidence: number;
  small?: boolean;
}) {
  // Normalize: if confidence > 1, assume 0-100 scale
  const normalized = confidence > 1 ? confidence : confidence * 100;
  const pct = Math.round(normalized);

  let colorClass: string;
  if (pct >= 80) {
    colorClass = "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
  } else if (pct >= 50) {
    colorClass = "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
  } else {
    colorClass = "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
  }

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium shrink-0 ${colorClass} ${
        small ? "text-[9px] px-1 py-0" : "text-[10px] px-1.5 py-0.5"
      }`}
    >
      {pct}%
    </span>
  );
}
