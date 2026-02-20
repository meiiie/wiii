/**
 * ThinkingTimeline — collapsible vertical timeline for completed messages
 * with 3+ thinking/action_text phases.
 *
 * Sprint 149 "Dòng Chảy Tư Duy":
 * - Collapsed header: "Quá trình tư duy · N giai đoạn · Xs"
 * - Expanded: vertical timeline with green dots (thinking) and orange dots (action_text)
 * - Connecting line between dots
 */
import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, CheckCircle } from "lucide-react";
import type { ContentBlock, ThinkingBlockData, ActionTextBlockData, ThinkingLevel } from "@/api/types";
import { ThinkingBlock } from "./ThinkingBlock";
import { ActionText } from "./ActionText";

interface ThinkingTimelineProps {
  phases: ContentBlock[];
  thinkingLevel: ThinkingLevel;
}

export function ThinkingTimeline({ phases, thinkingLevel }: ThinkingTimelineProps) {
  const [expanded, setExpanded] = useState(false);

  // Count thinking blocks for phase count
  const thinkingBlocks = phases.filter((b) => b.type === "thinking") as ThinkingBlockData[];
  const phaseCount = thinkingBlocks.length;

  // Calculate total duration from first startTime to last endTime
  const totalDuration = (() => {
    let firstStart: number | undefined;
    let lastEnd: number | undefined;
    for (const block of thinkingBlocks) {
      if (block.startTime && (firstStart === undefined || block.startTime < firstStart)) {
        firstStart = block.startTime;
      }
      if (block.endTime && (lastEnd === undefined || block.endTime > lastEnd)) {
        lastEnd = block.endTime;
      }
    }
    if (firstStart && lastEnd) {
      return Math.round((lastEnd - firstStart) / 1000);
    }
    return 0;
  })();

  const durationText = totalDuration > 0
    ? totalDuration >= 60
      ? `${Math.floor(totalDuration / 60)}:${String(totalDuration % 60).padStart(2, "0")}`
      : `${totalDuration}s`
    : "";

  return (
    <div className="mb-2" data-testid="thinking-timeline">
      {/* Collapsed header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-[13px] text-text-tertiary hover:text-text-secondary transition-colors"
        aria-expanded={expanded}
        data-testid="thinking-timeline-toggle"
      >
        <CheckCircle size={14} className="text-[var(--accent-green)] shrink-0" />
        <span className="font-medium">Quá trình tư duy</span>
        <span className="text-text-tertiary/70">·</span>
        <span className="tabular-nums">{phaseCount} giai đoạn</span>
        {durationText && (
          <>
            <span className="text-text-tertiary/70">·</span>
            <span className="tabular-nums">{durationText}</span>
          </>
        )}
        <ChevronDown
          size={14}
          className={`shrink-0 transition-transform duration-200 ${
            expanded ? "rotate-0" : "-rotate-90"
          }`}
        />
      </button>

      {/* Expanded timeline */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="thinking-timeline mt-2">
              {phases.map((block, i) => {
                const isLast = i === phases.length - 1;
                const isThinking = block.type === "thinking";

                return (
                  <div key={block.id} className="thinking-timeline-step">
                    {/* Dot */}
                    <div
                      className={`thinking-timeline-dot ${
                        isThinking ? "" : "thinking-timeline-dot--action"
                      }`}
                    />
                    {/* Connecting line (skip on last item) */}
                    {!isLast && <div className="thinking-timeline-line" />}
                    {/* Content */}
                    <div className="thinking-timeline-content">
                      {isThinking ? (
                        <ThinkingBlock
                          content={(block as ThinkingBlockData).content}
                          toolCalls={(block as ThinkingBlockData).toolCalls}
                          savedDuration={
                            (block as ThinkingBlockData).startTime && (block as ThinkingBlockData).endTime
                              ? Math.round(
                                  ((block as ThinkingBlockData).endTime! -
                                    (block as ThinkingBlockData).startTime!) /
                                    1000
                                )
                              : undefined
                          }
                          label={(block as ThinkingBlockData).label}
                          summary={(block as ThinkingBlockData).summary || (block as ThinkingBlockData).label}
                          thinkingLevel={thinkingLevel}
                        />
                      ) : block.type === "action_text" ? (
                        <ActionText
                          content={(block as ActionTextBlockData).content}
                          node={(block as ActionTextBlockData).node}
                        />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
