import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import type {
  ContentBlock,
  ThinkingBlockData,
  ActionTextBlockData,
  ThinkingLevel,
} from "@/api/types";
import { ThinkingBlock } from "./ThinkingBlock";
import { ActionText } from "./ActionText";
import { ThinkingJourneyBanner } from "./ThinkingJourneyBanner";

interface ThinkingTimelineProps {
  phases: ContentBlock[];
  thinkingLevel: ThinkingLevel;
}

function summarizeTimeline(phases: ContentBlock[]) {
  const thinkingCount = phases.filter((block) => block.type === "thinking").length;
  const actionCount = phases.filter((block) => block.type === "action_text").length;
  const completedLabels = phases
    .filter((block): block is ThinkingBlockData => block.type === "thinking")
    .map((block) => block.summary || block.label)
    .filter((value): value is string => typeof value === "string" && value.length > 0)
    .slice(0, 3);

  return {
    thinkingCount,
    actionCount,
    completedLabels,
  };
}

export function ThinkingTimeline({ phases, thinkingLevel }: ThinkingTimelineProps) {
  const [expanded, setExpanded] = useState(false);
  const summary = useMemo(() => summarizeTimeline(phases), [phases]);

  return (
    <div className="mb-2" data-testid="thinking-timeline">
      <ThinkingJourneyBanner
        blocks={phases}
        expanded={expanded}
        onToggle={() => setExpanded(!expanded)}
      />

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="thinking-timeline__intro">
              <span>{summary.thinkingCount} nhip suy luan</span>
              <span>{summary.actionCount} lan doi nhip</span>
              {summary.completedLabels.length > 0 && (
                <span>{summary.completedLabels.join(" · ")}</span>
              )}
            </div>

            <div className="thinking-timeline mt-2">
              {phases.map((block, index) => {
                const isLast = index === phases.length - 1;
                const isThinking = block.type === "thinking";
                const savedDuration = isThinking &&
                  (block as ThinkingBlockData).startTime &&
                  (block as ThinkingBlockData).endTime
                    ? Math.round(
                        ((block as ThinkingBlockData).endTime! - (block as ThinkingBlockData).startTime!) / 1000,
                      )
                    : undefined;

                return (
                  <div
                    key={block.id}
                    className={`thinking-timeline-step ${isThinking ? "thinking-timeline-step--thinking" : "thinking-timeline-step--action-shell"}`}
                  >
                    <div
                      className={`thinking-timeline-dot ${
                        isThinking ? "" : "thinking-timeline-dot--action"
                      }`}
                    />
                    {!isLast && <div className="thinking-timeline-line" />}

                    <div className="thinking-timeline-content">
                      {isThinking ? (
                        <ThinkingBlock
                          content={(block as ThinkingBlockData).content}
                          toolCalls={(block as ThinkingBlockData).toolCalls}
                          savedDuration={savedDuration}
                          label={(block as ThinkingBlockData).label}
                          summary={
                            (block as ThinkingBlockData).summary ||
                            (block as ThinkingBlockData).label
                          }
                          phase={(block as ThinkingBlockData).phase}
                          autoExpand={expanded}
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
